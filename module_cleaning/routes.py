
import os
import json
import logging
import traceback
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app, send_file, redirect, url_for
from common.utils import (
    random_id, 
    save_uploaded_file,
    save_uploaded_file_cloud,
    upload_base64_to_cloud
)
from common.db_utils import (
    create_submission_db,
    create_job_db,
    update_job_progress_db,
    complete_job_db,
    fail_job_db,
    get_job_status_db,
    get_submission_db
)
from app.models import db, User
from app.middleware import token_required
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.services.cloudinary_service import upload_local_file

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

cleaning_bp = Blueprint('cleaning', __name__, url_prefix='/cleaning', template_folder='templates')

@cleaning_bp.route('/generated/<path:filename>')
def download_generated_cleaning(filename):
    """Serve generated files as download attachments for cleaning module."""
    GENERATED_DIR = current_app.config['GENERATED_DIR']
    safe_path = os.path.join(GENERATED_DIR, filename)
    if not os.path.exists(safe_path):
        logger.warning(f"File not found: {filename}")
        return "File not found", 404
    # Serve as attachment for download
    return send_file(safe_path, as_attachment=True, download_name=filename)


@cleaning_bp.route("/download/<job_id>/<file_type>", methods=["GET"])
def download_file(job_id, file_type):
    """
    Download proxy route that fetches files from Cloudinary or local storage
    and serves them with proper download headers for auto-download.
    
    Args:
        job_id: Job ID to get file URLs from
        file_type: 'excel' or 'pdf'
    """
    GENERATED_DIR = current_app.config['GENERATED_DIR']
    
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
            filename = results.get('excel_filename') or 'cleaning_report.xlsx'
        elif file_type == 'pdf':
            file_url = results.get('pdf') or results.get('pdf_url')
            filename = results.get('pdf_filename') or 'cleaning_report.pdf'
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
            
            return send_file(local_path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        logger.error(traceback.format_exc())
        return error_response("Download failed", status_code=500, error_code='INTERNAL_ERROR')

try:
    from .cleaning_generators import create_excel_report, create_pdf_report
    logger.info("✅ Successfully imported cleaning_generators")
except Exception as e:
    logger.error(f"❌ Failed to import generators: {e}")
    def create_excel_report(data, output_dir):
        logger.error("Placeholder: Excel generator not implemented")
        raise NotImplementedError("Excel generator not available")
    
    def create_pdf_report(data, output_dir):
        logger.error("Placeholder: PDF generator not implemented")
        raise NotImplementedError("PDF generator not available")


@cleaning_bp.route('/')
def index():
    """Cleaning module index page"""
    return redirect(url_for('cleaning.form'))


@cleaning_bp.route('/form', methods=['GET'])
@jwt_required()
def form():
    """Cleaning form - requires authentication and module access. Supports editing existing submissions."""
    from flask import redirect, url_for
    from flask_jwt_extended import get_jwt_identity
    from app.models import Submission
    
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return render_template('access_denied.html',
                                 module='Cleaning',
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
                                     module='Cleaning',
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
                                     module='Cleaning',
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
            if not user.has_module_access('cleaning'):
                return render_template('access_denied.html',
                                     module='Cleaning',
                                     message='You do not have access to this module. Please contact an administrator to grant access.'), 403
        
        return render_template('cleaning_form.html', submission_data=submission_data, is_edit_mode=is_edit_mode)
    except Exception as e:
        logger.error(f"Error checking module access: {str(e)}")
        # If JWT check fails, redirect to login
        return redirect(url_for('login_page'))


@cleaning_bp.route('/submit', methods=['POST'])
@rate_limit_if_available('10 per minute')  # Limit form submissions
def submit():
    """Handle form submission and start background job."""
    try:
        data = request.get_json()
        
        if not data:
            return error_response('No data received', status_code=400, error_code='VALIDATION_ERROR')
        
        # Validate required fields
        required_fields = ['client_name', 'project_name', 'date_of_visit']
        missing = [f for f in required_fields if not data.get(f) or not str(data.get(f)).strip()]
        if missing:
            logger.warning(f"Missing required fields: {missing}")
            return error_response(f"Missing required fields: {', '.join(missing)}", status_code=400, error_code='VALIDATION_ERROR')
        
        # Validate date
        date_str = data.get('date_of_visit', '')
        if date_str:
            try:
                visit_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if visit_date > datetime.now().date():
                    return error_response('Visit date cannot be in the future', status_code=400, error_code='VALIDATION_ERROR')
            except ValueError:
                return error_response('Invalid date format. Use YYYY-MM-DD', status_code=400, error_code='VALIDATION_ERROR')
        
        GENERATED_DIR = current_app.config['GENERATED_DIR']
        UPLOADS_DIR = current_app.config['UPLOADS_DIR']
        JOBS_DIR = current_app.config['JOBS_DIR']
        
        # Ensure directories exist
        os.makedirs(GENERATED_DIR, exist_ok=True)
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        os.makedirs(JOBS_DIR, exist_ok=True)
        
        # Generate unique IDs
        submission_id = random_id('sub')
        job_id = random_id('job')
        
        # Save uploaded photos (assuming base64 data from frontend)
        photos = data.get('photos', [])
        saved_photos = []
        
        for idx, photo_base64 in enumerate(photos):
            if photo_base64 and photo_base64.startswith('data:image'):
                try:
                    # Cloud upload only - no fallback
                    cloud_url, is_cloud = upload_base64_to_cloud(
                        photo_base64, 
                        folder="cleaning_photos", 
                        prefix=f"photo_{idx}"
                    )
                    
                    saved_photos.append({
                        'saved': None,
                        'path': None,
                        'url': cloud_url,
                        'index': idx,
                        'is_cloud': True
                    })
                except Exception as e:
                    logger.error(f"Failed to upload photo {idx}: {e}")
                    return jsonify({'error': f'Cloud storage error for photo {idx}: {str(e)}'}), 500
        
        data['photos'] = saved_photos
        
        # Save signatures (base64 data)
        tech_signature = data.get('tech_signature', '')
        contact_signature = data.get('contact_signature', '')
        
        if tech_signature and tech_signature.startswith('data:image'):
            try:
                # Cloud upload only - no fallback
                cloud_url, is_cloud = upload_base64_to_cloud(
                    tech_signature, 
                    folder="signatures", 
                    prefix="tech_sig"
                )
                
                data['tech_signature'] = {
                    'saved': None,
                    'path': None,
                    'url': cloud_url,
                    'is_cloud': True
                }
            except Exception as e:
                logger.error(f"Failed to upload tech signature: {e}")
                return error_response('Cloud storage error for tech signature', status_code=500, error_code='STORAGE_ERROR')
        
        if contact_signature and contact_signature.startswith('data:image'):
            try:
                # Cloud upload only - no fallback
                cloud_url, is_cloud = upload_base64_to_cloud(
                    contact_signature, 
                    folder="signatures", 
                    prefix="contact_sig"
                )
                
                data['contact_signature'] = {
                    'saved': None,
                    'path': None,
                    'url': cloud_url,
                    'is_cloud': True
                }
            except Exception as e:
                logger.error(f"Failed to upload contact signature: {e}")
                return error_response('Cloud storage error for contact signature', status_code=500, error_code='STORAGE_ERROR')
        
        # Save base URL for report generation
        data['base_url'] = request.host_url.rstrip('/')
        data['created_at'] = datetime.utcnow().isoformat()
        
        # Get user_id from JWT token if available
        user_id = None
        try:
            from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
            try:
                verify_jwt_in_request(optional=True)
                user_id = get_jwt_identity()
                if user_id:
                    logger.info(f"✅ Submission will be associated with user_id: {user_id}")
            except Exception:
                pass  # No token or invalid token - submission will be anonymous
        except Exception:
            pass  # JWT not available
        
        # Create submission in database
        submission = create_submission_db(
            module_type='cleaning',
            form_data=data,
            site_name=data.get('project_name'),
            visit_date=data.get('date_of_visit'),
            user_id=user_id
        )
        submission_id = submission.submission_id
        
        # Add IDs to data for background task
        data['submission_id'] = submission_id
        
        logger.info(f"Submission saved to database: {submission_id}")
        
        # Create job in database
        job = create_job_db(submission)
        job_id = job.job_id
        data['job_id'] = job_id
        
        # Submit background job with submission_id
        executor = current_app.config.get('EXECUTOR')
        if executor:
            executor.submit(
                process_job, 
                submission_id, 
                job_id, 
                current_app.config,
                current_app._get_current_object()
            )
            logger.info(f"Job {job_id} submitted to executor")
        else:
            logger.error("ThreadPoolExecutor not found in app config")
            return error_response('Background task executor not available', status_code=500, error_code='SERVICE_UNAVAILABLE')
        
        return jsonify({
            'status': 'queued',
            'job_id': job_id,
            'submission_id': submission_id
        }), 202
        
    except Exception as e:
        logger.error(f"Submission error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@cleaning_bp.route('/status/<job_id>', methods=['GET'])
def job_status(job_id):
    """Check the status of a background job."""
    try:
        job_data = get_job_status_db(job_id)
        
        if not job_data:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(job_data)
        
    except Exception as e:
        logger.error(f"Job status error: {str(e)}")
        return jsonify({'error': str(e)}), 500


def process_job(sub_id, job_id, config, app):
    """Background worker: Generate BOTH Excel AND PDF reports"""
    logger.debug(f"process_job called with sub_id={sub_id}, job_id={job_id}")
    from common.module_base import process_report_job
    from .cleaning_generators import create_excel_report, create_pdf_report
    
    process_report_job(
        sub_id=sub_id,
        job_id=job_id,
        app=app,
        module_name='cleaning',
        create_excel_report=create_excel_report,
        create_pdf_report=create_pdf_report
    )


# ---------- Progressive Upload Endpoints ----------

@cleaning_bp.route("/upload-photo", methods=["POST"])
def upload_photo():
    """Upload a single photo immediately to cloud storage."""
    try:
        UPLOADS_DIR = current_app.config['UPLOADS_DIR']
        
        if 'photo' not in request.files:
            return jsonify({"success": False, "error": "No photo file provided"}), 400
        
        photo_file = request.files['photo']
        if photo_file.filename == '':
            return jsonify({"success": False, "error": "Empty filename"}), 400
        
        result = save_uploaded_file_cloud(photo_file, UPLOADS_DIR, folder="cleaning_photos")
        
        if not result.get("url"):
            return jsonify({"success": False, "error": "Cloud upload failed"}), 500
        
        logger.info(f"✅ Cleaning photo uploaded to cloud: {result['url']}")
        
        return jsonify({
            "success": True,
            "url": result["url"],
            "filename": result.get("filename"),
            "is_cloud": result.get("is_cloud", True)
        })
        
    except Exception as e:
        logger.error(f"❌ Cleaning photo upload failed: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@cleaning_bp.route("/submit-with-urls", methods=["POST"])
def submit_with_urls():
    """Submit form data where photos are already uploaded to cloud."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        GENERATED_DIR = current_app.config['GENERATED_DIR']
        UPLOADS_DIR = current_app.config['UPLOADS_DIR']
        JOBS_DIR = current_app.config['JOBS_DIR']
        
        os.makedirs(GENERATED_DIR, exist_ok=True)
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        os.makedirs(JOBS_DIR, exist_ok=True)
        
        submission_id = random_id('sub')
        job_id = random_id('job')
        
        # Process photos - convert URLs to expected format
        photo_urls = data.get('photo_urls', [])
        saved_photos = []
        
        logger.info(f"📸 Received {len(photo_urls)} photo URLs")
        
        for idx, url in enumerate(photo_urls):
            if url:
                logger.info(f"  Photo {idx + 1}: {url[:80]}...")
                saved_photos.append({
                    'saved': None,
                    'path': None,
                    'url': url,
                    'index': idx,
                    'is_cloud': True
                })
        
        data['photos'] = saved_photos
        logger.info(f"📸 Total photos processed: {len(saved_photos)}")
        
        # Save signatures (base64 data) to cloud
        tech_signature = data.get('tech_signature', '')
        contact_signature = data.get('contact_signature', '')
        
        if tech_signature:
            try:
                cloud_url, is_cloud = upload_base64_to_cloud(tech_signature, folder="signatures", prefix="tech_sig")
                data['tech_signature_url'] = cloud_url
            except Exception as e:
                logger.error(f"Failed to upload tech signature: {e}")
        
        if contact_signature:
            try:
                cloud_url, is_cloud = upload_base64_to_cloud(contact_signature, folder="signatures", prefix="contact_sig")
                data['contact_signature_url'] = cloud_url
            except Exception as e:
                logger.error(f"Failed to upload contact signature: {e}")
        
        # Save submission
        subs_dir = os.path.join(GENERATED_DIR, 'submissions')
        os.makedirs(subs_dir, exist_ok=True)
        
        submission_data = {
            'submission_id': submission_id,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
            'base_url': request.host_url.rstrip('/')
        }
        
        # Save submission to database
        submission_db = create_submission_db(
            module_type='cleaning',
            form_data=submission_data,
            site_name=data.get('project_name', 'Cleaning Assessment'),
            visit_date=data.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
        )
        submission_id = submission_db.submission_id
        
        logger.info(f"✅ Cleaning submission {submission_id} saved to database with {len(saved_photos)} photos")
        
        # Create job in database
        job = create_job_db(submission_db)
        job_id = job.job_id
        
        # Submit background task
        executor = current_app.config.get('EXECUTOR')
        if executor:
            future = executor.submit(
                process_job,
                submission_id,
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
        
        logger.info(f"🚀 Cleaning job {job_id} queued for submission {submission_id}")
        
        return jsonify({
            'status': 'queued',
            'job_id': job_id,
            'submission_id': submission_id,
            'job_status_url': url_for('cleaning.job_status', job_id=job_id, _external=False)
        })
        
    except Exception as e:
        logger.error(f"❌ Cleaning submit with URLs failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500