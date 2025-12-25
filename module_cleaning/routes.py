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
from app.models import db
from app.services.cloudinary_service import upload_local_file

logger = logging.getLogger(__name__)

cleaning_bp = Blueprint('cleaning', __name__, url_prefix='/cleaning', template_folder='templates')

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
def form():
    """Render the cleaning assessment form."""
    return render_template('cleaning_form.html')


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


@cleaning_bp.route('/job-status/<job_id>', methods=['GET'])
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
    logger.info(f"🔴 DEBUG: process_job called for {job_id}")
    with app.app_context():
        try:
            GENERATED_DIR = config.get('GENERATED_DIR')
            
            logger.info(f"🔄 Processing job {job_id}")
            
            # Update progress: Starting
            update_job_progress_db(job_id, 10, status='processing')
            
            # Get submission data from database
            submission_data_obj = get_submission_db(sub_id)
            if not submission_data_obj:
                fail_job_db(job_id, "Submission not found")
                return
            
            # Extract form_data
            submission_data = submission_data_obj.get('form_data', {})
            
            # Generate Excel
            logger.info("📊 Generating Excel report...")
            update_job_progress_db(job_id, 30)
            excel_path = create_excel_report(submission_data, GENERATED_DIR)
            excel_filename = os.path.basename(excel_path)
            logger.info(f"✅ Excel created: {excel_filename}")
            
            # Upload Excel to Cloudinary
            update_job_progress_db(job_id, 45)
            excel_url = upload_local_file(excel_path, f"cleaning_excel_{sub_id}")
            if not excel_url:
                base_url = submission_data.get('base_url', '')
                excel_url = f"{base_url}/generated/{excel_filename}"
                logger.warning("⚠️ Excel cloud upload failed, using local URL")
            else:
                logger.info(f"✅ Excel uploaded to cloud: {excel_url}")
            
            # Generate PDF
            logger.info("📄 Generating PDF report...")
            update_job_progress_db(job_id, 60)
            pdf_path = create_pdf_report(submission_data, GENERATED_DIR)
            pdf_filename = os.path.basename(pdf_path)
            logger.info(f"✅ PDF created: {pdf_filename}")
            
            # Upload PDF to Cloudinary
            update_job_progress_db(job_id, 80)
            pdf_url = upload_local_file(pdf_path, f"cleaning_pdf_{sub_id}")
            if not pdf_url:
                base_url = submission_data.get('base_url', '')
                pdf_url = f"{base_url}/generated/{pdf_filename}"
                logger.warning("⚠️ PDF cloud upload failed, using local URL")
            else:
                logger.info(f"✅ PDF uploaded to cloud: {pdf_url}")
            
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
            fail_job_db(job_id, str(e))


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
            "filename": result.get("filename")
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
        
        for idx, url in enumerate(photo_urls):
            if url:
                saved_photos.append({
                    'saved': None,
                    'path': None,
                    'url': url,
                    'index': idx,
                    'is_cloud': True
                })
        
        data['photos'] = saved_photos
        
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
            executor.submit(process_job, submission_id, job_id, current_app.config, current_app._get_current_object(), current_app._get_current_object())
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