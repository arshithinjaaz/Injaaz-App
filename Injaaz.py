import os
import sys
import logging
from flask import Flask, send_from_directory, abort, render_template, jsonify, request
from concurrent.futures import ThreadPoolExecutor
from werkzeug.exceptions import HTTPException
from flask_jwt_extended import JWTManager

# Import Flask extensions
from app.models import db, bcrypt

# App config constants (ensure config.py exists)
from config import BASE_DIR, GENERATED_DIR, UPLOADS_DIR, JOBS_DIR

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Try importing blueprints; if any import fails we log and continue so the app still starts.
hvac_mep_bp = None
civil_bp = None
cleaning_bp = None
auth_bp = None

try:
    from module_hvac_mep.routes import hvac_mep_bp  # noqa: F401
    logger.info("Imported module_hvac_mep.routes.hvac_mep_bp")
except Exception as e:
    logger.exception("Could not import module_hvac_mep.routes.hvac_mep_bp: %s", e)
    hvac_mep_bp = None

try:
    from module_civil.routes import civil_bp  # noqa: F401
    logger.info("Imported module_civil.routes.civil_bp")
except Exception as e:
    logger.exception("Could not import module_civil.routes.civil_bp: %s", e)
    civil_bp = None

try:
    from module_cleaning.routes import cleaning_bp  # noqa: F401
    logger.info("Imported module_cleaning.routes.cleaning_bp")
except Exception as e:
    logger.exception("Could not import module_cleaning.routes.cleaning_bp: %s", e)
    cleaning_bp = None

try:
    from app.auth.routes import auth_bp  # noqa: F401
    logger.info("Imported app.auth.routes.auth_bp")
except Exception as e:
    logger.exception("Could not import app.auth.routes.auth_bp: %s", e)
    auth_bp = None

# Ensure required directories exist at startup
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)

# Simple background executor for report generation tasks
executor = ThreadPoolExecutor(max_workers=2)


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # Load configuration from config.py
    app.config.from_object('config')
    
    # Validate critical settings
    flask_env = app.config.get('FLASK_ENV', 'development')
    secret_key = app.config.get('SECRET_KEY')
    jwt_secret_key = app.config.get('JWT_SECRET_KEY')
    
    if flask_env == 'production':
        if not secret_key or secret_key in ['dev-secret', 'dev-secret-change-in-production', 'change-me', 'change-me-in-production']:
            logger.error("❌ CRITICAL: SECRET_KEY not set or using default value in production!")
            sys.exit(1)
        if not jwt_secret_key or jwt_secret_key in ['change-me', 'change-me-jwt-secret']:
            logger.error("❌ CRITICAL: JWT_SECRET_KEY not set or using default value in production!")
            sys.exit(1)
        if len(secret_key) < 32:
            logger.error("❌ CRITICAL: SECRET_KEY too short (min 32 characters)!")
            sys.exit(1)
    
    # Initialize Flask extensions
    db.init_app(app)
    bcrypt.init_app(app)
    
    # Initialize JWT
    jwt = JWTManager(app)
    
    # JWT token verification callback (check if token is revoked)
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        from app.models import Session
        jti = jwt_payload['jti']
        session = Session.query.filter_by(token_jti=jti).first()
        return session is None or session.is_revoked
    
    logger.info("✅ Database and JWT initialized")
    
    # Set environment variables for cloudinary library
    if app.config.get('CLOUDINARY_CLOUD_NAME'):
        os.environ['CLOUDINARY_CLOUD_NAME'] = app.config['CLOUDINARY_CLOUD_NAME']
    if app.config.get('CLOUDINARY_API_KEY'):
        os.environ['CLOUDINARY_API_KEY'] = app.config['CLOUDINARY_API_KEY']
    if app.config.get('CLOUDINARY_API_SECRET'):
        os.environ['CLOUDINARY_API_SECRET'] = app.config['CLOUDINARY_API_SECRET']
    
    # Set Redis URL for other services
    redis_url = app.config.get('REDIS_URL')
    if redis_url:
        os.environ['REDIS_URL'] = redis_url
    
    logger.info(f"✅ Cloudinary configured: {app.config.get('CLOUDINARY_CLOUD_NAME')}")
    
    # Warn if using default secret (only in dev)
    if flask_env != 'production' and app.config['SECRET_KEY'] in ['dev-secret-change-in-production', 'change-me-in-production']:
        logger.warning("⚠️  Using default SECRET_KEY! Set SECRET_KEY in .env for production!")

    # App-wide config used by blueprints and utils
    app.config['BASE_DIR'] = BASE_DIR
    app.config['GENERATED_DIR'] = GENERATED_DIR
    app.config['UPLOADS_DIR'] = UPLOADS_DIR
    app.config['JOBS_DIR'] = JOBS_DIR
    app.config['EXECUTOR'] = executor
    
    # Setup rate limiting with Redis
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        
        # Get Redis URL from config (Upstash with TLS)
        redis_url = getattr(config, 'REDIS_URL', None) or os.environ.get('RATELIMIT_STORAGE_URL') or os.environ.get('REDIS_URL')
        
        if redis_url:
            try:
                limiter = Limiter(
                    app=app,
                    key_func=get_remote_address,
                    default_limits=[os.environ.get('RATELIMIT_DEFAULT', '100 per hour')],
                    storage_uri=redis_url,
                    strategy="fixed-window"
                )
                app.limiter = limiter
                logger.info("✓ Rate limiting enabled with Redis storage")
            except Exception as redis_error:
                logger.warning(f"⚠️  Redis connection failed - Rate limiting disabled: {redis_error}")
                app.limiter = None
        else:
            logger.info("✓ Rate limiting disabled (local development mode)")
            app.limiter = None
    except ImportError:
        logger.warning("⚠️  Flask-Limiter not installed - rate limiting disabled")
        app.limiter = None
    except Exception as e:
        logger.warning(f"⚠️  Rate limiting setup failed: {e}")
        app.limiter = None
    
    # Setup CSRF protection (if Flask-WTF available)
    try:
        from flask_wtf.csrf import CSRFProtect
        
        # Enable CSRF in production by default, disable in dev unless explicitly enabled
        enable_csrf = (
            os.environ.get('FLASK_ENV') == 'production' or 
            os.environ.get('ENABLE_CSRF', '').lower() == 'true'
        ) and os.environ.get('DISABLE_CSRF', '').lower() != 'true'
        
        if enable_csrf:
            csrf = CSRFProtect(app)
            app.csrf = csrf
            logger.info("✓ CSRF protection enabled")
        else:
            logger.warning("⚠️  CSRF protection disabled (development mode)")
            app.csrf = None
    except ImportError:
        logger.warning("⚠️  Flask-WTF not installed - CSRF protection disabled")
        app.csrf = None
    
    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Resource not found"}), 404
        return render_template('404.html') if os.path.exists(os.path.join(app.template_folder, '404.html')) else ("Not Found", 404)
    
    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large. Maximum upload size: 100MB"}), 413
    
    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        logger.warning(f"Rate limit exceeded from IP: {request.remote_addr}")
        return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
    
    @app.errorhandler(500)
    def internal_error(e):
        logger.exception(f"Internal server error: {e}")
        return jsonify({"error": "Internal server error", "request_id": request.headers.get('X-Request-ID', 'unknown')}), 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        # Pass through HTTP errors
        if isinstance(e, HTTPException):
            return e
        
        # Log the error
        logger.exception(f"Unhandled exception: {e}")
        
        # Return JSON error for API calls
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({"error": "An unexpected error occurred"}), 500
        
        # Return HTML error for browser requests
        return "An unexpected error occurred", 500
    
    # PWA Routes
    @app.route('/offline')
    def offline():
        """Offline fallback page for PWA"""
        return render_template('offline.html')
    
    @app.route('/manifest.json')
    def pwa_manifest():
        """Serve PWA manifest"""
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

    # Register blueprints only if they were imported successfully.
    if hvac_mep_bp:
        app.register_blueprint(hvac_mep_bp, url_prefix='/hvac-mep')  # Must be /hvac-mep with dash
        logger.info("✓ Registered HVAC/MEP blueprint at /hvac-mep")
    else:
        # Provide a helpful placeholder endpoint so someone visiting knows the blueprint failed to import
        @app.route('/hvac-mep')
        def hvac_mep_missing():
            return (
                "HVAC & MEP module is not available on this deployment. "
                "Check server logs for import errors."
            ), 500

    if civil_bp:
        app.register_blueprint(civil_bp, url_prefix='/civil')
        logger.info("Registered blueprint: /civil")
    else:
        @app.route('/civil')
        def civil_missing():
            return (
                "Civil module is not available on this deployment. "
                "Check server logs for import errors."
            ), 500

    if cleaning_bp:
        app.register_blueprint(cleaning_bp, url_prefix='/cleaning')
        logger.info("Registered blueprint: /cleaning")
    else:
        @app.route('/cleaning')
        def cleaning_missing():
            return (
                "Cleaning module is not available on this deployment. "
                "Check server logs for import errors."
            ), 500

    # Register authentication blueprint
    if auth_bp:
        app.register_blueprint(auth_bp)  # Already has /api/auth prefix
        logger.info("✅ Registered authentication blueprint at /api/auth")
    else:
        logger.warning("⚠️  Authentication blueprint not available - check imports")

    # Security headers middleware
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # Global error handlers
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
            return jsonify({"error": "Resource not found"}), 404
        return "<h1>404 Not Found</h1><p>The page you're looking for doesn't exist.</p>", 404
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({"error": "File too large. Maximum 100MB total."}), 413

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
            return jsonify({"error": "Internal server error"}), 500
        return "<h1>500 Internal Server Error</h1><p>Something went wrong. Please try again.</p>", 500

    # Authentication routes
    @app.route('/login')
    def login_page():
        """Render login page"""
        return render_template('login.html')
    
    @app.route('/register')
    def register_page():
        """Render register page"""
        return render_template('register.html')
    
    @app.route('/logout')
    def logout_page():
        """Logout and redirect to login"""
        # Clear any local storage via JS or just redirect
        return render_template('logout.html')
    
    @app.route('/dashboard')
    def dashboard():
        """Protected dashboard - requires authentication"""
        return render_template('dashboard.html')
    
    # Root route: redirect to dashboard or login
    @app.route('/')
    def index():
        # In a real app, check if user is authenticated
        # For now, redirect to dashboard (which can be protected later)
        try:
            return render_template('dashboard.html')
        except Exception as e:
            # If template rendering raises, log and return safe fallback.
            logger.error(f"Error rendering dashboard.html: {e}")
            return (
                "<html><body>"
                "<h1>Injaaz App — Dashboard (Fallback)</h1>"
                "<ul>"
                "<li><a href='/hvac-mep/form'>HVAC & MEP</a></li>"
                "<li><a href='/civil/form'>Civil</a></li>"
                "<li><a href='/cleaning/form'>Cleaning</a></li>"
                "</ul>"
                "<p><a href='/login'>Login</a> | <a href='/register'>Register</a></p>"
                "<p>Check server logs for template/render or import errors.</p>"
                "</body></html>"
            )

    # Serve generated files (downloads) with security checks
    GENERATED_DIR_NAME = os.path.basename(GENERATED_DIR.rstrip(os.sep))
    @app.route(f'/{GENERATED_DIR_NAME}/<path:filename>')
    def download_generated(filename):
        # Security: prevent path traversal
        from common.security import safe_path_join
        try:
            safe_path = safe_path_join(GENERATED_DIR, filename)
            if not os.path.exists(safe_path):
                logger.warning(f"File not found: {filename}")
                abort(404)
            logger.info(f"Serving file: {filename}")
            return send_from_directory(GENERATED_DIR, filename, as_attachment=True)
        except ValueError as e:
            logger.warning(f"Path traversal attempt blocked: {filename}")
            abort(403)

    # Enhanced health endpoint with dependency checks
    @app.route('/health')
    def health():
        checks = {
            "status": "ok",
            "filesystem": os.access(GENERATED_DIR, os.W_OK),
            "executor": executor is not None,
        }
        
        # Check Cloudinary
        try:
            checks["cloudinary"] = bool(app.config.get('CLOUDINARY_CLOUD_NAME'))
        except Exception:
            checks["cloudinary"] = False
        
        # Check Redis (if configured)
        redis_url = os.environ.get('REDIS_URL')
        if redis_url:
            try:
                import redis
                r = redis.from_url(redis_url, socket_connect_timeout=2)
                r.ping()
                checks["redis"] = True
            except Exception:
                checks["redis"] = False
        
        # Overall status
        all_ok = all([checks["filesystem"], checks["executor"]])
        status_code = 200 if all_ok else 503
        
        return jsonify(checks), status_code

    return app


if __name__ == '__main__':
    app = create_app()
    # For local development use debug=True. Remove or set False in production.
    app.run(debug=True, host='0.0.0.0', port=5000)