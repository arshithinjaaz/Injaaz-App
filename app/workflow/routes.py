"""
Workflow Routes - New 5-Stage Approval System
Stage 1: Supervisor/Inspector (creates form)
Stage 2: Operations Manager (reviews, edits, approves)
Stage 3: Business Development + Procurement (parallel review)
Stage 4: General Manager (final approval)
"""
from flask import Blueprint, request, jsonify, current_app, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, and_
from app.models import db, User, Submission, AuditLog
from common.error_responses import error_response, success_response
from datetime import datetime

workflow_bp = Blueprint('workflow_bp', __name__, url_prefix='/api/workflow')

# Valid designations for workflow
VALID_DESIGNATIONS = [
    'supervisor',
    'operations_manager',
    'business_development',
    'procurement',
    'general_manager'
]

# Workflow status progression
WORKFLOW_STAGES = {
    'submitted': 'operations_manager_review',
    'operations_manager_review': 'operations_manager_approved',
    'operations_manager_approved': 'bd_procurement_review',
    'bd_procurement_review': 'general_manager_review',  # After both BD & Procurement approve
    'general_manager_review': 'general_manager_approved',
    'general_manager_approved': 'completed'
}


def log_audit(user_id, action, resource_type=None, resource_id=None, details=None):
    """Create audit log entry"""
    try:
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            details=details
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to create audit log: {str(e)}")
        db.session.rollback()


def get_user_pending_submissions(user):
    """Get submissions pending for a user's designation"""
    designation = user.designation
    
    if designation == 'operations_manager':
        return Submission.query.filter(
            Submission.workflow_status == 'operations_manager_review'
        ).order_by(Submission.created_at.desc()).all()
    
    elif designation == 'business_development':
        return Submission.query.filter(
            Submission.workflow_status == 'bd_procurement_review',
            or_(
                Submission.business_dev_approved_at.is_(None),
                Submission.business_dev_approved_at == None
            )
        ).order_by(Submission.created_at.desc()).all()
    
    elif designation == 'procurement':
        return Submission.query.filter(
            Submission.workflow_status == 'bd_procurement_review',
            or_(
                Submission.procurement_approved_at.is_(None),
                Submission.procurement_approved_at == None
            )
        ).order_by(Submission.created_at.desc()).all()
    
    elif designation == 'general_manager':
        return Submission.query.filter(
            Submission.workflow_status == 'general_manager_review'
        ).order_by(Submission.created_at.desc()).all()
    
    elif designation == 'supervisor':
        # Supervisors see their own submissions or rejected ones
        return Submission.query.filter(
            or_(
                Submission.supervisor_id == user.id,
                and_(
                    Submission.workflow_status == 'rejected',
                    Submission.supervisor_id == user.id
                )
            )
        ).order_by(Submission.created_at.desc()).all()
    
    return []


def can_edit_submission(user, submission):
    """Check if user can edit a submission based on current workflow stage"""
    if user.role == 'admin':
        return True
    
    designation = user.designation
    status = submission.workflow_status
    
    # Supervisor can edit their own submissions if:
    # - Status is submitted/rejected (initial state)
    # - Status is operations_manager_review but not yet approved (allows updates before review)
    if designation == 'supervisor':
        # Check if this is the supervisor's own submission
        # Use supervisor_id if set, otherwise fall back to user_id (for older submissions)
        is_own_submission = (
            (hasattr(submission, 'supervisor_id') and submission.supervisor_id == user.id) or
            (submission.user_id == user.id)
        )
        
        if not is_own_submission:
            return False
        
        # Allow editing if status is submitted/rejected, or if in operations_manager_review but not yet approved
        if status in ['submitted', 'rejected', None]:
            return True
        if status == 'operations_manager_review' and not submission.operations_manager_approved_at:
            return True
        return False
    
    # Operations Manager can edit during their review stage
    if designation == 'operations_manager':
        return status == 'operations_manager_review'
    
    # Business Development can edit during BD/Procurement review stage (if not yet approved by them)
    if designation == 'business_development':
        return status == 'bd_procurement_review' and not submission.business_dev_approved_at
    
    # Procurement can edit during BD/Procurement review stage (if not yet approved by them)
    if designation == 'procurement':
        return status == 'bd_procurement_review' and not submission.procurement_approved_at
    
    # General Manager can edit during their review stage
    if designation == 'general_manager':
        return status == 'general_manager_review'
    
    return False


@workflow_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def workflow_dashboard():
    """Workflow dashboard page for all roles"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return render_template('access_denied.html', 
                                 module='Workflow',
                                 message='User not found.'), 404
        
        if not hasattr(user, 'designation') or user.designation not in VALID_DESIGNATIONS:
            if user.role != 'admin':
                return render_template('access_denied.html',
                                     module='Workflow',
                                     message='You must have a valid designation assigned to access workflow.'), 403
        
        return render_template('workflow_dashboard.html', 
                             user_designation=user.designation or 'admin',
                             user_role=user.role,
                             user_name=user.full_name or user.username)
    except Exception as e:
        current_app.logger.error(f"Error loading workflow dashboard: {str(e)}", exc_info=True)
        return render_template('access_denied.html',
                             module='Workflow',
                             message='Error loading dashboard.'), 500


@workflow_bp.route('/history', methods=['GET'])
@jwt_required()
def history_page():
    """Render the Review History page"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return render_template('access_denied.html', module='Workflow', message='User not found.'), 404
            
        if not hasattr(user, 'designation') or user.designation not in VALID_DESIGNATIONS:
            if user.role != 'admin':
                return render_template('access_denied.html',
                                     module='Workflow',
                                     message='You must have a valid designation to access workflow history.'), 403
        
        return render_template('workflow_history.html', 
                             user_designation=user.designation or 'admin',
                             user_name=user.full_name or user.username)
    except Exception as e:
        current_app.logger.error(f"Error loading history page: {str(e)}", exc_info=True)
        return render_template('access_denied.html', module='Workflow', message='Error loading history page.'), 500


@workflow_bp.route('/submissions/pending', methods=['GET'])
@jwt_required()
def get_pending_submissions():
    """Get pending submissions for current user based on their designation"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if not hasattr(user, 'designation') or not user.designation:
            if user.role != 'admin':
                return error_response('No designation assigned', status_code=403, error_code='NO_DESIGNATION')
            # Admin sees all pending
            submissions = Submission.query.filter(
                Submission.workflow_status != 'completed'
            ).order_by(Submission.created_at.desc()).all()
        else:
            submissions = get_user_pending_submissions(user)
        
        result = []
        for submission in submissions:
            sub_user = User.query.get(submission.user_id) if submission.user_id else None
            sub_dict = submission.to_dict()
            sub_dict['user'] = sub_user.to_dict() if sub_user else None
            sub_dict['can_edit'] = can_edit_submission(user, submission)
            result.append(sub_dict)
        
        return success_response({
            'submissions': result,
            'count': len(result)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting pending submissions: {str(e)}", exc_info=True)
        return error_response('Failed to get pending submissions', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/history', methods=['GET'])
@jwt_required()
def get_history_submissions():
    """Get all relevant submissions for user (reviewed and pending)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        # Admin sees all submissions
        if user.role == 'admin':
            submissions = Submission.query.order_by(Submission.created_at.desc()).all()
        elif not hasattr(user, 'designation') or not user.designation:
            return error_response('No designation assigned', status_code=403, error_code='NO_DESIGNATION')
        else:
            designation = user.designation
            
            # Filter based on designation
            if designation == 'supervisor':
                submissions = Submission.query.filter(
                    Submission.supervisor_id == user.id
                ).order_by(Submission.created_at.desc()).all()
            
            elif designation == 'operations_manager':
                # Operations Manager sees all forms they've reviewed (where they're assigned as operations_manager_id)
                # This includes forms they've approved even if status has moved forward
                submissions = Submission.query.filter(
                    Submission.operations_manager_id == user.id
                ).order_by(Submission.created_at.desc()).all()
            
            elif designation == 'business_development':
                submissions = Submission.query.filter(
                    Submission.business_dev_id == user.id
                ).order_by(Submission.created_at.desc()).all()
            
            elif designation == 'procurement':
                submissions = Submission.query.filter(
                    Submission.procurement_id == user.id
                ).order_by(Submission.created_at.desc()).all()
            
            elif designation == 'general_manager':
                # GM sees everything that reached their stage
                submissions = Submission.query.filter(
                    or_(
                        Submission.workflow_status == 'general_manager_review',
                        Submission.workflow_status == 'general_manager_approved',
                        Submission.workflow_status == 'completed',
                        Submission.general_manager_id == user.id
                    )
                ).order_by(Submission.created_at.desc()).all()
            else:
                submissions = []
        
        result = []
        for submission in submissions:
            sub_user = User.query.get(submission.user_id) if submission.user_id else None
            sub_dict = submission.to_dict()
            sub_dict['user'] = sub_user.to_dict() if sub_user else None
            result.append(sub_dict)
        
        return success_response({
            'submissions': result,
            'count': len(result)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting history submissions: {str(e)}", exc_info=True)
        return error_response('Failed to get submission history', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>', methods=['GET'])
@jwt_required()
def get_submission_detail(submission_id):
    """Get detailed submission information"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        # Check access permissions
        has_access = (
            user.role == 'admin' or
            submission.supervisor_id == user.id or
            (user.designation and user.designation in VALID_DESIGNATIONS)
        )
        
        if not has_access:
            return error_response('Access denied', status_code=403, error_code='UNAUTHORIZED')
        
        sub_dict = submission.to_dict()
        sub_dict['can_edit'] = can_edit_submission(user, submission)
        
        # Add user details
        if submission.user_id:
            submitter = User.query.get(submission.user_id)
            sub_dict['user'] = submitter.to_dict() if submitter else None
        
        # Add approver details
        if submission.operations_manager_id:
            ops_mgr = User.query.get(submission.operations_manager_id)
            sub_dict['operations_manager'] = ops_mgr.to_dict() if ops_mgr else None
        
        if submission.business_dev_id:
            bd_user = User.query.get(submission.business_dev_id)
            sub_dict['business_dev'] = bd_user.to_dict() if bd_user else None
        
        if submission.procurement_id:
            proc_user = User.query.get(submission.procurement_id)
            sub_dict['procurement'] = proc_user.to_dict() if proc_user else None
        
        if submission.general_manager_id:
            gm_user = User.query.get(submission.general_manager_id)
            sub_dict['general_manager'] = gm_user.to_dict() if gm_user else None
        
        return success_response(sub_dict)
    except Exception as e:
        current_app.logger.error(f"Error getting submission detail: {str(e)}", exc_info=True)
        return error_response('Failed to get submission', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/approve-ops-manager', methods=['POST'])
@jwt_required()
def approve_operations_manager(submission_id):
    """Operations Manager approves submission"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if user.designation != 'operations_manager' and user.role != 'admin':
            return error_response('Only Operations Manager can approve at this stage', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        if submission.workflow_status != 'operations_manager_review':
            return error_response('Submission is not at Operations Manager review stage', 
                                status_code=400, error_code='INVALID_STATUS')
        
        # Extract data
        comments = data.get('comments', '')
        signature = data.get('signature', '')
        form_data_updates = data.get('form_data', {})
        
        # Update submission
        submission.operations_manager_id = user.id
        submission.operations_manager_comments = comments
        submission.operations_manager_approved_at = datetime.utcnow()
        submission.workflow_status = 'operations_manager_approved'
        
        # Update form_data if provided
        form_data = submission.form_data if submission.form_data else {}
        if form_data_updates:
            form_data.update(form_data_updates)
        
        # Always save Operations Manager comments and signature to form_data for next reviewers
        if comments:
            form_data['operations_manager_comments'] = comments
        if signature:
            form_data['operations_manager_signature'] = signature
        
        submission.form_data = form_data
        
        # Move to BD/Procurement review
        submission.workflow_status = 'bd_procurement_review'
        submission.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Regenerate documents if this is an HVAC submission (to include Operations Manager comments/signature)
        job_id = None
        if submission.module_type == 'hvac_mep':
            from common.db_utils import create_job_db
            from module_hvac_mep.routes import get_paths, process_job
            from app.models import Job
            
            # Delete old jobs to force regeneration
            old_jobs = Job.query.filter_by(submission_id=submission.id).all()
            for old_job in old_jobs:
                db.session.delete(old_job)
            db.session.commit()
            
            # Create new job for regeneration
            new_job = create_job_db(submission)
            job_id = new_job.job_id
            
            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
            
            if EXECUTOR:
                EXECUTOR.submit(
                    process_job,
                    submission.submission_id,
                    job_id,
                    current_app.config,
                    current_app._get_current_object()
                )
                current_app.logger.info(f"✅ Regeneration job {job_id} queued for Operations Manager approval - submission {submission_id}")
            else:
                current_app.logger.error("ThreadPoolExecutor not available for document regeneration")
        
        log_audit(user_id, 'operations_manager_approved', 'submission', submission_id, {
            'comments': comments,
            'has_signature': bool(signature)
        })
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Approved successfully. Forwarded to Business Development and Procurement.' + (' Documents are being regenerated.' if job_id else ''),
            'job_id': job_id,
            'regenerating': bool(job_id)
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in ops manager approval: {str(e)}", exc_info=True)
        return error_response('Failed to approve submission', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/approve-bd', methods=['POST'])
@jwt_required()
def approve_business_development(submission_id):
    """Business Development approves submission"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if user.designation != 'business_development' and user.role != 'admin':
            return error_response('Only Business Development can approve at this stage', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        if submission.workflow_status != 'bd_procurement_review':
            return error_response('Submission is not at BD/Procurement review stage', 
                                status_code=400, error_code='INVALID_STATUS')
        
        if submission.business_dev_approved_at:
            return error_response('Already approved by Business Development', 
                                status_code=400, error_code='ALREADY_APPROVED')
        
        # Extract data
        comments = data.get('comments', '')
        signature = data.get('signature', '')
        form_data_updates = data.get('form_data', {})
        
        # Update submission
        submission.business_dev_id = user.id
        submission.business_dev_comments = comments
        submission.business_dev_approved_at = datetime.utcnow()
        
        # Update form_data if provided
        form_data = submission.form_data if submission.form_data else {}
        if form_data_updates:
            form_data.update(form_data_updates)
        
        # Always save BD comments and signature to form_data for next reviewers
        if comments:
            form_data['business_dev_comments'] = comments
        if signature:
            form_data['business_dev_signature'] = signature
        
        submission.form_data = form_data
        
        # Check if both BD and Procurement have approved
        if submission.procurement_approved_at:
            submission.workflow_status = 'general_manager_review'
            message = 'Approved successfully. Both BD and Procurement approved. Forwarded to General Manager.'
        else:
            message = 'Approved successfully. Waiting for Procurement approval.'
        
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        # If this is an HVAC submission, regenerate documents so GM/History always
        # see PDFs that include BD + previous reviewers' changes
        job_id = None
        if submission.module_type == 'hvac_mep':
            try:
                from common.db_utils import create_job_db
                from module_hvac_mep.routes import get_paths, process_job
                from app.models import Job

                # Delete old jobs so we always generate a fresh set for this stage
                old_jobs = Job.query.filter_by(submission_id=submission.id).all()
                for old_job in old_jobs:
                    db.session.delete(old_job)
                db.session.commit()

                new_job = create_job_db(submission)
                job_id = new_job.job_id

                GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
                if EXECUTOR:
                    EXECUTOR.submit(
                        process_job,
                        submission.submission_id,
                        job_id,
                        current_app.config,
                        current_app._get_current_object()
                    )
                    current_app.logger.info(f"✅ Regeneration job {job_id} queued for BD approval - submission {submission_id}")
                else:
                    current_app.logger.error("ThreadPoolExecutor not available for BD document regeneration")
            except Exception as regen_err:
                current_app.logger.error(f"Error queuing regeneration job after BD approval: {regen_err}", exc_info=True)
        
        log_audit(user_id, 'business_dev_approved', 'submission', submission_id, {'comments': comments})
        
        return success_response({
            'submission': submission.to_dict(),
            'message': message,
            'job_id': job_id,
            'regenerating': bool(job_id)
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in BD approval: {str(e)}", exc_info=True)
        return error_response('Failed to approve submission', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/approve-procurement', methods=['POST'])
@jwt_required()
def approve_procurement(submission_id):
    """Procurement approves submission"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if user.designation != 'procurement' and user.role != 'admin':
            return error_response('Only Procurement can approve at this stage', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        if submission.workflow_status != 'bd_procurement_review':
            return error_response('Submission is not at BD/Procurement review stage', 
                                status_code=400, error_code='INVALID_STATUS')
        
        if submission.procurement_approved_at:
            return error_response('Already approved by Procurement', 
                                status_code=400, error_code='ALREADY_APPROVED')
        
        # Extract data
        comments = data.get('comments', '')
        signature = data.get('signature', '')
        form_data_updates = data.get('form_data', {})
        
        # Update submission
        submission.procurement_id = user.id
        submission.procurement_comments = comments
        submission.procurement_approved_at = datetime.utcnow()
        
        # Update form_data if provided
        form_data = submission.form_data if submission.form_data else {}
        if form_data_updates:
            form_data.update(form_data_updates)
        
        # Always save Procurement comments and signature to form_data for next reviewers
        if comments:
            form_data['procurement_comments'] = comments
        if signature:
            form_data['procurement_signature'] = signature
        
        submission.form_data = form_data
        
        # Check if both BD and Procurement have approved
        if submission.business_dev_approved_at:
            submission.workflow_status = 'general_manager_review'
            message = 'Approved successfully. Both BD and Procurement approved. Forwarded to General Manager.'
        else:
            message = 'Approved successfully. Waiting for Business Development approval.'
        
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Regenerate documents for HVAC so GM/History PDFs include Procurement stage
        job_id = None
        if submission.module_type == 'hvac_mep':
            try:
                from common.db_utils import create_job_db
                from module_hvac_mep.routes import get_paths, process_job
                from app.models import Job

                old_jobs = Job.query.filter_by(submission_id=submission.id).all()
                for old_job in old_jobs:
                    db.session.delete(old_job)
                db.session.commit()

                new_job = create_job_db(submission)
                job_id = new_job.job_id

                GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
                if EXECUTOR:
                    EXECUTOR.submit(
                        process_job,
                        submission.submission_id,
                        job_id,
                        current_app.config,
                        current_app._get_current_object()
                    )
                    current_app.logger.info(f"✅ Regeneration job {job_id} queued for Procurement approval - submission {submission_id}")
                else:
                    current_app.logger.error("ThreadPoolExecutor not available for Procurement document regeneration")
            except Exception as regen_err:
                current_app.logger.error(f"Error queuing regeneration job after Procurement approval: {regen_err}", exc_info=True)
        
        log_audit(user_id, 'procurement_approved', 'submission', submission_id, {'comments': comments})
        
        return success_response({
            'submission': submission.to_dict(),
            'message': message,
            'job_id': job_id,
            'regenerating': bool(job_id)
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in Procurement approval: {str(e)}", exc_info=True)
        return error_response('Failed to approve submission', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/approve-gm', methods=['POST'])
@jwt_required()
def approve_general_manager(submission_id):
    """General Manager gives final approval"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if user.designation != 'general_manager' and user.role != 'admin':
            return error_response('Only General Manager can approve at this stage', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        if submission.workflow_status != 'general_manager_review':
            return error_response('Submission is not at General Manager review stage', 
                                status_code=400, error_code='INVALID_STATUS')
        
        # Extract data
        comments = data.get('comments', '')
        signature = data.get('signature', '')
        form_data_updates = data.get('form_data', {})
        
        # Update submission
        submission.general_manager_id = user.id
        submission.general_manager_comments = comments
        submission.general_manager_approved_at = datetime.utcnow()
        submission.workflow_status = 'completed'
        submission.status = 'completed'
        
        # Update form_data if provided
        form_data = submission.form_data if submission.form_data else {}
        if form_data_updates:
            form_data.update(form_data_updates)
        
        # Always save General Manager comments and signature to form_data
        if comments:
            form_data['general_manager_comments'] = comments
        if signature:
            form_data['general_manager_signature'] = signature
        
        submission.form_data = form_data
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Regenerate documents if this is an HVAC submission (to include all reviewer signatures)
        job_id = None
        if submission.module_type == 'hvac_mep':
            from common.db_utils import create_job_db
            from module_hvac_mep.routes import get_paths, process_job
            from app.models import Job
            
            # Delete old jobs to force regeneration
            old_jobs = Job.query.filter_by(submission_id=submission.id).all()
            for old_job in old_jobs:
                db.session.delete(old_job)
            db.session.commit()
            
            # Create new job for regeneration
            new_job = create_job_db(submission)
            job_id = new_job.job_id
            
            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
            
            if EXECUTOR:
                EXECUTOR.submit(
                    process_job,
                    submission.submission_id,
                    job_id,
                    current_app.config,
                    current_app._get_current_object()
                )
                current_app.logger.info(f"✅ Regeneration job {job_id} queued for General Manager approval - submission {submission_id}")
            else:
                current_app.logger.error("ThreadPoolExecutor not available for document regeneration")
        
        log_audit(user_id, 'general_manager_approved', 'submission', submission_id, {
            'comments': comments,
            'has_signature': bool(signature)
        })
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Final approval completed. Submission is now complete.' + (' Documents are being regenerated with all signatures.' if job_id else ''),
            'job_id': job_id,
            'regenerating': bool(job_id)
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in GM approval: {str(e)}", exc_info=True)
        return error_response('Failed to approve submission', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/my-submissions', methods=['GET'])
@jwt_required()
def get_my_submissions():
    """Get all submissions created by the current supervisor"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if user.designation != 'supervisor' and user.role != 'admin':
            return error_response('Only supervisors can view submitted forms', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        # Get all submissions by this supervisor
        submissions = Submission.query.filter_by(supervisor_id=user.id).order_by(Submission.created_at.desc()).all()
        
        submissions_list = []
        for submission in submissions:
            sub_dict = submission.to_dict()
            # Add module information
            module_map = {
                'hvac': 'HVAC & MEP',
                'hvac_mep': 'HVAC & MEP',
                'civil': 'Civil Works',
                'cleaning': 'Cleaning Services'
            }
            sub_dict['module_name'] = module_map.get(submission.module_type, submission.module_type)
            submissions_list.append(sub_dict)
        
        return success_response({
            'submissions': submissions_list,
            'count': len(submissions_list)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting my submissions: {str(e)}", exc_info=True)
        return error_response('Failed to get submissions', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/reject', methods=['POST'])
@jwt_required()
def reject_submission(submission_id):
    """Reject submission at any stage and send back to supervisor"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if not reason:
            return error_response('Rejection reason is required', status_code=400, error_code='MISSING_REASON')
        
        if user.designation not in VALID_DESIGNATIONS and user.role != 'admin':
            return error_response('Invalid designation for rejection', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        # Record rejection details
        submission.workflow_status = 'rejected'
        submission.rejection_stage = submission.workflow_status  # Store previous stage
        submission.rejection_reason = reason
        submission.rejected_at = datetime.utcnow()
        submission.rejected_by_id = user.id
        submission.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        log_audit(user_id, 'reject_submission', 'submission', submission_id, {
            'reason': reason,
            'rejected_by': user.designation or user.role,
            'stage': submission.rejection_stage
        })
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Submission rejected and sent back to supervisor for revision.'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting submission: {str(e)}", exc_info=True)
        return error_response('Failed to reject submission', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/update', methods=['PUT'])
@jwt_required()
def update_submission(submission_id):
    """Update submission form data (for edits during review)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        if not can_edit_submission(user, submission):
            return error_response('You do not have permission to edit this submission', 
                                status_code=403, error_code='UNAUTHORIZED')
        
        # Check if supervisor is updating their own submission
        # Allow updates if status is submitted/rejected OR if in operations_manager_review but not yet approved
        is_supervisor_own_update = (
            user.designation == 'supervisor' and 
            hasattr(submission, 'supervisor_id') and 
            submission.supervisor_id == user.id and
            (
                submission.workflow_status in ['submitted', 'rejected'] or
                (submission.workflow_status == 'operations_manager_review' and not submission.operations_manager_approved_at)
            )
        )
        
        # Update form_data - accept full form_data or updates
        if 'form_data' in data:
            # If full form_data is provided, use it directly (like admin endpoint)
            form_data = data['form_data'].copy() if isinstance(data['form_data'], dict) else data['form_data']
            
            # Convert photo_urls to photos format for PDF generator (if items are present)
            if isinstance(form_data, dict) and 'items' in form_data and isinstance(form_data['items'], list):
                items = form_data['items']
                for item in items:
                    # Convert photo_urls array to photos format expected by generators
                    # Frontend sends photo_urls (array of strings), we need photos (array of objects)
                    if 'photo_urls' in item and isinstance(item['photo_urls'], list):
                        photos_saved = []
                        for url in item['photo_urls']:
                            if url:  # Only add non-empty URLs
                                photos_saved.append({
                                    "saved": None,
                                    "path": None,
                                    "url": url,
                                    "is_cloud": True
                                })
                        # Set photos from photo_urls (frontend sends complete list)
                        item['photos'] = photos_saved
                    # If photos already exist but no photo_urls, keep photos as-is
                    # This handles cases where items already have photos in correct format
                    elif 'photos' not in item or not item.get('photos'):
                        # No photos at all - initialize empty array
                        item['photos'] = []
            
            # If supervisor is updating their own submission, ensure signature is saved
            if is_supervisor_own_update and isinstance(form_data, dict):
                existing_comment = form_data.get('supervisor_comments', '')
                if existing_comment and '[Form updated by supervisor with new details]' not in existing_comment:
                    form_data['supervisor_comments'] = existing_comment + '\n\n[Form updated by supervisor with new details]'
                elif not existing_comment:
                    form_data['supervisor_comments'] = '[Form updated by supervisor with new details]'
                
                # Ensure supervisor_signature is in form_data if provided in payload
                if 'supervisor_signature' in form_data and form_data['supervisor_signature']:
                    # Signature is already in form_data, ensure it's preserved
                    current_app.logger.info(f"✅ Supervisor signature preserved in form_data for submission {submission_id}")
                elif 'supervisor_signature' not in form_data or not form_data.get('supervisor_signature'):
                    # Check if signature exists in old form_data and preserve it
                    old_form_data = submission.form_data if submission.form_data else {}
                    if old_form_data.get('supervisor_signature'):
                        form_data['supervisor_signature'] = old_form_data['supervisor_signature']
                        current_app.logger.info(f"⚠️ Preserving existing supervisor signature for submission {submission_id}")
                    else:
                        current_app.logger.warning(f"⚠️ No supervisor signature found in form_data for submission {submission_id}")
            
            submission.form_data = form_data
        elif 'form_data_updates' in data:
            # Otherwise merge updates (backward compatibility)
            form_data_updates = data.get('form_data_updates', {})
            form_data = submission.form_data if submission.form_data else {}
            form_data.update(form_data_updates)
            submission.form_data = form_data
        
        # Update site_name and visit_date if provided
        if 'site_name' in data:
            submission.site_name = data['site_name']
        if 'visit_date' in data:
            try:
                submission.visit_date = datetime.strptime(data['visit_date'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass  # Invalid date, skip
        
        # If supervisor is updating their own submission, move it to Operations Manager review
        # This ensures updated forms are sent for review with new changes
        if is_supervisor_own_update:
            # Change status to operations_manager_review so it goes to Operations Manager
            submission.workflow_status = 'operations_manager_review'
        
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Regenerate documents if this is an HVAC submission and it's a supervisor updating their own submission
        # or if it's being updated by a reviewer
        job_id = None
        should_regenerate = is_supervisor_own_update or user.designation in ['operations_manager', 'business_development', 'procurement', 'general_manager']
        if submission.module_type == 'hvac_mep' and should_regenerate:
            from common.db_utils import create_job_db
            from module_hvac_mep.routes import get_paths, process_job
            from app.models import Job
            
            # Delete old jobs to force regeneration
            old_jobs = Job.query.filter_by(submission_id=submission.id).all()
            for old_job in old_jobs:
                db.session.delete(old_job)
            db.session.commit()
            
            # Create new job for regeneration
            new_job = create_job_db(submission)
            job_id = new_job.job_id
            
            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
            
            if EXECUTOR:
                EXECUTOR.submit(
                    process_job,
                    submission.submission_id,
                    job_id,
                    current_app.config,
                    current_app._get_current_object()
                )
                current_app.logger.info(f"✅ Regeneration job {job_id} queued for submission {submission_id}")
            else:
                current_app.logger.error("ThreadPoolExecutor not available for document regeneration")
        
        log_audit(user_id, 'update_submission', 'submission', submission_id)
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Submission updated successfully. Documents are being regenerated.' if job_id else 'Submission updated successfully',
            'job_id': job_id,
            'regenerating': bool(job_id)
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating submission: {str(e)}", exc_info=True)
        return error_response('Failed to update submission', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/resubmit', methods=['POST'])
@jwt_required()
def resubmit_submission(submission_id):
    """Resubmit a rejected submission (supervisor only)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if user.designation != 'supervisor' and user.role != 'admin':
            return error_response('Only supervisors can resubmit rejected submissions', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        if submission.workflow_status != 'rejected':
            return error_response('Only rejected submissions can be resubmitted', 
                                status_code=400, error_code='INVALID_STATUS')
        
        if submission.supervisor_id != user.id and user.role != 'admin':
            return error_response('You can only resubmit your own submissions', 
                                status_code=403, error_code='UNAUTHORIZED')
        
        # Update form_data if provided
        form_data_updates = data.get('form_data', {})
        if form_data_updates:
            form_data = submission.form_data if submission.form_data else {}
            form_data.update(form_data_updates)
            submission.form_data = form_data
        
        # Reset workflow to start
        submission.workflow_status = 'operations_manager_review'
        submission.rejection_stage = None
        submission.rejection_reason = None
        submission.rejected_at = None
        submission.rejected_by_id = None
        submission.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        log_audit(user_id, 'resubmit_submission', 'submission', submission_id)
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Submission resubmitted successfully. Sent to Operations Manager.'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resubmitting submission: {str(e)}", exc_info=True)
        return error_response('Failed to resubmit submission', status_code=500, error_code='DATABASE_ERROR')


# Legacy compatibility endpoints (deprecated but kept for backwards compatibility)
@workflow_bp.route('/submissions/<submission_id>/approve', methods=['POST'])
@jwt_required()
def legacy_approve_submission(submission_id):
    """Legacy approval endpoint - routes to appropriate new endpoint"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        # Route to appropriate endpoint based on current workflow status
        if submission.workflow_status == 'operations_manager_review':
            return approve_operations_manager(submission_id)
        elif submission.workflow_status == 'bd_procurement_review':
            if user.designation == 'business_development':
                return approve_business_development(submission_id)
            elif user.designation == 'procurement':
                return approve_procurement(submission_id)
        elif submission.workflow_status == 'general_manager_review':
            return approve_general_manager(submission_id)
        else:
            return error_response('Invalid workflow status for approval', 
                                status_code=400, error_code='INVALID_STATUS')
    except Exception as e:
        current_app.logger.error(f"Error in legacy approval: {str(e)}", exc_info=True)
        return error_response('Failed to process approval', status_code=500, error_code='DATABASE_ERROR')
