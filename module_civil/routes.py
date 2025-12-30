import os
import json
import logging
import traceback
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, jsonify, url_for, send_from_directory
from common.utils import random_id, save_uploaded_file_cloud, upload_base64_to_cloud
from common.db_utils import create_submission_db, create_job_db, update_job_progress_db, complete_job_db, fail_job_db, get_job_status_db, get_submission_db
from app.models import db, User
from app.middleware import token_required
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.services.cloudinary_service import upload_local_file

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
@jwt_required()
def index():
    """Civil form - requires authentication and module access"""
    from flask import redirect, url_for
    from flask_jwt_extended import get_jwt_identity
    
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return render_template('access_denied.html',
                                 module='Civil Works',
                                 message='Your account is inactive. Please contact an administrator.'), 403
        
        if not user.has_module_access('civil'):
            return render_template('access_denied.html',
                                 module='Civil Works',
                                 message='You do not have access to this module. Please contact an administrator to grant access.'), 403
        
        return render_template('civil_form.html')
    except Exception as e:
        logger.error(f"Error checking module access: {str(e)}")
        # If JWT check fails, redirect to login
        return redirect(url_for('login_page'))

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

    def task_generate_reports(job_id_local, sub_id_local, base_url, app):
        logger.info(f"🔴 DEBUG: task_generate_reports called for {job_id_local}")
        with app.app_context():
            try:
                update_job_progress_db(job_id_local, 10, status='processing')
                
                # Get submission data from database
                data = get_submission_db(sub_id_local)
                if not data:
                    fail_job_db(job_id_local, "Submission not found")
                    return

                # Generate Excel
                logger.info("📊 Generating Excel report...")
                excel_path = create_excel_report(data, output_dir=GENERATED_DIR)
                excel_filename = os.path.basename(excel_path)
                logger.info(f"✅ Excel created: {excel_filename}")
                excel_url = f"{base_url}/generated/{excel_filename}"
                update_job_progress_db(job_id_local, 40)

                # Generate PDF
                logger.info("📄 Generating PDF report...")
                pdf_path = create_pdf_report(data, output_dir=GENERATED_DIR)
                pdf_filename = os.path.basename(pdf_path)
                logger.info(f"✅ PDF created: {pdf_filename}")
                pdf_url = f"{base_url}/generated/{pdf_filename}"
                update_job_progress_db(job_id_local, 60)

                # Set results
                results = {
                    "excel": excel_url,
                    "excel_filename": excel_filename,
                    "pdf": pdf_url,
                    "pdf_filename": pdf_filename
                }

                complete_job_db(job_id_local, results)
            except Exception as e:
                logger.exception(f"Report generation failed: {e}")
                fail_job_db(job_id_local, str(e))

    EXECUTOR.submit(task_generate_reports, job_id, sub_id, request.host_url.rstrip('/'), current_app._get_current_object())
    return jsonify({"status": "queued", "job_id": job_id, "submission_id": sub_id, "files": saved_files})

@civil_bp.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    try:
        job_data = get_job_status_db(job_id)
        if not job_data:
            return jsonify({"error": "unknown job"}), 404
        return jsonify(job_data)
    except Exception as e:
        logger.error(f"Status check failed for {job_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "Status check failed", "details": str(e)}), 500


@civil_bp.route("/generated/<path:filename>", methods=["GET"])
def download_generated(filename):
    """Download generated files (Excel/PDF reports)"""
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    # allow nested paths like uploads/<name>
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)


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
        
        logger.info(f"Uploading photo: {photo_file.filename}")
        
        # Upload directly to cloud storage with proper error handling
        try:
            result = save_uploaded_file_cloud(photo_file, UPLOADS_DIR, folder="civil_photos")
            
            if not result or not result.get("url"):
                logger.error("Upload returned no URL")
                return jsonify({"success": False, "error": "Upload failed - no URL returned"}), 500
            
            logger.info(f"✅ Photo uploaded successfully: {result['url']}")
            
            return jsonify({
                "success": True,
                "url": result["url"],
                "is_cloud": result.get("is_cloud", False),
                "filename": photo_file.filename
            })
            
        except Exception as upload_error:
            logger.error(f"Upload error: {str(upload_error)}")
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": f"Upload failed: {str(upload_error)}"}), 500
        
    except Exception as e:
        logger.error(f"❌ Civil photo upload failed: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


def save_signature_dataurl(dataurl, uploads_dir, prefix="signature"):
    """
    Upload signature to cloud storage - CLOUD ONLY.
    Returns (saved_filename_or_none, file_path_or_none, public_url) tuple.
    Raises exception if cloud upload fails.
    """
    if not dataurl:
        return None, None, None
    
    # Cloud upload only - no fallback
    cloud_url, is_cloud = upload_base64_to_cloud(dataurl, folder="signatures", prefix=prefix)
    if is_cloud and cloud_url:
        logger.info(f"✅ Signature uploaded to cloud: {cloud_url}")
        return None, None, cloud_url  # No local file
    
    # Should never reach here due to exception in upload_base64_to_cloud
    raise Exception("Cloud storage required but signature upload failed")


@civil_bp.route("/submit-with-urls", methods=["POST"])
def submit_with_urls():
    """Submit form data where photos are already uploaded to cloud."""
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    
    os.makedirs(GENERATED_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(JOBS_DIR, exist_ok=True)
    
    try:
        payload = request.get_json(force=True)
        
        # Validate required fields
        project_name = payload.get("project_name", "").strip()
        location = payload.get("location", "").strip()
        visit_date = payload.get("visit_date", "").strip()
        
        if not project_name:
            return jsonify({"error": "Project name is required"}), 400
        if not location:
            return jsonify({"error": "Location is required"}), 400
        
        # Validate date format
        if visit_date:
            try:
                parsed_date = datetime.strptime(visit_date, '%Y-%m-%d').date()
                if parsed_date > datetime.now().date():
                    return jsonify({"error": "Visit date cannot be in the future"}), 400
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        # Process signatures (data URLs)
        inspector_sig_dataurl = payload.get("inspector_signature", "")
        manager_sig_dataurl = payload.get("manager_signature", "")
        
        inspector_sig_file = None
        manager_sig_file = None
        
        if inspector_sig_dataurl:
            fname, fpath, url = save_signature_dataurl(inspector_sig_dataurl, UPLOADS_DIR, prefix="inspector_sig")
            if url:
                inspector_sig_file = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
        
        if manager_sig_dataurl:
            fname, fpath, url = save_signature_dataurl(manager_sig_dataurl, UPLOADS_DIR, prefix="manager_sig")
            if url:
                manager_sig_file = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
        
        # Extract work items with photo URLs
        work_items = payload.get("work_items", [])
        logger.info(f"📋 Received {len(work_items)} work items")
        processed_items = []
        
        total_photos = 0
        for idx, item_data in enumerate(work_items):
            photo_urls = item_data.get("photo_urls", [])
            logger.info(f"  Work item {idx + 1}: {len(photo_urls)} photo URLs")
            photos_saved = []
            
            for url_idx, url in enumerate(photo_urls):
                logger.info(f"    Photo {url_idx + 1}: {url[:80] if url else 'NO URL'}...")
                photos_saved.append({
                    "saved": None,
                    "path": None,
                    "url": url,
                    "is_cloud": True
                })
            
            total_photos += len(photos_saved)
            processed_items.append({
                "item_number": item_data.get("item_number", ""),
                "description": item_data.get("description", ""),
                "quantity": item_data.get("quantity", ""),
                "material": item_data.get("material", ""),
                "material_qty": item_data.get("material_qty", ""),
                "price": item_data.get("price", ""),
                "labour": item_data.get("labour", ""),
                "photos": photos_saved
            })
        
        logger.info(f"📸 Total photos processed: {total_photos}")
        
        # Create submission in database
        submission_data = {
            "project_name": project_name,
            "location": location,
            "visit_date": visit_date,
            "inspector_name": payload.get("inspector_name", ""),
            "inspector_signature": inspector_sig_file,
            "manager_name": payload.get("manager_name", ""),
            "manager_signature": manager_sig_file,
            "description_of_work": payload.get("description_of_work", ""),
            "floor": payload.get("floor", ""),
            "developer_client": payload.get("developer_client", ""),
            "city_area": payload.get("city_area", ""),
            "estimated_time": payload.get("estimated_time", ""),
            "estimated_completion": payload.get("estimated_completion", ""),
            "work_items": processed_items,
            "base_url": request.host_url.rstrip('/'),
            "created_at": datetime.utcnow().isoformat()
        }
        
        submission = create_submission_db(
            module_type='civil',
            form_data=submission_data,
            site_name=project_name,
            visit_date=visit_date
        )
        sub_id = submission.submission_id
        
        logger.info(f"✅ Civil submission {sub_id} saved with {len(processed_items)} work items")
        
        # Create job in database
        job = create_job_db(submission)
        job_id = job.job_id
        
        logger.info(f"Starting background task for job {job_id}")
        
        # Submit to executor using process_job pattern like HVAC
        if EXECUTOR:
            future = EXECUTOR.submit(
                process_job,
                sub_id,
                job_id,
                current_app.config,
                current_app._get_current_object()
            )
            
            # Add error callback to catch silent failures
            def log_exception(fut):
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"❌ FATAL: Background job {job_id} crashed: {e}")
                    logger.error(traceback.format_exc())
            
            future.add_done_callback(log_exception)
            logger.info(f"✅ Background job {job_id} submitted to executor")
        else:
            logger.error("ThreadPoolExecutor not found in app config")
            return jsonify({'error': 'Background processing not available'}), 500
        
        logger.info(f"🚀 Civil job {job_id} queued for submission {sub_id}")
        
        return jsonify({
            "status": "ok",
            "submission_id": sub_id,
            "job_id": job_id,
            "job_status_url": url_for("civil_bp.status", job_id=job_id, _external=False)
        })
        
    except Exception as e:
        logger.error(f"❌ Civil submit with URLs failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"status": "error", "error": str(e)}), 500


def process_job(sub_id, job_id, config, app):
    """Background worker: Generate BOTH Excel AND PDF reports (like HVAC)"""
    logger.info(f"DEBUG: process_job called with sub_id={sub_id}, job_id={job_id}")
    try:
        with app.app_context():
            GENERATED_DIR = app.config.get('GENERATED_DIR')
            if not os.path.exists(GENERATED_DIR):
                os.makedirs(GENERATED_DIR, exist_ok=True)
            
            logger.info(f"🔄 Processing civil job {job_id}")
            update_job_progress_db(job_id, 10, status='processing')
            
            # Get submission data from database
            submission_data = get_submission_db(sub_id)
            if not submission_data:
                logger.error(f"❌ Submission {sub_id} not found in database")
                fail_job_db(job_id, "Submission not found")
                return
            
            # Use form_data from database
            submission_record = submission_data.get('form_data', {})
            
            # Generate Excel
            logger.info("📊 Generating Excel report...")
            update_job_progress_db(job_id, 30)
            excel_path = create_excel_report(submission_record, output_dir=GENERATED_DIR)
            excel_filename = os.path.basename(excel_path)
            logger.info(f"✅ Excel created: {excel_filename}")
            
            # Upload Excel to Cloudinary (optional)
            update_job_progress_db(job_id, 45)
            base_url = submission_record.get('base_url', '')
            excel_url = f"{base_url}/generated/{excel_filename}"
            
            # Generate PDF
            logger.info("📄 Generating PDF report...")
            update_job_progress_db(job_id, 60)
            pdf_path = create_pdf_report(submission_record, output_dir=GENERATED_DIR)
            pdf_filename = os.path.basename(pdf_path)
            logger.info(f"✅ PDF created: {pdf_filename}")
            pdf_url = f"{base_url}/generated/{pdf_filename}"
            
            # Mark complete
            results = {
                'excel': excel_url,
                'pdf': pdf_url,
                'excel_filename': excel_filename,
                'pdf_filename': pdf_filename
            }
            complete_job_db(job_id, results)
            logger.info(f"✅ Job {job_id} completed successfully")
            
    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {str(e)}")
        logger.error(traceback.format_exc())
        try:
            with app.app_context():
                fail_job_db(job_id, str(e))
        except:
            logger.error("Could not even update job status to failed")