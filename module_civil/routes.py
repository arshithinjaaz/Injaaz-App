import os
import json
import logging
from flask import Blueprint, current_app, render_template, request, jsonify, url_for
from common.utils import random_id, save_uploaded_file_cloud, mark_job_started, update_job_progress, mark_job_done

logger = logging.getLogger(__name__)

try:
    from .civil_generators import create_excel_report, create_pdf_report
except Exception:
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
    fields = dict(request.form)
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
            except Exception as e:
                logger.error(f"Failed to upload file: {e}")
                return jsonify({"error": f"Cloud storage error: {str(e)}"}), 500
    sub_id = random_id("sub")
    subs_dir = os.path.join(GENERATED_DIR, "submissions")
    os.makedirs(subs_dir, exist_ok=True)
    submission_path = os.path.join(subs_dir, f"{sub_id}.json")
    
    submission_data = {
        "id": sub_id,
        "fields": fields,
        "files": saved_files,
        "base_url": request.host_url.rstrip('/')
    }
    
    with open(submission_path, 'w') as f:
        json.dump(submission_data, f)

    job_id = random_id("job")
    meta = {"submission_id": sub_id, "module": "civil"}
    mark_job_started(JOBS_DIR, job_id, meta=meta)

    def task_generate_reports(job_id_local, submission_path_local, base_url):
        try:
            update_job_progress(JOBS_DIR, job_id_local, 10)
            data = {}
            try:
                if submission_path_local and os.path.exists(submission_path_local):
                    with open(submission_path_local, 'r') as sf:
                        data = json.load(sf)
            except Exception:
                data = {}

            excel_name = create_excel_report(data, output_dir=GENERATED_DIR)
            update_job_progress(JOBS_DIR, job_id_local, 60)
            pdf_name = create_pdf_report(data, output_dir=GENERATED_DIR)

            results = []
            if excel_name:
                results.append({"filename": excel_name, "url": f"{base_url}/generated/{excel_name}"})
            if pdf_name:
                results.append({"filename": pdf_name, "url": f"{base_url}/generated/{pdf_name}"})

            mark_job_done(JOBS_DIR, job_id_local, results)
        except Exception as e:
            update_job_progress(JOBS_DIR, job_id_local, 0, state='failed', results=[{"error": str(e)}])

    EXECUTOR.submit(task_generate_reports, job_id, submission_path, request.host_url.rstrip('/'))
    return jsonify({"status": "queued", "job_id": job_id, "submission_id": sub_id, "files": saved_files})

@civil_bp.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    job_state_file = os.path.join(JOBS_DIR, f"{job_id}.json")
    if not os.path.exists(job_state_file):
        return jsonify({"error": "unknown job"}), 404
    with open(job_state_file, 'r') as f:
        return jsonify(json.load(f))


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
        
        # Create submission
        sub_id = random_id("sub")
        subs_dir = os.path.join(GENERATED_DIR, "submissions")
        os.makedirs(subs_dir, exist_ok=True)
        
        submission_data = {
            "id": sub_id,
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
        
        submission_path = os.path.join(subs_dir, f"{sub_id}.json")
        with open(submission_path, 'w') as f:
            json.dump(submission_data, f, indent=2)
        
        logger.info(f"✅ Civil submission {sub_id} saved with {len(processed_items)} work items")
        
        # Create job and queue background task
        job_id = random_id("job")
        meta = {
            "submission_id": sub_id,
            "module": "civil",
            "project_name": payload.get("project_name", ""),
            "items_count": len(processed_items)
        }
        mark_job_started(JOBS_DIR, job_id, meta=meta)
        
        base_url = request.host_url.rstrip('/')
        
        def task_generate_reports(job_id_local, submission_path_local, base_url):
            try:
                update_job_progress(JOBS_DIR, job_id_local, 10)
                data = {}
                if submission_path_local and os.path.exists(submission_path_local):
                    with open(submission_path_local, 'r') as sf:
                        data = json.load(sf)
                
                excel_name = create_excel_report(data, output_dir=GENERATED_DIR)
                update_job_progress(JOBS_DIR, job_id_local, 60)
                pdf_name = create_pdf_report(data, output_dir=GENERATED_DIR)
                
                results = []
                if excel_name:
                    results.append({"filename": excel_name, "url": f"{base_url}/generated/{excel_name}"})
                if pdf_name:
                    results.append({"filename": pdf_name, "url": f"{base_url}/generated/{pdf_name}"})
                
                mark_job_done(JOBS_DIR, job_id_local, results)
            except Exception as e:
                update_job_progress(JOBS_DIR, job_id_local, 0, state='failed', results=[{"error": str(e)}])
        
        EXECUTOR.submit(task_generate_reports, job_id, submission_path, base_url)
        
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