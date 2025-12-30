
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
    """Cleaning form - requires authentication and module access"""
    from flask import redirect, url_for
    from flask_jwt_extended import get_jwt_identity
    
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return render_template('access_denied.html',
                                 module='Cleaning',
                                 message='Your account is inactive. Please contact an administrator.'), 403
        
        if not user.has_module_access('cleaning'):
            return render_template('access_denied.html',
                                 module='Cleaning',
                                 message='You do not have access to this module. Please contact an administrator to grant access.'), 403
        
        return render_template('cleaning_form.html')
    except Exception as e:
        logger.error(f"Error checking module access: {str(e)}")
        # If JWT check fails, redirect to login
        return redirect(url_for('login_page'))


@cleaning_bp.route('/submit', methods=['POST'])
def submit():
    """Handle form submission and start background job."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        # Validate required fields
        required_fields = ['client_name', 'project_name', 'date_of_visit']
        missing = [f for f in required_fields if not data.get(f) or not str(data.get(f)).strip()]
        if missing:
            logger.warning(f"Missing required fields: {missing}")
            return jsonify({'error': f"Missing required fields: {', '.join(missing)}"}), 400
        
        # Validate date
        date_str = data.get('date_of_visit', '')
        if date_str:
            try:
                visit_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if visit_date > datetime.now().date():
                    return jsonify({'error': 'Visit date cannot be in the future'}), 400
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
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
                return jsonify({'error': f'Cloud storage error for tech signature: {str(e)}'}), 500
        
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
                return jsonify({'error': f'Cloud storage error for contact signature: {str(e)}'}), 500
        
        # Save base URL for report generation
        data['base_url'] = request.host_url.rstrip('/')
        data['created_at'] = datetime.utcnow().isoformat()
        
        # Create submission in database
        submission = create_submission_db(
            module_type='cleaning',
            form_data=data,
            site_name=data.get('project_name'),
            visit_date=data.get('date_of_visit')
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
            return jsonify({'error': 'Background task executor not available'}), 500
        
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
    """Background worker: Generate BOTH Excel AND PDF reports (like civil/HVAC)"""
    logger.info(f"DEBUG: process_job called with sub_id={sub_id}, job_id={job_id}")
    try:
        with app.app_context():
            GENERATED_DIR = app.config.get('GENERATED_DIR')
            if not os.path.exists(GENERATED_DIR):
                os.makedirs(GENERATED_DIR, exist_ok=True)
            
            logger.info(f"🔄 Processing cleaning job {job_id}")
            update_job_progress_db(job_id, 10, status='processing')
            
            # Get submission data from database
            submission_data = get_submission_db(sub_id)
            if not submission_data:
                logger.error(f"❌ Submission {sub_id} not found in database")
                fail_job_db(job_id, "Submission not found")
                return
            
            # Use form_data from database
            # Note: submission_data is wrapped as {'form_data': {...}}
            # The form_data contains {'data': {...}, 'submission_id': ..., 'timestamp': ...}
            # So we need to extract the actual data
            form_data_wrapper = submission_data.get('form_data', {})
            
            # Check if data is wrapped in a 'data' key (from submit-with-urls)
            if 'data' in form_data_wrapper:
                submission_record = form_data_wrapper.get('data', {})
                logger.info("📸 Process Job: Extracted data from wrapper")
            else:
                # Direct form_data (from old submit endpoint)
                submission_record = form_data_wrapper
                logger.info("📸 Process Job: Using form_data directly")
            
            # Log photo data for debugging
            photos_in_data = submission_record.get('photos', [])
            logger.info(f"📸 Process Job: Found {len(photos_in_data)} photos in submission_record")
            if photos_in_data:
                for idx, photo in enumerate(photos_in_data[:3]):  # Log first 3
                    if isinstance(photo, dict):
                        logger.info(f"📸 Process Job: Photo {idx + 1}: url={photo.get('url', 'NO URL')[:80]}...")
                    else:
                        logger.info(f"📸 Process Job: Photo {idx + 1}: {str(photo)[:80]}...")
            else:
                logger.warning(f"📸 Process Job: No photos found! Keys in submission_record: {list(submission_record.keys())}")
            
            # Generate Excel
            logger.info("📊 Generating Excel report...")
            update_job_progress_db(job_id, 30)
            excel_path = create_excel_report(submission_record, output_dir=GENERATED_DIR)
            excel_filename = os.path.basename(excel_path)
            logger.info(f"✅ Excel created: {excel_filename}")
            # Only use local Excel URL, skip Cloudinary upload
            base_url = submission_record.get('base_url', '')
            excel_url = f"{base_url}/cleaning/generated/{excel_filename}"

            # Generate PDF
            logger.info("📄 Generating PDF report...")
            update_job_progress_db(job_id, 60)
            pdf_path = create_pdf_report(submission_record, output_dir=GENERATED_DIR)
            pdf_filename = os.path.basename(pdf_path)
            logger.info(f"✅ PDF created: {pdf_filename}")
            pdf_url = f"{base_url}/cleaning/generated/{pdf_filename}"

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