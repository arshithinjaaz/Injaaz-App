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
from common.error_responses import error_response, success_response

# Rate limiting helper
def get_limiter():
    """Get rate limiter from current app"""
    try:
        return current_app.limiter
    except (AttributeError, RuntimeError):
        return None

def rate_limit_if_available(limit_str):
    """Decorator to apply rate limiting if limiter is available"""
    def decorator(f):
        limiter = get_limiter()
        if limiter:
            return limiter.limit(limit_str)(f)
        return f
    return decorator

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
    """Civil form - requires authentication and module access. Supports editing existing submissions."""
    from flask import redirect, url_for, request
    from flask_jwt_extended import get_jwt_identity
    from app.models import Submission
    
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return render_template('access_denied.html',
                                 module='Civil Works',
                                 message='Your account is inactive. Please contact an administrator.'), 403
        
        # Allow admins, supervisors, and managers to edit submissions even if they don't have module access
        edit_submission_id = request.args.get('edit')
        submission_data = None
        is_edit_mode = False
        
        if edit_submission_id:
            # Check if user can edit (admin, or supervisor/manager of this submission)
            submission = Submission.query.filter_by(submission_id=edit_submission_id).first()
            if not submission:
                return render_template('access_denied.html',
                                     module='Civil Works',
                                     message='Submission not found.'), 404
            
            # Allow editing if: admin, or supervisor/manager assigned to this submission
            can_edit = False
            if user.role == 'admin':
                can_edit = True
            elif hasattr(submission, 'supervisor_id') and submission.supervisor_id == user.id:
                can_edit = True
            elif hasattr(submission, 'manager_id') and submission.manager_id == user.id:
                can_edit = True
            
            if not can_edit:
                return render_template('access_denied.html',
                                     module='Civil Works',
                                     message='You do not have permission to edit this submission.'), 403
            
            # Load submission data for editing
            submission_dict = submission.to_dict()
            # Parse form_data if it's a string
            form_data = submission_dict.get('form_data', {})
            if isinstance(form_data, str):
                try:
                    form_data = json.loads(form_data)
                except:
                    form_data = {}
            
            submission_data = {
                'submission_id': submission.submission_id,
                'site_name': submission.site_name or '',
                'visit_date': submission.visit_date.isoformat() if submission.visit_date else '',
                'form_data': form_data,
                'is_edit_mode': True
            }
            is_edit_mode = True
        else:
            # Normal form access - check module access
            if not user.has_module_access('civil'):
                return render_template('access_denied.html',
                                     module='Civil Works',
                                     message='You do not have access to this module. Please contact an administrator to grant access.'), 403
        
        # Pass designation info so the template can adjust signature visibility
        user_designation = user.designation if hasattr(user, 'designation') else None
        is_supervisor_edit = is_edit_mode and user_designation == 'supervisor'
        
        return render_template(
            'civil_form.html',
            submission_data=submission_data,
            is_edit_mode=is_edit_mode,
            user_designation=user_designation,
            is_supervisor_edit=is_supervisor_edit
        )
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
@rate_limit_if_available('10 per minute')  # Limit form submissions
def submit():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    
    # Validate required fields
    fields = dict(request.form)
    required_fields = ['project_name', 'location', 'date']
    missing = [f for f in required_fields if not fields.get(f) or not fields.get(f).strip()]
    if missing:
        logger.warning(f"Missing required fields: {missing}")
        return error_response(f"Missing required fields: {', '.join(missing)}", status_code=400, error_code='VALIDATION_ERROR')
    
    # Validate date format
    try:
        from datetime import datetime
        visit_date = datetime.strptime(fields.get('date'), '%Y-%m-%d').date()
        if visit_date > datetime.now().date():
            return error_response("Visit date cannot be in the future", status_code=400, error_code='VALIDATION_ERROR')
    except ValueError:
        return error_response("Invalid date format. Use YYYY-MM-DD", status_code=400, error_code='VALIDATION_ERROR')
    
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
                return error_response("File storage error", status_code=500, error_code='STORAGE_ERROR')
            except ValueError as e:
                logger.error(f"Invalid file data: {e}")
                return error_response("Invalid file data", status_code=400, error_code='VALIDATION_ERROR')
            except Exception as e:
                logger.error(f"Unexpected error uploading file: {e}")
                return error_response("Cloud storage error", status_code=500, error_code='STORAGE_ERROR')
    # Create submission in database
    submission_data = {
        "fields": fields,
        "files": saved_files,
        "base_url": request.host_url.rstrip('/')
    }
    
    # Get user_id from JWT token if available
    user_id = None
    try:
        from flask_jwt_extended import verify_jwt_in_request
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            if user_id:
                logger.info(f"✅ Submission will be associated with user_id: {user_id}")
        except Exception:
            pass  # No token or invalid token - submission will be anonymous
    except Exception:
        pass  # JWT not available
    
    submission = create_submission_db(
        module_type='civil',
        form_data=submission_data,
        site_name=fields.get('project_name'),
        visit_date=fields.get('date'),
        user_id=user_id
    )
    sub_id = submission.submission_id

    # Create job in database
    job = create_job_db(submission)
    job_id = job.job_id

    def task_generate_reports(job_id_local, sub_id_local, base_url, app):
        logger.debug(f"task_generate_reports called for {job_id_local}")
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


@civil_bp.route("/download/<job_id>/<file_type>", methods=["GET"])
def download_file(job_id, file_type):
    """
    Download proxy route that fetches files from Cloudinary or local storage
    and serves them with proper download headers for auto-download.
    
    Args:
        job_id: Job ID to get file URLs from
        file_type: 'excel' or 'pdf'
    """
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    
    try:
        import requests
        from io import BytesIO
        
        # Get job data from database
        job_data = get_job_status_db(job_id)
        if not job_data:
            logger.error(f"Job not found: {job_id}")
            return jsonify({"error": "Job not found"}), 404
        
        # Extract results
        results = {}
        if isinstance(job_data, dict):
            results = job_data.get('results', {}) or job_data.get('result_data', {}) or job_data.get('results_data', {})
            if isinstance(results, str):
                try:
                    results = json.loads(results)
                except:
                    logger.warning(f"Failed to parse results as JSON")
                    results = {}
        
        if not results:
            logger.error(f"Job results not found for {job_id}")
            return error_response("Job results not found", status_code=404, error_code='NOT_FOUND')
        
        # Get file URL and filename based on file_type
        if file_type == 'excel':
            file_url = results.get('excel') or results.get('excel_url')
            filename = results.get('excel_filename') or 'civil_report.xlsx'
        elif file_type == 'pdf':
            file_url = results.get('pdf') or results.get('pdf_url')
            filename = results.get('pdf_filename') or 'civil_report.pdf'
        else:
            return error_response("Invalid file type", status_code=400, error_code='VALIDATION_ERROR')
        
        if not file_url:
            return error_response(f"{file_type.upper()} file URL not found", status_code=404, error_code='NOT_FOUND')
        
        # Check if it's a Cloudinary URL
        if 'cloudinary.com' in file_url:
            try:
                clean_url = file_url.split('?')[0]
                response = requests.get(clean_url, timeout=60, stream=True)
                response.raise_for_status()
                
                file_content = response.content
                file_data = BytesIO(file_content)
                file_data.seek(0)
                
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if file_type == 'excel' else 'application/pdf'
                
                if len(file_content) == 0:
                    logger.error(f"Empty file content received from Cloudinary")
                    return error_response("File content is empty", status_code=500, error_code='STORAGE_ERROR')
                
                from flask import send_file
                return send_file(
                    file_data,
                    mimetype=mimetype,
                    as_attachment=True,
                    download_name=filename
                )
            except Exception as e:
                logger.error(f"Error fetching from Cloudinary: {str(e)}")
                logger.error(traceback.format_exc())
                return error_response("Failed to fetch file from Cloudinary", status_code=500, error_code='STORAGE_ERROR')
        else:
            # Local URL
            local_filename = file_url.lstrip('/').replace('generated/', '')
            local_path = os.path.join(GENERATED_DIR, local_filename)
            
            if not os.path.exists(local_path):
                return error_response("File not found locally", status_code=404, error_code='NOT_FOUND')
            
            from flask import send_file
            return send_file(local_path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        logger.error(traceback.format_exc())
        return error_response("Download failed", status_code=500, error_code='INTERNAL_ERROR')


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
                return error_response("Upload failed - no URL returned", status_code=500, error_code='STORAGE_ERROR')
            
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
    """Background worker: Generate BOTH Excel AND PDF reports"""
    logger.debug(f"process_job called with sub_id={sub_id}, job_id={job_id}")
    from common.module_base import process_report_job
    from .civil_generators import create_excel_report, create_pdf_report
    
    process_report_job(
        sub_id=sub_id,
        job_id=job_id,
        app=app,
        module_name='civil',
        create_excel_report=create_excel_report,
        create_pdf_report=create_pdf_report
    )