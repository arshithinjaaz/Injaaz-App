from flask import Blueprint

hvac_mep_bp = Blueprint(
    'hvac_mep_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    url_prefix='/hvac-mep'
)

# Import routes when package is imported so blueprint gets registered
from . import routes  # noqa: F401