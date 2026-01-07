"""
Workflow Routes - Supervisor and Manager review endpoints
"""
from flask import Blueprint, request, jsonify, current_app, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, User, Submission, AuditLog
from common.error_responses import error_response, success_response
from datetime import datetime

workflow_bp = Blueprint('workflow_bp', __name__, url_prefix='/api/workflow')


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


@workflow_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def supervisor_dashboard():
    """Supervisor/Manager dashboard page"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return render_template('access_denied.html', 
                                 module='Workflow',
                                 message='User not found.'), 404
        
        if not hasattr(user, 'designation') or user.designation not in ['supervisor', 'manager']:
            return render_template('access_denied.html',
                                 module='Workflow',
                                 message='You must be assigned as a Supervisor or Manager to access this page.'), 403
        
        return render_template('supervisor_dashboard.html', 
                             user_designation=user.designation,
                             user_name=user.full_name or user.username)
    except Exception as e:
        current_app.logger.error(f"Error loading supervisor dashboard: {str(e)}", exc_info=True)
        return render_template('access_denied.html',
                             module='Workflow',
                             message='Error loading dashboard.'), 500


@workflow_bp.route('/submissions/pending', methods=['GET'])
@jwt_required()
def get_pending_submissions():
    """Get pending submissions for supervisor or manager"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if not hasattr(user, 'designation') or not user.designation:
            return error_response('No designation assigned', status_code=403, error_code='NO_DESIGNATION')
        
        # Get submissions based on designation
        if user.designation == 'supervisor':
            # Get submissions that need supervisor review
            submissions = Submission.query.filter(
                Submission.workflow_status.in_(['submitted', 'supervisor_notified'])
            ).all()
        elif user.designation == 'manager':
            # Get submissions that need manager review
            submissions = Submission.query.filter(
                Submission.workflow_status.in_(['supervisor_reviewing', 'manager_notified'])
            ).all()
        else:
            return error_response('Invalid designation for review', status_code=403, error_code='INVALID_DESIGNATION')
        
        result = []
        for submission in submissions:
            sub_user = User.query.get(submission.user_id) if submission.user_id else None
            result.append({
                **submission.to_dict(),
                'user': sub_user.to_dict() if sub_user else None
            })
        
        return success_response({
            'submissions': result,
            'count': len(result)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting pending submissions: {str(e)}", exc_info=True)
        return error_response('Failed to get pending submissions', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/start-review', methods=['POST'])
@jwt_required()
def start_review(submission_id):
    """Start reviewing a submission (supervisor or manager)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first_or_404()
        
        if user.designation == 'supervisor':
            if submission.workflow_status not in ['submitted', 'supervisor_notified']:
                return error_response('Submission is not ready for supervisor review', 
                                    status_code=400, error_code='INVALID_STATUS')
            submission.workflow_status = 'supervisor_reviewing'
            submission.supervisor_id = user.id
            if not submission.supervisor_notified_at:
                submission.supervisor_notified_at = datetime.utcnow()
            log_audit(user_id, 'start_supervisor_review', 'submission', submission_id)
        
        elif user.designation == 'manager':
            if submission.workflow_status not in ['supervisor_reviewing', 'manager_notified']:
                return error_response('Submission is not ready for manager review', 
                                    status_code=400, error_code='INVALID_STATUS')
            submission.workflow_status = 'manager_reviewing'
            submission.manager_id = user.id
            if not submission.manager_notified_at:
                submission.manager_notified_at = datetime.utcnow()
            log_audit(user_id, 'start_manager_review', 'submission', submission_id)
        
        else:
            return error_response('Invalid designation for review', status_code=403, error_code='INVALID_DESIGNATION')
        
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Review started successfully'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error starting review: {str(e)}", exc_info=True)
        return error_response('Failed to start review', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/approve', methods=['POST'])
@jwt_required()
def approve_submission(submission_id):
    """Approve and forward submission (supervisor -> manager, manager -> approved)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        comments = data.get('comments', '')
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first_or_404()
        
        if user.designation == 'supervisor':
            if submission.workflow_status != 'supervisor_reviewing':
                return error_response('Submission is not being reviewed by supervisor', 
                                    status_code=400, error_code='INVALID_STATUS')
            
            submission.workflow_status = 'manager_notified'
            submission.supervisor_reviewed_at = datetime.utcnow()
            
            # Notify manager
            from common.db_utils import _notify_manager
            _notify_manager(submission, db.session)
            
            log_audit(user_id, 'supervisor_approved', 'submission', submission_id, {'comments': comments})
        
        elif user.designation == 'manager':
            if submission.workflow_status != 'manager_reviewing':
                return error_response('Submission is not being reviewed by manager', 
                                    status_code=400, error_code='INVALID_STATUS')
            
            submission.workflow_status = 'approved'
            submission.manager_reviewed_at = datetime.utcnow()
            submission.status = 'completed'
            
            log_audit(user_id, 'manager_approved', 'submission', submission_id, {'comments': comments})
        
        else:
            return error_response('Invalid designation for approval', status_code=403, error_code='INVALID_DESIGNATION')
        
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Submission approved and forwarded successfully'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error approving submission: {str(e)}", exc_info=True)
        return error_response('Failed to approve submission', status_code=500, error_code='DATABASE_ERROR')


@workflow_bp.route('/submissions/<submission_id>/reject', methods=['POST'])
@jwt_required()
def reject_submission(submission_id):
    """Reject submission and send back to technician"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if user.designation not in ['supervisor', 'manager']:
            return error_response('Only supervisor or manager can reject submissions', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first_or_404()
        
        submission.workflow_status = 'rejected'
        submission.updated_at = datetime.utcnow()
        
        if user.designation == 'supervisor':
            submission.supervisor_reviewed_at = datetime.utcnow()
        elif user.designation == 'manager':
            submission.manager_reviewed_at = datetime.utcnow()
        
        db.session.commit()
        
        log_audit(user_id, 'reject_submission', 'submission', submission_id, {
            'reason': reason,
            'rejected_by': user.designation
        })
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Submission rejected successfully'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting submission: {str(e)}", exc_info=True)
        return error_response('Failed to reject submission', status_code=500, error_code='DATABASE_ERROR')
