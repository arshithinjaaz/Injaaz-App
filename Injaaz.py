import os
import logging
from flask import Flask, send_from_directory, abort, render_template, jsonify
from concurrent.futures import ThreadPoolExecutor

# App config constants (ensure config.py exists)
from config import BASE_DIR, GENERATED_DIR, UPLOADS_DIR, JOBS_DIR

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Try importing blueprints; if any import fails we log and continue so the app still starts.
hvac_mep_bp = None
civil_bp = None
cleaning_bp = None

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

# Ensure required directories exist at startup
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)

# Simple background executor for report generation tasks
executor = ThreadPoolExecutor(max_workers=2)


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # Add this to allow larger uploads
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB total upload

    # App-wide config used by blueprints and utils
    app.config['BASE_DIR'] = BASE_DIR
    app.config['GENERATED_DIR'] = GENERATED_DIR
    app.config['UPLOADS_DIR'] = UPLOADS_DIR
    app.config['JOBS_DIR'] = JOBS_DIR
    app.config['EXECUTOR'] = executor

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

    # Root route: dashboard (fallback to a simple HTML if template is missing)
    @app.route('/')
    def index():
        dashboard_path = os.path.join(app.template_folder or '', 'dashboard.html')
        if os.path.exists(dashboard_path):
            try:
                return render_template('dashboard.html')
            except Exception:
                # If template rendering raises, log and return safe fallback.
                logger.exception("Error rendering dashboard.html")
        # Fallback simple dashboard if template missing or rendering failed
        return (
            "<html><body>"
            "<h1>Injaaz App — Dashboard (Fallback)</h1>"
            "<ul>"
            "<li><a href='/hvac-mep'>HVAC & MEP</a></li>"
            "<li><a href='/civil'>Civil</a></li>"
            "<li><a href='/cleaning'>Cleaning</a></li>"
            "</ul>"
            "<p>Check server logs for template/render or import errors.</p>"
            "</body></html>"
        )

    # Serve generated files (downloads) using the GENERATED_DIR base name
    GENERATED_DIR_NAME = os.path.basename(GENERATED_DIR.rstrip(os.sep))
    @app.route(f'/{GENERATED_DIR_NAME}/<path:filename>')
    def download_generated(filename):
        full_path = os.path.join(GENERATED_DIR, filename)
        if not os.path.exists(full_path):
            abort(404)
        return send_from_directory(GENERATED_DIR, filename, as_attachment=True)

    # Simple health endpoint
    @app.route('/health')
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == '__main__':
    app = create_app()
    # For local development use debug=True. Remove or set False in production.
    app.run(debug=True, host='0.0.0.0', port=5000)