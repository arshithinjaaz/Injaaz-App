"""
Database utility functions for submission and job management
Provides a clean interface for database operations used by all modules
"""
import logging
from datetime import datetime
from app.models import db, Submission, Job, File
from common.utils import random_id

logger = logging.getLogger(__name__)


def create_submission_db(module_type, form_data, site_name=None, visit_date=None, user_id=None):
    """
    Create a submission in the database
    
    Args:
        module_type: 'civil', 'hvac_mep', or 'cleaning'
        form_data: Dictionary containing all form fields and file URLs
        site_name: Name of the site/project (optional)
        visit_date: Date of visit as string or date object (optional)
        user_id: ID of the user creating submission (optional)
    
    Returns:
        Submission object with submission_id
    """
    try:
        submission_id = random_id("sub")
        
        # Parse visit_date if string
        parsed_date = None
        if visit_date:
            if isinstance(visit_date, str):
                try:
                    parsed_date = datetime.strptime(visit_date, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"Invalid date format: {visit_date}")
            else:
                parsed_date = visit_date
        
        submission = Submission(
            submission_id=submission_id,
            user_id=user_id,
            module_type=module_type,
            site_name=site_name or form_data.get('site_name') or form_data.get('project_name'),
            visit_date=parsed_date,
            status='submitted',
            form_data=form_data
        )
        
        db.session.add(submission)
        db.session.commit()
        
        logger.info(f"✅ Created submission {submission_id} for {module_type}")
        return submission
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Failed to create submission: {e}")
        raise


def create_job_db(submission_id_or_obj, job_id=None):
    """
    Create a job in the database for report generation
    
    Args:
        submission_id_or_obj: Submission ID (int) or Submission object
        job_id: Custom job ID (optional, will generate if not provided)
    
    Returns:
        Job object with job_id
    """
    try:
        if not job_id:
            job_id = random_id("job")
        
        # Get submission ID if object passed
        if isinstance(submission_id_or_obj, Submission):
            submission_db_id = submission_id_or_obj.id
        elif isinstance(submission_id_or_obj, int):
            submission_db_id = submission_id_or_obj
        else:
            # Assume it's a submission_id string, need to look up
            submission = Submission.query.filter_by(submission_id=submission_id_or_obj).first()
            if not submission:
                raise ValueError(f"Submission not found: {submission_id_or_obj}")
            submission_db_id = submission.id
        
        job = Job(
            job_id=job_id,
            submission_id=submission_db_id,
            status='pending',
            progress=0,
            started_at=datetime.utcnow()
        )
        
        db.session.add(job)
        db.session.commit()
        
        logger.info(f"✅ Created job {job_id} for submission ID {submission_db_id}")
        return job
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Failed to create job: {e}")
        raise


def update_job_progress_db(job_id, progress, status=None, error_message=None):
    """
    Update job progress in database
    
    Args:
        job_id: Job ID string
        progress: Progress percentage (0-100)
        status: Optional status update ('pending', 'processing', 'completed', 'failed')
        error_message: Optional error message if failed
    """
    try:
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return
        
        job.progress = progress
        
        if status:
            job.status = status
        
        if progress > 0 and not job.started_at:
            job.started_at = datetime.utcnow()
        
        if error_message:
            job.error_message = error_message
            job.status = 'failed'
        
        db.session.commit()
        logger.debug(f"Updated job {job_id}: progress={progress}, status={status}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Failed to update job progress: {e}")


def complete_job_db(job_id, result_urls):
    """
    Mark job as completed with result URLs
    
    Args:
        job_id: Job ID string
        result_urls: Dictionary with report URLs (e.g., {"excel": "url", "pdf": "url"})
    """
    try:
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return
        
        job.status = 'completed'
        job.progress = 100
        job.completed_at = datetime.utcnow()
        job.result_data = result_urls
        
        db.session.commit()
        logger.info(f"✅ Job {job_id} completed successfully")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Failed to complete job: {e}")


def fail_job_db(job_id, error_message):
    """
    Mark job as failed with error message
    
    Args:
        job_id: Job ID string
        error_message: Error description
    """
    try:
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return
        
        job.status = 'failed'
        job.progress = 0
        job.completed_at = datetime.utcnow()
        job.error_message = error_message
        
        db.session.commit()
        logger.error(f"❌ Job {job_id} failed: {error_message}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Failed to mark job as failed: {e}")


def get_job_status_db(job_id):
    """
    Get job status from database
    
    Args:
        job_id: Job ID string
    
    Returns:
        Dictionary with job status, or None if not found
    """
    try:
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return None
        
        return job.to_dict()
        
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}")
        return None


def get_submission_db(submission_id):
    """
    Get submission from database by submission_id
    
    Args:
        submission_id: Submission ID string (e.g., 'sub_abc123')
    
    Returns:
        Dictionary with submission data, or None if not found
    """
    try:
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return None
        
        return submission.to_dict()
        
    except Exception as e:
        logger.error(f"❌ Failed to get submission: {e}")
        return None
