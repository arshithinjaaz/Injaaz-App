import os
from flask import Flask, send_from_directory, abort, render_template, jsonify
from concurrent.futures import ThreadPoolExecutor

# App config constants (ensure you created config.py as instructed)
from config import BASE_DIR, GENERATED_DIR, UPLOADS_DIR, JOBS_DIR

# Import the blueprints for the three standardized modules.
# Make sure these module files exist at the paths:
# - module_hvac_mep/routes.py  (hvac_mep_bp)
# - module_civil/routes.py     (civil_bp)
# - module_cleaning/routes.py  (cleaning_bp)
from module_hvac_mep.routes import hvac_mep_bp
from module_civil.routes import civil_bp
from module_cleaning.routes import cleaning_bp

# Ensure required directories exist at startup
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)

# Simple background executor for report generation tasks
executor = ThreadPoolExecutor(max_workers=2)

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # App-wide config used by blueprints and utils
    app.config['BASE_DIR'] = BASE_DIR
    app.config['GENERATED_DIR'] = GENERATED_DIR
    app.config['UPLOADS_DIR'] = UPLOADS_DIR
    app.config['JOBS_DIR'] = JOBS_DIR
    app.config['EXECUTOR'] = executor

    # Register blueprints with consistent URL prefixes
    app.register_blueprint(hvac_mep_bp, url_prefix='/hvac-mep')
    app.register_blueprint(civil_bp, url_prefix='/civil')
    app.register_blueprint(cleaning_bp, url_prefix='/cleaning')

    # Root route: dashboard
    @app.route('/')
    def index():
        return render_template('dashboard.html')

    # Serve generated files (downloads)
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