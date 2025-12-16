import os
import json
import time
import tempfile
import traceback
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, url_for, send_from_directory

# Optional Cloudinary
try:
    import cloudinary
    import cloudinary.uploader
    _HAS_CLOUDINARY = True
except Exception:
    _HAS_CLOUDINARY = False

# Redis + RQ optional
try:
    import redis
    from rq import Queue
    from redis.exceptions import RedisError
    _HAS_REDIS = True
except Exception:
    redis = None
    Queue = None
    RedisError = Exception
    _HAS_REDIS = False

# Import local helpers (ensure these files exist in module_hvac_mep/utils)
from .utils.email_sender import send_outlook_email
from .utils.excel_writer import create_report_workbook
from .utils.pdf_generator import generate_visit_pdf
from .utils.state import save_report_state, get_report_state

# Configuration (environment)
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')
CLOUDINARY_UPLOAD_PRESET = os.environ.get('CLOUDINARY_UPLOAD_PRESET', 'render_site_upload')

REDIS_URL = os.environ.get('REDIS_URL', '')

BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BLUEPRINT_DIR)
TEMPLATE_ABSOLUTE_PATH = os.path.join(BLUEPRINT_DIR, 'templates')
DROPDOWN_DATA_PATH = os.path.join(BLUEPRINT_DIR, 'dropdown_data.json')

# Do NOT use current_app at import time. Provide a default and a getter that reads app config at runtime.
DEFAULT_GENERATED_DIR = os.path.join(BASE_DIR, 'generated')

def get_generated_dir():
    """Return the generated directory: prefer app config at runtime, fallback to module default."""
    try:
        from flask import current_app
        return current_app.config.get('GENERATED_DIR', DEFAULT_GENERATED_DIR)
    except Exception:
        return DEFAULT_GENERATED_DIR

hvac_mep_bp = Blueprint(
    'hvac_mep_bp',
    __name__,
    template_folder=TEMPLATE_ABSOLUTE_PATH,
    static_folder='static'
)

# Cloudinary init (best-effort)
if _HAS_CLOUDINARY:
    try:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
    except Exception:
        _HAS_CLOUDINARY = False

# Redis + RQ queue (optional)
q = None
if _HAS_REDIS and REDIS_URL:
    try:
        redis_conn = redis.from_url(REDIS_URL, socket_connect_timeout=5, decode_responses=True)
        redis_conn.ping()
        q = Queue('default', connection=redis_conn)
    except Exception:
        redis_conn = None
        q = None
else:
    redis_conn = None
    q = None

# Utility to upload base64 signature to Cloudinary (if available)
def upload_base64_to_cloudinary(base64_string, public_id_prefix):
    if not base64_string or not _HAS_CLOUDINARY:
        return None
    try:
        upload_result = cloudinary.uploader.upload(
            file=base64_string,
            folder="signatures",
            public_id=f"{public_id_prefix}_{int(time.time())}"
        )
        return upload_result.get('secure_url')
    except Exception:
        return None

# Routes
@hvac_mep_bp.route('/form')
def index():
    return render_template('hvac_mep_form.html')

@hvac_mep_bp.route('/dropdowns')
def get_dropdown_data():
    try:
        with open(DROPDOWN_DATA_PATH, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Dropdown data file not found"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON data"}), 500

@hvac_mep_bp.route('/api/submit/metadata', methods=['POST'])
def submit_metadata():
    try:
        data = request.json or {}
        visit_info = data.get('visit_info', {})
        processed_items = data.get('report_items', [])
        signatures = data.get('signatures', {})

        tech_sig_url = upload_base64_to_cloudinary(signatures.get('tech_signature'), 'hvac_tech') if _HAS_CLOUDINARY else None
        opman_sig_url = upload_base64_to_cloudinary(signatures.get('opMan_signature'), 'hvac_opman') if _HAS_CLOUDINARY else None

        visit_info['tech_signature_url'] = tech_sig_url
        visit_info['opMan_signature_url'] = opman_sig_url

        report_id = f"hvac-report-{int(time.time())}"

        save_report_state(report_id, {
            'visit_info': visit_info,
            'report_items': processed_items,
            'photo_urls': []
        })

        return jsonify({
            "status": "success",
            "visit_id": report_id,
            "cloudinary_cloud_name": CLOUDINARY_CLOUD_NAME,
            "cloudinary_upload_preset": CLOUDINARY_UPLOAD_PRESET,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Failed to process metadata: {str(e)}"}), 500

@hvac_mep_bp.route('/api/submit/update-photos', methods=['POST'])
def update_photos():
    report_id = request.args.get('visit_id')
    if not report_id:
        return jsonify({"error": "Missing visit_id"}), 400
    record = get_report_state(report_id)
    if not record:
        return jsonify({"error": "Report record not found"}), 500
    try:
        data = request.json or {}
        photo_urls = data.get('photo_urls', [])
        record['photo_urls'] = photo_urls
        save_report_state(report_id, record)
        return jsonify({"status": "success"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Failed to update photo URLs: {str(e)}"}), 500

@hvac_mep_bp.route('/api/submit/finalize', methods=['GET'])
def finalize_report():
    report_id = request.args.get('visit_id')
    if not report_id:
        return jsonify({"error": "Missing visit_id parameter for finalization."}), 400

    record = get_report_state(report_id)
    if not record:
        return jsonify({"error": "Report record not found."}), 500

    try:
        visit_info = record.get('visit_info', {}) or {}
        final_items = record.get('report_items', []) or []
        final_photo_urls = record.get('photo_urls', []) or []

        # Build URL map for photos (optional)
        url_map = {}
        for url_data in final_photo_urls:
            try:
                key = (int(url_data.get('item_index', 0)), int(url_data.get('photo_index', 0)))
                url_map[key] = url_data.get('photo_url')
            except Exception:
                continue
        for item_index, item in enumerate(final_items):
            image_urls = []
            for photo_index in range(int(item.get('photo_count', 0))):
                key = (item_index, photo_index)
                photo_url = url_map.get(key)
                if photo_url:
                    image_urls.append(photo_url)
            item['image_urls'] = image_urls
            item.pop('photo_count', None)

        gen_dir = get_generated_dir()
        os.makedirs(gen_dir, exist_ok=True)

        # Create Excel synchronously
        excel_path, excel_filename = create_report_workbook(gen_dir, visit_info, final_items)

        # If no queue, generate PDF synchronously
        if q is None:
            pdf_path, pdf_filename = generate_visit_pdf(visit_info, final_items, gen_dir)
            attachments = [p for p in (excel_path, pdf_path) if p and os.path.exists(p)]
            try:
                send_outlook_email(f"HVAC Report: {visit_info.get('building_name','Unknown')}", "Report generated", attachments, visit_info.get('email'))
            except Exception:
                pass

            return jsonify({
                "status": "success",
                "excel_url": url_for('hvac_mep_bp.download_generated', filename=excel_filename, _external=True),
                "pdf_url": url_for('hvac_mep_bp.download_generated', filename=pdf_filename, _external=True)
            })

        # Enqueue background job (if Redis/RQ available)
        from .utils.tasks import generate_and_send_report  # noqa: E402
        job = q.enqueue(generate_and_send_report, report_id, visit_info, final_items, gen_dir, job_timeout=1800)
        try:
            if redis_conn is not None:
                redis_conn.set(f"report:{report_id}", json.dumps({"status": "pending", "job_id": job.get_id()}))
        except Exception:
            pass

        return jsonify({
            "status": "accepted",
            "visit_id": report_id,
            "job_id": job.get_id(),
            "status_url": url_for('hvac_mep_bp.report_status', visit_id=report_id, _external=True)
        }), 202

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500

@hvac_mep_bp.route('/api/report-status', methods=['GET'])
def report_status():
    visit_id = request.args.get('visit_id')
    if not visit_id:
        return jsonify({"error": "Missing visit_id"}), 400
    if redis_conn is None:
        return jsonify({"status": "error", "message": "Redis not configured on server."}), 500
    key = f"report:{visit_id}"
    result = redis_conn.get(key)
    if not result:
        return jsonify({"status": "unknown"}), 404
    try:
        data = json.loads(result)
        return jsonify({"status": "ok", "report": data})
    except Exception:
        return jsonify({"status": "ok", "report_raw": result})

@hvac_mep_bp.route('/generated/<path:filename>')
def download_generated(filename):
    gen_dir = get_generated_dir()
    return send_from_directory(gen_dir, filename, as_attachment=True)