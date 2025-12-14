# in app/__init__.py (or wherever you register blueprints)
from .site_visit_form import bp as site_visit_form_bp
app.register_blueprint(site_visit_form_bp)