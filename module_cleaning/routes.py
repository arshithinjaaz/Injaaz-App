import os
import json
import logging
from flask import Blueprint, render_template, request, jsonify, current_app, send_file, redirect, url_for
from common.utils import random_id, save_uploaded_file, mark_job_started, update_job_progress, mark_job_done

logger = logging.getLogger(__name__)

cleaning_bp = Blueprint('cleaning', __name__, url_prefix='/cleaning', template_folder='templates')

try:
    from .cleaning_generators import create_excel_report, create_pdf_report
except Exception as e:
    logger.warning(f"Could not import cleaning_generators: {e}")
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
        
        # Generate unique IDs
        submission_id = random_id('sub')
        job_id = random_id('job')
        
        # Save uploaded photos - FIXED: save_uploaded_file() takes 2 args not 3
        photos = data.get('photos', [])
        saved_photos = []
        
        for idx, photo_base64 in enumerate(photos):
            if photo_base64 and photo_base64.startswith('data:image'):
                # FIXED: Pass only base64 data and uploads dir (2 args)
                photo_path = save_uploaded_file(
                    photo_base64,
                    current_app.config['UPLOADS_DIR']
                )
                if photo_path:
                    saved_photos.append({'path': photo_path, 'index': idx})
        
        data['photos'] = saved_photos
        
        # Save signatures - FIXED: Only 2 arguments
        tech_signature = data.get('tech_signature', '')
        contact_signature = data.get('contact_signature', '')
        
        if tech_signature and tech_signature.startswith('data:image'):
            tech_sig_path = save_uploaded_file(
                tech_signature,
                current_app.config['UPLOADS_DIR']
            )
            data['tech_signature'] = {'path': tech_sig_path} if tech_sig_path else ''
        
        if contact_signature and contact_signature.startswith('data:image'):
            contact_sig_path = save_uploaded_file(
                contact_signature,
                current_app.config['UPLOADS_DIR']
            )
            data['contact_signature'] = {'path': contact_sig_path} if contact_sig_path else ''
        
        # Save base URL for report generation
        data['base_url'] = request.host_url.rstrip('/')
        data['submission_id'] = submission_id
        data['job_id'] = job_id
        
        # Save submission data
        submissions_dir = current_app.config['GENERATED_DIR']
        submission_path = os.path.join(submissions_dir, f"{submission_id}.json")
        
        with open(submission_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Submission saved: {submission_path}")
        
        # Submit background job
        executor = current_app.config.get('EXECUTOR')
        if executor:
            executor.submit(_generate_reports_task, submission_id, job_id)
            logger.info(f"Job {job_id} submitted to executor")
        else:
            return jsonify({'error': 'Background task executor not available'}), 500
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'submission_id': submission_id
        }), 202
        
    except Exception as e:
        logger.error(f"Submission error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@cleaning_bp.route('/job-status/<job_id>', methods=['GET'])
def job_status(job_id):
    """Check the status of a background job."""
    try:
        jobs_dir = current_app.config['JOBS_DIR']
        job_path = os.path.join(jobs_dir, f"{job_id}.json")
        
        if not os.path.exists(job_path):
            return jsonify({'error': 'Job not found'}), 404
        
        with open(job_path, 'r') as f:
            job_data = json.load(f)
        
        return jsonify(job_data)
        
    except Exception as e:
        logger.error(f"Job status error: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _generate_reports_task(submission_id, job_id):
    """Background task to generate Excel and PDF reports."""
    from flask import current_app
    
    try:
        mark_job_started(job_id, current_app.config['JOBS_DIR'])
        update_job_progress(job_id, 10, "Loading submission data...", current_app.config['JOBS_DIR'])
        
        # Load submission data
        submissions_dir = current_app.config['GENERATED_DIR']
        submission_path = os.path.join(submissions_dir, f"{submission_id}.json")
        
        with open(submission_path, 'r') as f:
            data = json.load(f)
        
        update_job_progress(job_id, 30, "Generating Excel report...", current_app.config['JOBS_DIR'])
        
        # Generate Excel report
        excel_path = create_excel_report(data, current_app.config['GENERATED_DIR'])
        excel_filename = os.path.basename(excel_path)
        
        update_job_progress(job_id, 60, "Generating PDF report...", current_app.config['JOBS_DIR'])
        
        # Generate PDF report
        pdf_path = create_pdf_report(data, current_app.config['GENERATED_DIR'])
        pdf_filename = os.path.basename(pdf_path)
        
        update_job_progress(job_id, 90, "Finalizing...", current_app.config['JOBS_DIR'])
        
        # Build download URLs
        base_url = data.get('base_url', '')
        
        results = {
            'excel': f"{base_url}/generated/{excel_filename}",
            'pdf': f"{base_url}/generated/{pdf_filename}"
        }
        
        mark_job_done(job_id, results, current_app.config['JOBS_DIR'])
        logger.info(f"✅ Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {str(e)}")
        mark_job_done(job_id, None, current_app.config['JOBS_DIR'], error=str(e))