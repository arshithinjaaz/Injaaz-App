"""
Base module handler to reduce code duplication across modules
"""
import os
import logging
import traceback
from common.db_utils import (
    get_submission_db,
    update_job_progress_db,
    complete_job_db,
    fail_job_db
)
from app.services.cloudinary_service import upload_local_file

logger = logging.getLogger(__name__)


def process_report_job(sub_id, job_id, app, module_name, create_excel_report, create_pdf_report):
    """
    Common job processing logic for all modules
    
    Args:
        sub_id: Submission ID
        job_id: Job ID
        app: Flask application instance
        module_name: Module name ('hvac', 'civil', 'cleaning')
        create_excel_report: Function to create Excel report
        create_pdf_report: Function to create PDF report
    
    Returns:
        None (updates job status in database)
    """
    try:
        with app.app_context():
            GENERATED_DIR = app.config.get('GENERATED_DIR')
            if not os.path.exists(GENERATED_DIR):
                os.makedirs(GENERATED_DIR, exist_ok=True)
            
            logger.info(f"🔄 Processing {module_name} job {job_id}")
            update_job_progress_db(job_id, 10, status='processing')
            
            # Get submission data from database
            submission_data = get_submission_db(sub_id)
            if not submission_data:
                logger.error(f"❌ Submission {sub_id} not found in database")
                fail_job_db(job_id, "Submission not found")
                return
            
            # Extract form data (handle different data structures)
            form_data_wrapper = submission_data.get('form_data', {})
            if 'data' in form_data_wrapper:
                submission_record = form_data_wrapper.get('data', {})
            else:
                submission_record = form_data_wrapper
            
            # Merge reviewer comments and signatures from submission model fields into form_data if not already present
            # Query the submission directly to get comments and signatures (they're not in to_dict())
            try:
                from app.models import Submission
                submission = Submission.query.filter_by(submission_id=sub_id).first()
                if submission:
                    # Add comments to submission_record if not already present in form_data
                    if hasattr(submission, 'operations_manager_comments') and submission.operations_manager_comments:
                        if not submission_record.get('operations_manager_comments'):
                            submission_record['operations_manager_comments'] = submission.operations_manager_comments
                            logger.info(f"✅ Added Operations Manager comments from model field to submission_record")
                    
                    if hasattr(submission, 'business_dev_comments') and submission.business_dev_comments:
                        if not submission_record.get('business_dev_comments'):
                            submission_record['business_dev_comments'] = submission.business_dev_comments
                    
                    if hasattr(submission, 'procurement_comments') and submission.procurement_comments:
                        if not submission_record.get('procurement_comments'):
                            submission_record['procurement_comments'] = submission.procurement_comments
                    
                    if hasattr(submission, 'general_manager_comments') and submission.general_manager_comments:
                        if not submission_record.get('general_manager_comments'):
                            submission_record['general_manager_comments'] = submission.general_manager_comments
                    
                    # Add signatures from form_data if available (signatures are stored in form_data, not model fields)
                    # Check both top-level form_data and nested data structure
                    form_data_dict = submission.form_data if submission.form_data else {}
                    if isinstance(form_data_dict, dict):
                        # Operations Manager signature
                        # Check top-level form_data first (signatures might be at top level)
                        ops_mgr_sig = None
                        if form_data_dict.get('operations_manager_signature'):
                            ops_mgr_sig = form_data_dict.get('operations_manager_signature')
                            logger.info(f"✅ Found Operations Manager signature at top level of form_data")
                        elif form_data_dict.get('opMan_signature'):
                            ops_mgr_sig = form_data_dict.get('opMan_signature')
                            logger.info(f"✅ Found Operations Manager signature (opMan_signature) at top level of form_data")
                        # Also check nested data if submission_record was extracted from form_data['data']
                        nested_form_data = form_data_dict.get('data') if isinstance(form_data_dict.get('data'), dict) else {}
                        if not ops_mgr_sig and nested_form_data:
                            if nested_form_data.get('operations_manager_signature'):
                                ops_mgr_sig = nested_form_data.get('operations_manager_signature')
                                logger.info(f"✅ Found Operations Manager signature in nested data structure")
                            elif nested_form_data.get('opMan_signature'):
                                ops_mgr_sig = nested_form_data.get('opMan_signature')
                                logger.info(f"✅ Found Operations Manager signature (opMan_signature) in nested data structure")
                        
                        # Add to submission_record if found and not already present
                        if ops_mgr_sig and not submission_record.get('operations_manager_signature') and not submission_record.get('opMan_signature'):
                            submission_record['operations_manager_signature'] = ops_mgr_sig
                            logger.info(f"✅ Added Operations Manager signature to submission_record for PDF generation")
                        
                        # Business Development signature
                        if not submission_record.get('business_dev_signature') and not submission_record.get('businessDevSignature'):
                            if form_data_dict.get('business_dev_signature'):
                                submission_record['business_dev_signature'] = form_data_dict['business_dev_signature']
                                logger.info(f"✅ Added Business Development signature from form_data to submission_record")
                        
                        # Procurement signature
                        if not submission_record.get('procurement_signature'):
                            if form_data_dict.get('procurement_signature'):
                                submission_record['procurement_signature'] = form_data_dict['procurement_signature']
                                logger.info(f"✅ Added Procurement signature from form_data to submission_record")
                        
                        # General Manager signature
                        if not submission_record.get('general_manager_signature'):
                            if form_data_dict.get('general_manager_signature'):
                                submission_record['general_manager_signature'] = form_data_dict['general_manager_signature']
                                logger.info(f"✅ Added General Manager signature from form_data to submission_record")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch comments/signatures from submission model: {str(e)}")
            
            # Generate Excel
            logger.info("📊 Generating Excel report...")
            update_job_progress_db(job_id, 30)
            excel_path = create_excel_report(submission_record, output_dir=GENERATED_DIR)
            excel_filename = os.path.basename(excel_path)
            logger.info(f"✅ Excel created: {excel_filename}")
            
            # Upload Excel to Cloudinary (REQUIRED in production)
            update_job_progress_db(job_id, 45)
            logger.info(f"Uploading Excel to Cloudinary...")
            excel_url = upload_local_file(excel_path, f"{module_name}_excel_{sub_id}")
            if not excel_url:
                flask_env = app.config.get('FLASK_ENV', 'development')
                if flask_env == 'production':
                    logger.error("❌ Excel cloud upload failed in production - this is required!")
                    fail_job_db(job_id, "Excel cloud upload failed - required in production")
                    return
                base_url = submission_record.get('base_url', '')
                excel_url = f"{base_url}/generated/{excel_filename}"
                logger.warning("⚠️ Excel cloud upload failed, using local URL (development only)")
            else:
                logger.info(f"✅ Excel uploaded to cloud: {excel_url}")
            
            # Generate PDF
            logger.info("📄 Generating PDF report...")
            update_job_progress_db(job_id, 60)
            pdf_path = create_pdf_report(submission_record, output_dir=GENERATED_DIR)
            pdf_filename = os.path.basename(pdf_path)
            logger.info(f"✅ PDF created: {pdf_filename}")
            
            # Upload PDF to Cloudinary (REQUIRED in production)
            update_job_progress_db(job_id, 75)
            logger.info(f"Uploading PDF to Cloudinary...")
            pdf_url = upload_local_file(pdf_path, f"{module_name}_pdf_{sub_id}")
            if not pdf_url:
                flask_env = app.config.get('FLASK_ENV', 'development')
                if flask_env == 'production':
                    logger.error("❌ PDF cloud upload failed in production - this is required!")
                    fail_job_db(job_id, "PDF cloud upload failed - required in production")
                    return
                base_url = submission_record.get('base_url', '')
                pdf_url = f"{base_url}/generated/{pdf_filename}"
                logger.warning("⚠️ PDF cloud upload failed, using local URL (development only)")
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
        try:
            with app.app_context():
                fail_job_db(job_id, str(e))
        except:
            logger.error("Could not even update job status to failed")

