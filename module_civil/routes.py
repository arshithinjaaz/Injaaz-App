import os
import json
import logging
from flask import Blueprint, current_app, render_template, request, jsonify, url_for
from common.utils import random_id, save_uploaded_file_cloud
from common.db_utils import create_submission_db, create_job_db, update_job_progress_db, complete_job_db, fail_job_db, get_job_status_db, get_submission_db
from app.models import db

logger = logging.getLogger(__name__)

try:
    from .civil_generators import create_excel_report, create_pdf_report
except (ImportError, ModuleNotFoundError) as e:
    logger.warning(f"Could not import civil_generators: {e}")
    def create_excel_report(data, output_dir):
        basename = f"civil_report_{random_id('')}.xlsx"
        path = os.path.join(output_dir, basename)
        with open(path, "wb") as f:
            f.write(b"Dummy CIVIL EXCEL")
        return basename
    def create_pdf_report(data, output_dir):
        basename = f"civil_report_{random_id('')}.pdf"
        path = os.path.join(output_dir, basename)
        with open(path, "wb") as f:
            f.write(b"Dummy CIVIL PDF")
        return basename

BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FOLDER = os.path.join(BLUEPRINT_DIR, 'templates')

civil_bp = Blueprint('civil_bp', __name__, template_folder=TEMPLATE_FOLDER, static_folder='static')

def app_paths():
    app = current_app
    return app.config['GENERATED_DIR'], app.config['UPLOADS_DIR'], app.config['JOBS_DIR'], app.config['EXECUTOR']

@civil_bp.route('/form', methods=['GET'])
def index():
    return render_template('civil_form.html')

@civil_bp.route('/dropdowns', methods=['GET'])
def dropdowns():
    local = os.path.join(BLUEPRINT_DIR, 'dropdown_data.json')
    if os.path.exists(local):
        with open(local, 'r') as f:
            return jsonify(json.load(f))
    central = os.path.join(current_app.config.get('BASE_DIR', ''), 'data', 'dropdown_data.json')
    if os.path.exists(central):
        with open(central, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({})

@civil_bp.route('/save-draft', methods=['POST'])
def save_draft():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    payload = request.get_json(force=True)
    draft_id = random_id("draft")
    drafts_dir = os.path.join(GENERATED_DIR, "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    with open(os.path.join(drafts_dir, f"{draft_id}.json"), 'w') as f:
        json.dump(payload, f)
    return jsonify({"status": "ok", "draft_id": draft_id})

@civil_bp.route('/submit', methods=['POST'])
def submit():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    
    # Validate required fields
    fields = dict(request.form)
    required_fields = ['project_name', 'location', 'date']
    missing = [f for f in required_fields if not fields.get(f) or not fields.get(f).strip()]
    if missing:
        logger.warning(f"Missing required fields: {missing}")
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    
    # Validate date format
    try:
        from datetime import datetime
        visit_date = datetime.strptime(fields.get('date'), '%Y-%m-%d').date()
        if visit_date > datetime.now().date():
            return jsonify({"error": "Visit date cannot be in the future"}), 400
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    
    saved_files = []
    for key in request.files:
        f = request.files.get(key)
        if f and f.filename:
            try:
                result = save_uploaded_file_cloud(f, UPLOADS_DIR, folder="civil_photos")
                saved_files.append({
                    "field": key,
                    "saved": None,
                    "url": result["url"],
                    "is_cloud": True
                })
            except (IOError, OSError) as e:
                logger.error(f"File system error uploading file: {e}")
                return jsonify({"error": "File storage error"}), 500
            except ValueError as e:
                logger.error(f"Invalid file data: {e}")
                return jsonify({"error": "Invalid file data"}), 400
            except Exception as e:
                logger.error(f"Unexpected error uploading file: {e}")
                return jsonify({"error": f"Cloud storage error: {str(e)}"}), 500
    # Create submission in database
    submission_data = {
        "fields": fields,
        "files": saved_files,
        "base_url": request.host_url.rstrip('/')
    }
    
    submission = create_submission_db(
        module_type='civil',
        form_data=submission_data,
        site_name=fields.get('project_name'),
        visit_date=fields.get('date')
    )
    sub_id = submission.submission_id

    # Create job in database
    job = create_job_db(submission)
    job_id = job.job_id

    def task_generate_reports(job_id_local, sub_id_local, base_url):
        try:
            update_job_progress_db(job_id_local, 10, status='processing')
            
            # Get submission data from database
            data = get_submission_db(sub_id_local)
            if not data:
                fail_job_db(job_id_local, "Submission not found")
                return

            excel_name = create_excel_report(data, output_dir=GENERATED_DIR)
            update_job_progress_db(job_id_local, 60)
            pdf_name = create_pdf_report(data, output_dir=GENERATED_DIR)

            results = {}
            if excel_name:
                results["excel"] = f"{base_url}/generated/{excel_name}"
                results["excel_filename"] = excel_name
            if pdf_name:
                results["pdf"] = f"{base_url}/generated/{pdf_name}"
                results["pdf_filename"] = pdf_name

            complete_job_db(job_id_local, results)
        except Exception as e:
            logger.exception(f"Report generation failed: {e}")
            fail_job_db(job_id_local, str(e))

    EXECUTOR.submit(task_generate_reports, job_id, sub_id, request.host_url.rstrip('/'))
    return jsonify({"status": "queued", "job_id": job_id, "submission_id": sub_id, "files": saved_files})

@civil_bp.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    job_data = get_job_status_db(job_id)
    if not job_data:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(job_data)


# ---------- Progressive Upload Endpoints ----------

@civil_bp.route("/upload-photo", methods=["POST"])
def upload_photo():
    """Upload a single photo immediately to cloud storage."""
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    
    try:
        if 'photo' not in request.files:
            return jsonify({"success": False, "error": "No photo file provided"}), 400
        
        photo_file = request.files['photo']
        if photo_file.filename == '':
            return jsonify({"success": False, "error": "Empty filename"}), 400
        
        result = save_uploaded_file_cloud(photo_file, UPLOADS_DIR, folder="civil_photos")
        
        if not result.get("url"):
            return jsonify({"success": False, "error": "Cloud upload failed"}), 500
        
        logger.info(f"✅ Civil photo uploaded to cloud: {result['url']}")
        
        return jsonify({
            "success": True,
            "url": result["url"],
            "filename": result.get("filename")
        })
        
    except Exception as e:
        logger.error(f"❌ Civil photo upload failed: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@civil_bp.route("/submit-with-urls", methods=["POST"])
def submit_with_urls():
    """Submit form data where photos are already uploaded to cloud."""
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    
    os.makedirs(GENERATED_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(JOBS_DIR, exist_ok=True)
    
    try:
        payload = request.get_json(force=True)
        
        # Extract work items with photo URLs
        work_items = payload.get("work_items", [])
        processed_items = []
        
        for item_data in work_items:
            photo_urls = item_data.get("photo_urls", [])
            photos_saved = []
            
            for url in photo_urls:
                photos_saved.append({
                    "saved": None,
                    "path": None,
                    "url": url,
                    "is_cloud": True
                })
            
            processed_items.append({
                "item_number": item_data.get("item_number", ""),
                "description": item_data.get("description", ""),
                "quantity": item_data.get("quantity", ""),
                "photos": photos_saved
            })
        
        # Create submission in database
        submission_data = {
            "project_name": payload.get("project_name", ""),
            "location": payload.get("location", ""),
            "visit_date": payload.get("visit_date", ""),
            "inspector_name": payload.get("inspector_name", ""),
            "inspector_signature": payload.get("inspector_signature", ""),
            "manager_name": payload.get("manager_name", ""),
            "manager_signature": payload.get("manager_signature", ""),
            "work_items": processed_items,
            "estimated_completion": payload.get("estimated_completion", ""),
            "base_url": request.host_url.rstrip('/')
        }
        
        submission = create_submission_db(
            module_type='civil',
            form_data=submission_data,
            site_name=payload.get("project_name"),
            visit_date=payload.get("visit_date")
        )
        sub_id = submission.submission_id
        
        logger.info(f"✅ Civil submission {sub_id} saved with {len(processed_items)} work items")
        
        # Create job in database
        job = create_job_db(submission)
        job_id = job.job_id
        
        base_url = request.host_url.rstrip('/')
        
        def task_generate_reports(job_id_local, sub_id_local, base_url):
            try:
                update_job_progress_db(job_id_local, 10, status='processing')
                
                # Get submission data from database
                data = get_submission_db(sub_id_local)
                if not data:
                    fail_job_db(job_id_local, "Submission not found")
                    return
                
                excel_name = create_excel_report(data, output_dir=GENERATED_DIR)
                update_job_progress_db(job_id_local, 60)
                pdf_name = create_pdf_report(data, output_dir=GENERATED_DIR)
                
                results = {}
                if excel_name:
                    results["excel"] = f"{base_url}/generated/{excel_name}"
                    results["excel_filename"] = excel_name
                if pdf_name:
                    results["pdf"] = f"{base_url}/generated/{pdf_name}"
                    results["pdf_filename"] = pdf_name
                
                complete_job_db(job_id_local, results)
            except Exception as e:
                logger.exception(f"Report generation failed: {e}")
                fail_job_db(job_id_local, str(e))
        
        EXECUTOR.submit(task_generate_reports, job_id, sub_id, base_url)
        
        logger.info(f"🚀 Civil job {job_id} queued for submission {sub_id}")
        
        return jsonify({
            "status": "ok",
            "submission_id": sub_id,
            "job_id": job_id,
            "job_status_url": url_for("civil_bp.status", job_id=job_id, _external=False)
        })
        
    except Exception as e:
        logger.error(f"❌ Civil submit with URLs failed: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500