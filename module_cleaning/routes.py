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
    upload_base64_to_cloud,
    mark_job_started, 
    read_job_state, 
    update_job_progress, 
    mark_job_done
)

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
        data['submission_id'] = submission_id
        data['job_id'] = job_id
        data['created_at'] = datetime.utcnow().isoformat()
        
        # Save submission data in submissions folder
        submissions_dir = os.path.join(GENERATED_DIR, 'submissions')
        os.makedirs(submissions_dir, exist_ok=True)
        submission_path = os.path.join(submissions_dir, f"{submission_id}.json")
        
        with open(submission_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Submission saved: {submission_path}")
        
        # Create job record - FIXED: Use correct parameter order (JOBS_DIR first)
        mark_job_started(JOBS_DIR, job_id, meta={
            "submission_id": submission_id, 
            "module": "cleaning", 
            "created_at": datetime.utcnow().isoformat()
        })
        
        # Submit background job
        executor = current_app.config.get('EXECUTOR')
        if executor:
            executor.submit(
                process_job, 
                data, 
                job_id, 
                current_app.config
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
        JOBS_DIR = current_app.config['JOBS_DIR']
        # FIXED: Use correct parameter order (JOBS_DIR first)
        state = read_job_state(JOBS_DIR, job_id)
        
        if not state:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(state)
        
    except Exception as e:
        logger.error(f"Job status error: {str(e)}")
        return jsonify({'error': str(e)}), 500


def process_job(submission_data, job_id, config):
    """Background worker: Generate BOTH Excel AND PDF reports"""
    try:
        GENERATED_DIR = config.get('GENERATED_DIR')
        JOBS_DIR = config.get('JOBS_DIR')
        
        logger.info(f"🔄 Processing job {job_id}")
        
        # Update progress: Starting - FIXED: Use correct parameter order
        update_job_progress(JOBS_DIR, job_id, 10)
        
        # Generate Excel
        logger.info("📊 Generating Excel report...")
        update_job_progress(JOBS_DIR, job_id, 30)
        excel_path = create_excel_report(submission_data, GENERATED_DIR)
        excel_filename = os.path.basename(excel_path)
        logger.info(f"✅ Excel created: {excel_filename}")
        
        # Generate PDF
        logger.info("📄 Generating PDF report...")
        update_job_progress(JOBS_DIR, job_id, 60)
        pdf_path = create_pdf_report(submission_data, GENERATED_DIR)
        pdf_filename = os.path.basename(pdf_path)
        logger.info(f"✅ PDF created: {pdf_filename}")
        
        # Build URLs using base_url from submission
        base_url = submission_data.get('base_url', '')
        excel_url = f"{base_url}/generated/{excel_filename}"
        pdf_url = f"{base_url}/generated/{pdf_filename}"
        
        # Mark complete - FIXED: Use correct parameter order
        update_job_progress(JOBS_DIR, job_id, 100)
        
        results = {
            'excel': excel_url,
            'pdf': pdf_url
        }
        
        mark_job_done(JOBS_DIR, job_id, results)
        logger.info(f"✅ Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Mark as failed
        state = read_job_state(JOBS_DIR, job_id) or {}
        state.update({
            "state": "failed",
            "progress": 0,
            "results": {"error": str(e)},
            "completed_at": datetime.utcnow().isoformat()
        })
        
        from common.utils import write_job_state
        write_job_state(JOBS_DIR, job_id, state)