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


def get_module_functions(module_type):
    """
    Get module-specific functions for signature handling and job processing.
    Returns (save_signature_dataurl, get_paths, process_job) functions.
    """
    if module_type == 'hvac_mep':
        from module_hvac_mep.routes import save_signature_dataurl, get_paths, process_job
        return save_signature_dataurl, get_paths, process_job
    elif module_type == 'civil':
        from module_civil.routes import save_signature_dataurl, process_job
        # Civil uses app_paths() instead of get_paths(), create a wrapper
        def get_paths_civil():
            from module_civil.routes import app_paths
            return app_paths()
        return save_signature_dataurl, get_paths_civil, process_job
    elif module_type == 'cleaning':
        # Cleaning doesn't have these functions yet, use common utilities
        from common.utils import upload_base64_to_cloud
        import os
        from config import GENERATED_DIR, UPLOADS_DIR, JOBS_DIR
        from concurrent.futures import ThreadPoolExecutor
        
        def save_signature_dataurl_cleaning(dataurl, uploads_dir, prefix="signature"):
            """Save signature for cleaning module"""
            if not dataurl:
                return None, None, None
            try:
                url, is_cloud = upload_base64_to_cloud(dataurl, folder="signatures", prefix=prefix, uploads_dir=uploads_dir)
                if url:
                    if is_cloud:
                        return None, None, url
                    else:
                        filename = url.split('/')[-1]
                        file_path = os.path.join(GENERATED_DIR, "uploads", "signatures", filename)
                        return filename, file_path, url
                raise Exception("Upload succeeded but no URL returned")
            except Exception as e:
                current_app.logger.error(f"Signature upload failed: {e}")
                raise
        
        def get_paths_cleaning():
            """Get paths for cleaning module"""
            executor = current_app.config.get('EXECUTOR') if current_app else None
            if not executor:
                executor = ThreadPoolExecutor(max_workers=2)
            return GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, executor
        
        from module_cleaning.routes import process_job
        return save_signature_dataurl_cleaning, get_paths_cleaning, process_job
    else:
        raise ValueError(f"Unknown module type: {module_type}")

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
    
    # Business Development can edit during BD/Procurement review stage
    # Allow editing if status is bd_procurement_review (even after approval, to allow comment/signature updates)
    if designation == 'business_development':
        return status == 'bd_procurement_review'
    
    # Procurement can edit during BD/Procurement review stage
    # Allow editing if status is bd_procurement_review (even after approval, to allow comment/signature updates)
    if designation == 'procurement':
        return status == 'bd_procurement_review'
    
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
            
            # For admin, include all reviewer comments in the history
            if user.role == 'admin':
                form_data = submission.form_data
                if isinstance(form_data, str):
                    try:
                        import json
                        form_data = json.loads(form_data)
                    except:
                        form_data = {}
                
                reviewers = []
                
                # Operations Manager
                om_has_approved = bool(submission.operations_manager_approved_at or submission.operations_manager_id)
                om_comments = submission.operations_manager_comments
                om_sig = form_data.get('operations_manager_signature') or form_data.get('opMan_signature') if isinstance(form_data, dict) else None
                om_sig_url = None
                if om_sig:
                    om_sig_url = om_sig.get('url') if isinstance(om_sig, dict) and om_sig.get('url') else (om_sig if isinstance(om_sig, str) and (om_sig.startswith('http') or om_sig.startswith('/') or om_sig.startswith('data:')) else None)
                
                if om_has_approved or om_comments or om_sig_url:
                    reviewers.append({
                        'role': 'Operations Manager',
                        'comments': om_comments,
                        'signature_url': om_sig_url,
                        'approved_at': submission.operations_manager_approved_at.isoformat() if submission.operations_manager_approved_at else None
                    })
                
                # Business Development
                bd_has_approved = bool(submission.business_dev_approved_at or submission.business_dev_id)
                bd_comments = submission.business_dev_comments
                bd_sig = form_data.get('business_dev_signature') if isinstance(form_data, dict) else None
                bd_sig_url = None
                if bd_sig:
                    bd_sig_url = bd_sig.get('url') if isinstance(bd_sig, dict) and bd_sig.get('url') else (bd_sig if isinstance(bd_sig, str) and (bd_sig.startswith('http') or bd_sig.startswith('/') or bd_sig.startswith('data:')) else None)
                
                if bd_has_approved or bd_comments or bd_sig_url:
                    reviewers.append({
                        'role': 'Business Development',
                        'comments': bd_comments,
                        'signature_url': bd_sig_url,
                        'approved_at': submission.business_dev_approved_at.isoformat() if submission.business_dev_approved_at else None
                    })
                
                # Procurement
                po_has_approved = bool(submission.procurement_approved_at or submission.procurement_id)
                po_comments = submission.procurement_comments
                po_sig = form_data.get('procurement_signature') if isinstance(form_data, dict) else None
                po_sig_url = None
                if po_sig:
                    po_sig_url = po_sig.get('url') if isinstance(po_sig, dict) and po_sig.get('url') else (po_sig if isinstance(po_sig, str) and (po_sig.startswith('http') or po_sig.startswith('/') or po_sig.startswith('data:')) else None)
                
                if po_has_approved or po_comments or po_sig_url:
                    reviewers.append({
                        'role': 'Procurement',
                        'comments': po_comments,
                        'signature_url': po_sig_url,
                        'approved_at': submission.procurement_approved_at.isoformat() if submission.procurement_approved_at else None
                    })
                
                # General Manager
                gm_has_approved = bool(submission.general_manager_approved_at or submission.general_manager_id)
                gm_comments = submission.general_manager_comments
                gm_sig = form_data.get('general_manager_signature') if isinstance(form_data, dict) else None
                gm_sig_url = None
                if gm_sig:
                    gm_sig_url = gm_sig.get('url') if isinstance(gm_sig, dict) and gm_sig.get('url') else (gm_sig if isinstance(gm_sig, str) and (gm_sig.startswith('http') or gm_sig.startswith('/') or gm_sig.startswith('data:')) else None)
                
                if gm_has_approved or gm_comments or gm_sig_url:
                    reviewers.append({
                        'role': 'General Manager',
                        'comments': gm_comments,
                        'signature_url': gm_sig_url,
                        'approved_at': submission.general_manager_approved_at.isoformat() if submission.general_manager_approved_at else None
                    })
                
                sub_dict['reviewers'] = reviewers
            
            result.append(sub_dict)
        
        return success_response({
            'submissions': result,
            'count': len(result)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting history submissions: {str(e)}", exc_info=True)
        return error_response('Failed to get submission history', status_code=500, error_code='DATABASE_ERROR')


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
            
            # Extract reviewer comments and signatures from form_data for display
            form_data = submission.form_data if submission.form_data else {}
            if isinstance(form_data, str):
                try:
                    import json
                    form_data = json.loads(form_data)
                except:
                    form_data = {}
            
            # Add reviewer information
            reviewers = []
            
            # Operations Manager
            # Only show if OM has actually approved (has approved_at) or has signature/comments
            # STRICT: Only use model field - never fallback to form_data to avoid mixing supervisor comments
            om_has_approved = bool(submission.operations_manager_approved_at or submission.operations_manager_id)
            # Only use the database field - do NOT fallback to form_data to prevent supervisor comments from appearing
            om_comments = submission.operations_manager_comments if submission.operations_manager_comments else None
            
            om_sig = form_data.get('operations_manager_signature') or form_data.get('opMan_signature') if isinstance(form_data, dict) else None
            om_sig_url = None
            if om_sig:
                om_sig_url = om_sig.get('url') if isinstance(om_sig, dict) and om_sig.get('url') else (om_sig if isinstance(om_sig, str) and (om_sig.startswith('http') or om_sig.startswith('/') or om_sig.startswith('data:')) else None)
            
            if om_has_approved or om_comments or om_sig_url:
                reviewers.append({
                    'role': 'Operations Manager',
                    'comments': om_comments,  # Use extracted comments (model field prioritized)
                    'signature_url': om_sig_url,
                    'approved_at': submission.operations_manager_approved_at.isoformat() if submission.operations_manager_approved_at else None
                })
            
            # Business Development
            # Prioritize model field over form_data
            bd_has_approved = bool(submission.business_dev_approved_at or submission.business_dev_id)
            bd_comments = submission.business_dev_comments
            if not bd_comments and isinstance(form_data, dict):
                form_bd_comments = form_data.get('business_dev_comments')
                # Verify it's not supervisor comments
                supervisor_comments = form_data.get('supervisor_comments', '')
                if form_bd_comments and form_bd_comments != supervisor_comments:
                    bd_comments = form_bd_comments
            
            bd_sig = form_data.get('business_dev_signature') if isinstance(form_data, dict) else None
            bd_sig_url = None
            if bd_sig:
                bd_sig_url = bd_sig.get('url') if isinstance(bd_sig, dict) and bd_sig.get('url') else (bd_sig if isinstance(bd_sig, str) and (bd_sig.startswith('http') or bd_sig.startswith('/') or bd_sig.startswith('data:')) else None)
            
            if bd_has_approved or bd_comments or bd_sig_url:
                reviewers.append({
                    'role': 'Business Development',
                    'comments': bd_comments,
                    'signature_url': bd_sig_url,
                    'approved_at': submission.business_dev_approved_at.isoformat() if submission.business_dev_approved_at else None
                })
            
            # Procurement
            # Prioritize model field over form_data
            po_has_approved = bool(submission.procurement_approved_at or submission.procurement_id)
            po_comments = submission.procurement_comments
            if not po_comments and isinstance(form_data, dict):
                form_po_comments = form_data.get('procurement_comments')
                # Verify it's not supervisor comments
                supervisor_comments = form_data.get('supervisor_comments', '')
                if form_po_comments and form_po_comments != supervisor_comments:
                    po_comments = form_po_comments
            
            po_sig = form_data.get('procurement_signature') if isinstance(form_data, dict) else None
            po_sig_url = None
            if po_sig:
                po_sig_url = po_sig.get('url') if isinstance(po_sig, dict) and po_sig.get('url') else (po_sig if isinstance(po_sig, str) and (po_sig.startswith('http') or po_sig.startswith('/') or po_sig.startswith('data:')) else None)
            
            if po_has_approved or po_comments or po_sig_url:
                reviewers.append({
                    'role': 'Procurement',
                    'comments': po_comments,
                    'signature_url': po_sig_url,
                    'approved_at': submission.procurement_approved_at.isoformat() if submission.procurement_approved_at else None
                })
            
            # General Manager
            # Prioritize model field over form_data
            gm_has_approved = bool(submission.general_manager_approved_at or submission.general_manager_id)
            gm_comments = submission.general_manager_comments
            if not gm_comments and isinstance(form_data, dict):
                form_gm_comments = form_data.get('general_manager_comments')
                # Verify it's not supervisor comments
                supervisor_comments = form_data.get('supervisor_comments', '')
                if form_gm_comments and form_gm_comments != supervisor_comments:
                    gm_comments = form_gm_comments
            
            gm_sig = form_data.get('general_manager_signature') if isinstance(form_data, dict) else None
            gm_sig_url = None
            if gm_sig:
                gm_sig_url = gm_sig.get('url') if isinstance(gm_sig, dict) and gm_sig.get('url') else (gm_sig if isinstance(gm_sig, str) and (gm_sig.startswith('http') or gm_sig.startswith('/') or gm_sig.startswith('data:')) else None)
            
            if gm_has_approved or gm_comments or gm_sig_url:
                reviewers.append({
                    'role': 'General Manager',
                    'comments': gm_comments,
                    'signature_url': gm_sig_url,
                    'approved_at': submission.general_manager_approved_at.isoformat() if submission.general_manager_approved_at else None
                })
            
            sub_dict['reviewers'] = reviewers
            
            # Extract photos and signatures from form_data for display
            photos = []
            supervisor_signature = None
            
            if isinstance(form_data, dict):
                # Extract photos - handle different module formats
                if submission.module_type in ['civil', 'cleaning']:
                    # Civil and Cleaning: photos might be in work_items or directly in form_data
                    if 'work_items' in form_data and isinstance(form_data['work_items'], list):
                        for item in form_data['work_items']:
                            if isinstance(item, dict) and 'photos' in item:
                                item_photos = item.get('photos', [])
                                if isinstance(item_photos, list):
                                    photos.extend(item_photos)
                    elif 'photo_urls' in form_data and isinstance(form_data['photo_urls'], list):
                        photos = form_data['photo_urls']
                    elif 'photos' in form_data and isinstance(form_data['photos'], list):
                        photos = form_data['photos']
                elif submission.module_type in ['hvac', 'hvac_mep']:
                    # HVAC: photos are in items array
                    if 'items' in form_data and isinstance(form_data['items'], list):
                        for item in form_data['items']:
                            if isinstance(item, dict) and 'photos' in item:
                                item_photos = item.get('photos', [])
                                if isinstance(item_photos, list):
                                    photos.extend(item_photos)
                
                # Extract supervisor signature
                supervisor_sig = form_data.get('supervisor_signature') or form_data.get('supervisorSignature')
                if supervisor_sig:
                    if isinstance(supervisor_sig, dict):
                        supervisor_signature = supervisor_sig.get('url') or supervisor_sig.get('path')
                    elif isinstance(supervisor_sig, str) and (supervisor_sig.startswith('http') or supervisor_sig.startswith('/') or supervisor_sig.startswith('data:')):
                        supervisor_signature = supervisor_sig
            
            # Normalize photo URLs - extract URLs from photo objects
            photo_urls = []
            for photo in photos[:10]:  # Limit to first 10 for preview
                if isinstance(photo, dict):
                    url = photo.get('url') or photo.get('path')
                    if url:
                        photo_urls.append(url)
                elif isinstance(photo, str) and (photo.startswith('http') or photo.startswith('/') or photo.startswith('data:')):
                    photo_urls.append(photo)
            
            sub_dict['photos'] = photo_urls
            sub_dict['photo_count'] = len(photos)  # Total count
            sub_dict['supervisor_signature'] = supervisor_signature
            
            submissions_list.append(sub_dict)
        
        return success_response({
            'submissions': submissions_list,
            'count': len(submissions_list)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting my submissions: {str(e)}", exc_info=True)
        return error_response('Failed to get submissions', status_code=500, error_code='DATABASE_ERROR')


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


@workflow_bp.route('/submissions/<submission_id>/approve-supervisor', methods=['POST'])
@jwt_required()
def approve_supervisor_resubmission(submission_id):
    """Supervisor resubmits/approves their own submission (allows editing and regeneration)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        data = request.get_json() or {}
        
        if not user:
            return error_response('User not found', status_code=404, error_code='NOT_FOUND')
        
        if user.designation != 'supervisor' and user.role != 'admin':
            return error_response('Only supervisors can resubmit their own forms', 
                                status_code=403, error_code='INVALID_DESIGNATION')
        
        submission = Submission.query.filter_by(submission_id=submission_id).first()
        if not submission:
            return error_response('Submission not found', status_code=404, error_code='NOT_FOUND')
        
        # Verify this is the supervisor's own submission
        is_own_submission = (
            (hasattr(submission, 'supervisor_id') and submission.supervisor_id == user.id) or
            (submission.user_id == user.id)
        )
        
        if not is_own_submission and user.role != 'admin':
            return error_response('You can only resubmit your own submissions', 
                                status_code=403, error_code='UNAUTHORIZED')
        
        # Allow resubmission if status is submitted/rejected OR operations_manager_review (but not yet approved by OM)
        if submission.workflow_status not in ['submitted', 'rejected', None] and not (
            submission.workflow_status == 'operations_manager_review' and not submission.operations_manager_approved_at
        ):
            return error_response('Submission cannot be resubmitted at this stage', 
                                status_code=400, error_code='INVALID_STATUS')
        
        # Extract data
        comments = data.get('comments', '') or data.get('supervisor_comments', '')
        signature = data.get('signature', '') or data.get('supervisor_signature', '')
        verified = data.get('verified', False)
        form_data_updates = data.get('form_data', {})
        
        # Update form_data
        form_data = submission.form_data if submission.form_data else {}
        if isinstance(form_data, str):
            try:
                import json
                form_data = json.loads(form_data)
            except:
                form_data = {}
        
        # Preserve existing reviewer data (OM, BD, PO, GM) before updating
        existing_om_comments = form_data.get('operations_manager_comments')
        existing_om_signature = form_data.get('operations_manager_signature') or form_data.get('opMan_signature')
        existing_bd_comments = form_data.get('business_dev_comments')
        existing_bd_signature = form_data.get('business_dev_signature')
        existing_procurement_comments = form_data.get('procurement_comments')
        existing_procurement_signature = form_data.get('procurement_signature')
        existing_gm_comments = form_data.get('general_manager_comments')
        existing_gm_signature = form_data.get('general_manager_signature')
        
        # Update with new form_data
        if form_data_updates:
            form_data.update(form_data_updates)
        
        # Update supervisor data
        if comments:
            form_data['supervisor_comments'] = comments
            submission.supervisor_comments = comments
        
        if signature:
            # Process and save supervisor signature
            save_signature_dataurl, get_paths_fn, _ = get_module_functions(submission.module_type)
            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
            
            sig_filename, sig_path, sig_url = save_signature_dataurl(
                signature, 
                UPLOADS_DIR, 
                prefix="supervisor_sig"
            )
            
            if sig_url:
                form_data['supervisor_signature'] = {
                    'url': sig_url,
                    'path': sig_path,
                    'saved': sig_filename,
                    'is_cloud': sig_url.startswith('http') and 'cloudinary' in sig_url
                }
                current_app.logger.info(f"✅ Saved supervisor signature for resubmission {submission_id}")
        
        if verified:
            form_data['supervisor_verified'] = True
        
        # Restore reviewer data if it was lost
        if existing_om_comments and not form_data.get('operations_manager_comments'):
            form_data['operations_manager_comments'] = existing_om_comments
        if existing_om_signature and not form_data.get('operations_manager_signature') and not form_data.get('opMan_signature'):
            form_data['operations_manager_signature'] = existing_om_signature
        if existing_bd_comments and not form_data.get('business_dev_comments'):
            form_data['business_dev_comments'] = existing_bd_comments
        if existing_bd_signature and not form_data.get('business_dev_signature'):
            form_data['business_dev_signature'] = existing_bd_signature
        if existing_procurement_comments and not form_data.get('procurement_comments'):
            form_data['procurement_comments'] = existing_procurement_comments
        if existing_procurement_signature and not form_data.get('procurement_signature'):
            form_data['procurement_signature'] = existing_procurement_signature
        if existing_gm_comments and not form_data.get('general_manager_comments'):
            form_data['general_manager_comments'] = existing_gm_comments
        if existing_gm_signature and not form_data.get('general_manager_signature'):
            form_data['general_manager_signature'] = existing_gm_signature
        
        submission.form_data = form_data
        submission.supervisor_id = user.id
        
        # Reset workflow status to submitted (or operations_manager_review if OM was already reviewing)
        if submission.workflow_status == 'operations_manager_review' and not submission.operations_manager_approved_at:
            # Keep at operations_manager_review if OM hasn't approved yet
            submission.workflow_status = 'operations_manager_review'
        else:
            # Reset to submitted for fresh review
            submission.workflow_status = 'submitted'
        
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Regenerate PDF and Excel documents with updated data
        job_id = None
        try:
            from common.db_utils import create_job_db
            from app.models import Job
            _, get_paths_fn, process_job_fn = get_module_functions(submission.module_type)
            
            # Delete old jobs to force regeneration
            old_jobs = Job.query.filter_by(submission_id=submission.id).all()
            for old_job in old_jobs:
                db.session.delete(old_job)
            db.session.commit()
            
            # Create new job for regeneration
            new_job = create_job_db(submission)
            job_id = new_job.job_id
            
            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
            
            if EXECUTOR:
                EXECUTOR.submit(
                    process_job_fn,
                    submission.submission_id,
                    job_id,
                    current_app.config,
                    current_app._get_current_object()
                )
                current_app.logger.info(f"✅ Regeneration job {job_id} queued for supervisor resubmission - submission {submission_id} ({submission.module_type})")
            else:
                current_app.logger.error("ThreadPoolExecutor not available for document regeneration")
        except Exception as regen_err:
            current_app.logger.error(f"Error queuing regeneration job after supervisor resubmission: {regen_err}", exc_info=True)
        
        log_audit(user_id, 'supervisor_resubmitted', 'submission', submission_id, {
            'comments': comments,
            'has_signature': bool(signature),
            'verified': verified
        })
        
        return success_response({
            'submission': submission.to_dict(),
            'message': 'Form resubmitted successfully. PDF and Excel reports are being regenerated with your updates.' + (' Documents are being regenerated.' if job_id else ''),
            'job_id': job_id,
            'regenerating': bool(job_id)
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in supervisor resubmission: {str(e)}", exc_info=True)
        return error_response('Failed to resubmit submission', status_code=500, error_code='DATABASE_ERROR')


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
        
        # Log incoming data for debugging
        current_app.logger.info(f"🔍 Operations Manager approval request for submission {submission_id}:")
        current_app.logger.info(f"  - Comments provided: {bool(comments and comments.strip())} (length: {len(comments) if comments else 0})")
        current_app.logger.info(f"  - Signature provided: {bool(signature and signature.strip())} (type: {type(signature).__name__}, length: {len(str(signature)) if signature else 0})")
        if signature and signature.strip():
            current_app.logger.info(f"  - Signature preview: {str(signature)[:50]}...")
        current_app.logger.info(f"  - form_data_updates keys: {list(form_data_updates.keys())[:20] if form_data_updates else 'none'}")
        
        # Check if signature is in form_data_updates (might be sent there instead of top-level)
        if not signature or not signature.strip():
            if form_data_updates.get('opMan_signature'):
                signature = form_data_updates.get('opMan_signature')
                current_app.logger.info(f"✅ Found Operations Manager signature in form_data_updates.opMan_signature")
            elif form_data_updates.get('operations_manager_signature'):
                signature = form_data_updates.get('operations_manager_signature')
                current_app.logger.info(f"✅ Found Operations Manager signature in form_data_updates.operations_manager_signature")
        
        # Update submission
        submission.operations_manager_id = user.id
        submission.operations_manager_comments = comments
        submission.operations_manager_approved_at = datetime.utcnow()
        submission.workflow_status = 'operations_manager_approved'
        
        # Update form_data if provided - but preserve existing Operations Manager data
        form_data = submission.form_data if submission.form_data else {}
        if isinstance(form_data, str):
            try:
                import json
                form_data = json.loads(form_data)
            except:
                form_data = {}
        
        # Preserve existing Operations Manager data before updating (in case form_data_updates overwrites it)
        existing_om_comments = form_data.get('operations_manager_comments')
        existing_om_signature = form_data.get('operations_manager_signature') or form_data.get('opMan_signature')
        
        if form_data_updates:
            # Merge form_data_updates, but don't overwrite Operations Manager data if it already exists
            # (unless new data is being provided)
            form_data.update(form_data_updates)
            current_app.logger.info(f"✅ Updated form_data with form_data_updates for submission {submission_id}")
        
        # Always save Operations Manager comments to form_data for next reviewers
        # Use new comments if provided, otherwise preserve existing
        if comments and comments.strip():
            form_data['operations_manager_comments'] = comments
            current_app.logger.info(f"✅ Saved Operations Manager comments to form_data for submission {submission_id}")
        elif existing_om_comments:
            # Preserve existing comments if no new ones provided
            form_data['operations_manager_comments'] = existing_om_comments
            current_app.logger.info(f"✅ Preserved existing Operations Manager comments in form_data")
        
        # Process and upload Operations Manager signature if provided
        if signature and signature.strip() and signature.startswith('data:image'):
            # Signature is a data URL - need to upload it to cloud storage
            try:
                save_sig_fn, get_paths_fn, _ = get_module_functions(submission.module_type)
                GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
                
                fname, fpath, url = save_sig_fn(signature, UPLOADS_DIR, prefix="opman_sig")
                if url:
                    # Save as object format for consistency with other signatures
                    form_data['operations_manager_signature'] = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
                    current_app.logger.info(f"✅ Operations Manager signature uploaded and saved to form_data (URL: {url[:80]}...)")
                else:
                    # Upload failed, save as data URL string as fallback
                    form_data['operations_manager_signature'] = signature
                    current_app.logger.warning(f"⚠️ Operations Manager signature upload failed, saving as data URL for submission {submission_id}")
            except Exception as e:
                current_app.logger.error(f"❌ Error uploading Operations Manager signature: {e}")
                import traceback
                current_app.logger.error(traceback.format_exc())
                # Fallback: save as data URL string
                form_data['operations_manager_signature'] = signature
                current_app.logger.warning(f"⚠️ Saving Operations Manager signature as data URL due to upload error")
        elif signature and signature.strip():
            # Signature is already a URL or object format
            # Handle both string URLs and object formats
            if isinstance(signature, dict):
                form_data['operations_manager_signature'] = signature
            elif isinstance(signature, str):
                form_data['operations_manager_signature'] = signature
            current_app.logger.info(f"✅ Saved Operations Manager signature to form_data (already processed format)")
        elif existing_om_signature:
            # Preserve existing signature if no new one provided
            form_data['operations_manager_signature'] = existing_om_signature
            current_app.logger.info(f"✅ Preserved existing Operations Manager signature in form_data")
        else:
            current_app.logger.warning(f"⚠️ No Operations Manager signature provided for submission {submission_id}")
            current_app.logger.warning(f"  - signature value: {repr(signature) if signature else 'None'}")
            current_app.logger.warning(f"  - existing_om_signature: {repr(existing_om_signature) if existing_om_signature else 'None'}")
        
        # Log final form_data keys for debugging
        current_app.logger.info(f"🔍 Final form_data keys after Operations Manager approval: {list(form_data.keys())[:30]}")
        current_app.logger.info(f"  - operations_manager_comments in form_data: {bool(form_data.get('operations_manager_comments'))}")
        current_app.logger.info(f"  - operations_manager_signature in form_data: {bool(form_data.get('operations_manager_signature'))}")
        if form_data.get('operations_manager_signature'):
            sig_val = form_data.get('operations_manager_signature')
            if isinstance(sig_val, dict):
                current_app.logger.info(f"  - operations_manager_signature type: dict, url: {sig_val.get('url', 'N/A')[:80] if sig_val.get('url') else 'N/A'}")
            else:
                current_app.logger.info(f"  - operations_manager_signature type: {type(sig_val).__name__}, preview: {str(sig_val)[:80] if sig_val else 'N/A'}")
        
        submission.form_data = form_data
        
        # Move to BD/Procurement review
        submission.workflow_status = 'bd_procurement_review'
        submission.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Regenerate documents for all modules (to include Operations Manager comments/signature)
        # This ensures Supervisor and all subsequent reviewers see the updated form with OM's changes
        job_id = None
        try:
            from common.db_utils import create_job_db
            from app.models import Job
            _, get_paths_fn, process_job_fn = get_module_functions(submission.module_type)
            
            # Delete old jobs to force regeneration
            old_jobs = Job.query.filter_by(submission_id=submission.id).all()
            for old_job in old_jobs:
                db.session.delete(old_job)
            db.session.commit()
            
            # Create new job for regeneration
            new_job = create_job_db(submission)
            job_id = new_job.job_id
            
            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
            
            if EXECUTOR:
                EXECUTOR.submit(
                    process_job_fn,
                    submission.submission_id,
                    job_id,
                    current_app.config,
                    current_app._get_current_object()
                )
                current_app.logger.info(f"✅ Regeneration job {job_id} queued for Operations Manager approval - submission {submission_id} ({submission.module_type})")
            else:
                current_app.logger.error("ThreadPoolExecutor not available for document regeneration")
        except Exception as regen_err:
            current_app.logger.error(f"Error queuing regeneration job after OM approval: {regen_err}", exc_info=True)
        
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
            return error_response('Already approved', 
                                status_code=400, error_code='ALREADY_APPROVED')
        
        # Extract data
        comments = data.get('comments', '')
        signature = data.get('signature', '')
        form_data_updates = data.get('form_data', {})
        
        # Update submission
        submission.business_dev_id = user.id
        submission.business_dev_comments = comments
        submission.business_dev_approved_at = datetime.utcnow()
        
        # Update form_data if provided - but preserve Operations Manager and other reviewer data
        form_data = submission.form_data if submission.form_data else {}
        if isinstance(form_data, str):
            try:
                import json
                form_data = json.loads(form_data)
            except:
                form_data = {}
        
        # CRITICAL: Preserve Operations Manager data before updating (BD's form_data_updates might not include it)
        existing_om_comments = form_data.get('operations_manager_comments')
        existing_om_signature = form_data.get('operations_manager_signature') or form_data.get('opMan_signature')
        current_app.logger.info(f"🔍 BD Approval: Preserving Operations Manager data before update:")
        current_app.logger.info(f"  - Existing OM comments: {bool(existing_om_comments)}")
        current_app.logger.info(f"  - Existing OM signature: {bool(existing_om_signature)}")
        
        # Also preserve other reviewer data
        existing_supervisor_comments = form_data.get('supervisor_comments')
        existing_supervisor_signature = form_data.get('supervisor_signature')
        
        if form_data_updates:
            # Merge form_data_updates, but preserve critical reviewer data
            form_data.update(form_data_updates)
            current_app.logger.info(f"✅ Updated form_data with BD's form_data_updates for submission {submission_id}")
        
        # Restore Operations Manager data if it was lost during update
        if existing_om_comments and not form_data.get('operations_manager_comments'):
            form_data['operations_manager_comments'] = existing_om_comments
            current_app.logger.info(f"✅ Restored Operations Manager comments after BD update")
        if existing_om_signature and not form_data.get('operations_manager_signature') and not form_data.get('opMan_signature'):
            form_data['operations_manager_signature'] = existing_om_signature
            current_app.logger.info(f"✅ Restored Operations Manager signature after BD update")
        
        # Restore supervisor data if it was lost (shouldn't happen, but be safe)
        if existing_supervisor_comments and not form_data.get('supervisor_comments'):
            form_data['supervisor_comments'] = existing_supervisor_comments
        if existing_supervisor_signature and not form_data.get('supervisor_signature'):
            form_data['supervisor_signature'] = existing_supervisor_signature
        
        # Always save BD comments and signature to form_data for next reviewers
        if comments:
            form_data['business_dev_comments'] = comments
            current_app.logger.info(f"✅ Saved BD comments to form_data")
        if signature:
            # Process and upload BD signature if it's a data URL
            if signature and signature.strip() and signature.startswith('data:image'):
                try:
                    save_sig_fn, get_paths_fn, _ = get_module_functions(submission.module_type)
                    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
                    
                    fname, fpath, url = save_sig_fn(signature, UPLOADS_DIR, prefix="bd_sig")
                    if url:
                        form_data['business_dev_signature'] = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
                        current_app.logger.info(f"✅ BD signature uploaded and saved to form_data (URL: {url[:80]}...)")
                    else:
                        form_data['business_dev_signature'] = signature
                        current_app.logger.warning(f"⚠️ BD signature upload failed, saving as data URL")
                except Exception as e:
                    current_app.logger.error(f"❌ Error uploading BD signature: {e}")
                    form_data['business_dev_signature'] = signature
            else:
                form_data['business_dev_signature'] = signature
                current_app.logger.info(f"✅ Saved BD signature to form_data")
        
        # Log final state to verify Operations Manager data is preserved
        current_app.logger.info(f"🔍 BD Approval: Final form_data state:")
        current_app.logger.info(f"  - operations_manager_comments: {bool(form_data.get('operations_manager_comments'))}")
        current_app.logger.info(f"  - operations_manager_signature: {bool(form_data.get('operations_manager_signature'))}")
        current_app.logger.info(f"  - business_dev_comments: {bool(form_data.get('business_dev_comments'))}")
        current_app.logger.info(f"  - business_dev_signature: {bool(form_data.get('business_dev_signature'))}")
        
        submission.form_data = form_data
        
        # Check if both BD and Procurement have approved
        if submission.procurement_approved_at:
            submission.workflow_status = 'general_manager_review'
            message = 'Approved successfully. Both BD and Procurement approved. Forwarded to General Manager.'
        else:
            message = 'Approved successfully. Waiting for Procurement approval.'
        
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Regenerate documents for all modules (to include BD comments/signature)
        # This ensures Supervisor, OM, and all subsequent reviewers see the updated form with BD's changes
        job_id = None
        try:
            from common.db_utils import create_job_db
            from app.models import Job
            _, get_paths_fn, process_job_fn = get_module_functions(submission.module_type)

            # Delete old jobs to force regeneration
            old_jobs = Job.query.filter_by(submission_id=submission.id).all()
            for old_job in old_jobs:
                db.session.delete(old_job)
            db.session.commit()

            # Create new job for regeneration
            new_job = create_job_db(submission)
            job_id = new_job.job_id

            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
            if EXECUTOR:
                EXECUTOR.submit(
                    process_job_fn,
                    submission.submission_id,
                    job_id,
                    current_app.config,
                    current_app._get_current_object()
                )
                current_app.logger.info(f"✅ Regeneration job {job_id} queued for BD approval - submission {submission_id} ({submission.module_type})")
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
            return error_response('Already approved', 
                                status_code=400, error_code='ALREADY_APPROVED')
        
        # Extract data
        comments = data.get('comments', '')
        signature = data.get('signature', '')
        form_data_updates = data.get('form_data', {})
        
        # Update submission
        submission.procurement_id = user.id
        submission.procurement_comments = comments
        submission.procurement_approved_at = datetime.utcnow()
        
        # Update form_data if provided - but preserve Operations Manager and Business Development data
        form_data = submission.form_data if submission.form_data else {}
        if isinstance(form_data, str):
            try:
                import json
                form_data = json.loads(form_data)
            except:
                form_data = {}
        
        # CRITICAL: Preserve Operations Manager and Business Development data before updating
        existing_om_comments = form_data.get('operations_manager_comments')
        existing_om_signature = form_data.get('operations_manager_signature') or form_data.get('opMan_signature')
        existing_bd_comments = form_data.get('business_dev_comments')
        existing_bd_signature = form_data.get('business_dev_signature')
        current_app.logger.info(f"🔍 Procurement Approval: Preserving reviewer data before update:")
        current_app.logger.info(f"  - Existing OM comments: {bool(existing_om_comments)}")
        current_app.logger.info(f"  - Existing OM signature: {bool(existing_om_signature)}")
        current_app.logger.info(f"  - Existing BD comments: {bool(existing_bd_comments)}")
        current_app.logger.info(f"  - Existing BD signature: {bool(existing_bd_signature)}")
        
        if form_data_updates:
            form_data.update(form_data_updates)
            current_app.logger.info(f"✅ Updated form_data with Procurement's form_data_updates for submission {submission_id}")
        
        # Restore Operations Manager data if it was lost during update
        if existing_om_comments and not form_data.get('operations_manager_comments'):
            form_data['operations_manager_comments'] = existing_om_comments
            current_app.logger.info(f"✅ Restored Operations Manager comments after Procurement update")
        if existing_om_signature and not form_data.get('operations_manager_signature') and not form_data.get('opMan_signature'):
            form_data['operations_manager_signature'] = existing_om_signature
            current_app.logger.info(f"✅ Restored Operations Manager signature after Procurement update")
        
        # Restore Business Development data if it was lost during update
        if existing_bd_comments and not form_data.get('business_dev_comments'):
            form_data['business_dev_comments'] = existing_bd_comments
            current_app.logger.info(f"✅ Restored Business Development comments after Procurement update")
        if existing_bd_signature and not form_data.get('business_dev_signature'):
            form_data['business_dev_signature'] = existing_bd_signature
            current_app.logger.info(f"✅ Restored Business Development signature after Procurement update")
        
        # Always save Procurement comments and signature to form_data for next reviewers
        if comments:
            form_data['procurement_comments'] = comments
            current_app.logger.info(f"✅ Saved Procurement comments to form_data")
        if signature:
            # Process and upload Procurement signature if it's a data URL
            if signature and signature.strip() and signature.startswith('data:image'):
                try:
                    save_sig_fn, get_paths_fn, _ = get_module_functions(submission.module_type)
                    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
                    
                    fname, fpath, url = save_sig_fn(signature, UPLOADS_DIR, prefix="procurement_sig")
                    if url:
                        form_data['procurement_signature'] = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
                        current_app.logger.info(f"✅ Procurement signature uploaded and saved to form_data (URL: {url[:80]}...)")
                    else:
                        form_data['procurement_signature'] = signature
                        current_app.logger.warning(f"⚠️ Procurement signature upload failed, saving as data URL")
                except Exception as e:
                    current_app.logger.error(f"❌ Error uploading Procurement signature: {e}")
                    form_data['procurement_signature'] = signature
            else:
                form_data['procurement_signature'] = signature
                current_app.logger.info(f"✅ Saved Procurement signature to form_data")
        
        # Log final state to verify BD data is preserved
        current_app.logger.info(f"🔍 Procurement Approval: Final form_data state:")
        current_app.logger.info(f"  - operations_manager_comments: {bool(form_data.get('operations_manager_comments'))}")
        current_app.logger.info(f"  - operations_manager_signature: {bool(form_data.get('operations_manager_signature'))}")
        current_app.logger.info(f"  - business_dev_comments: {bool(form_data.get('business_dev_comments'))}")
        current_app.logger.info(f"  - business_dev_signature: {bool(form_data.get('business_dev_signature'))}")
        current_app.logger.info(f"  - procurement_comments: {bool(form_data.get('procurement_comments'))}")
        current_app.logger.info(f"  - procurement_signature: {bool(form_data.get('procurement_signature'))}")
        
        submission.form_data = form_data
        
        # Check if both BD and Procurement have approved
        if submission.business_dev_approved_at:
            submission.workflow_status = 'general_manager_review'
            message = 'Approved successfully. Both BD and Procurement approved. Forwarded to General Manager.'
        else:
            message = 'Approved successfully. Waiting for Business Development approval.'
        
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Regenerate documents for all modules (to include Procurement comments/signature)
        # This ensures Supervisor, OM, BD, and all subsequent reviewers see the updated form with Procurement's changes
        job_id = None
        try:
            from common.db_utils import create_job_db
            from app.models import Job
            _, get_paths_fn, process_job_fn = get_module_functions(submission.module_type)

            # Delete old jobs to force regeneration
            old_jobs = Job.query.filter_by(submission_id=submission.id).all()
            for old_job in old_jobs:
                db.session.delete(old_job)
            db.session.commit()

            # Create new job for regeneration
            new_job = create_job_db(submission)
            job_id = new_job.job_id

            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
            if EXECUTOR:
                EXECUTOR.submit(
                    process_job_fn,
                    submission.submission_id,
                    job_id,
                    current_app.config,
                    current_app._get_current_object()
                )
                current_app.logger.info(f"✅ Regeneration job {job_id} queued for Procurement approval - submission {submission_id} ({submission.module_type})")
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
        
        # Update form_data if provided - but preserve Operations Manager and other reviewer data
        form_data = submission.form_data if submission.form_data else {}
        if isinstance(form_data, str):
            try:
                import json
                form_data = json.loads(form_data)
            except:
                form_data = {}
        
        # CRITICAL: Preserve all reviewer data before updating (OM, BD, Procurement)
        existing_om_comments = form_data.get('operations_manager_comments')
        existing_om_signature = form_data.get('operations_manager_signature') or form_data.get('opMan_signature')
        existing_bd_comments = form_data.get('business_dev_comments')
        existing_bd_signature = form_data.get('business_dev_signature')
        existing_procurement_comments = form_data.get('procurement_comments')
        existing_procurement_signature = form_data.get('procurement_signature')
        
        current_app.logger.info(f"🔍 General Manager Approval: Preserving reviewer data before update:")
        current_app.logger.info(f"  - Existing OM comments: {bool(existing_om_comments)}")
        current_app.logger.info(f"  - Existing OM signature: {bool(existing_om_signature)}")
        current_app.logger.info(f"  - Existing BD comments: {bool(existing_bd_comments)}")
        current_app.logger.info(f"  - Existing BD signature: {bool(existing_bd_signature)}")
        current_app.logger.info(f"  - Existing Procurement comments: {bool(existing_procurement_comments)}")
        current_app.logger.info(f"  - Existing Procurement signature: {bool(existing_procurement_signature)}")
        
        if form_data_updates:
            form_data.update(form_data_updates)
            current_app.logger.info(f"✅ Updated form_data with General Manager's form_data_updates for submission {submission_id}")
        
        # Restore Operations Manager data if it was lost during update
        if existing_om_comments and not form_data.get('operations_manager_comments'):
            form_data['operations_manager_comments'] = existing_om_comments
            current_app.logger.info(f"✅ Restored Operations Manager comments after General Manager update")
        if existing_om_signature and not form_data.get('operations_manager_signature') and not form_data.get('opMan_signature'):
            form_data['operations_manager_signature'] = existing_om_signature
            current_app.logger.info(f"✅ Restored Operations Manager signature after General Manager update")
        
        # Restore Business Development data if it was lost during update
        if existing_bd_comments and not form_data.get('business_dev_comments'):
            form_data['business_dev_comments'] = existing_bd_comments
            current_app.logger.info(f"✅ Restored Business Development comments after General Manager update")
        if existing_bd_signature and not form_data.get('business_dev_signature'):
            form_data['business_dev_signature'] = existing_bd_signature
            current_app.logger.info(f"✅ Restored Business Development signature after General Manager update")
        
        # Restore Procurement data if it was lost during update
        if existing_procurement_comments and not form_data.get('procurement_comments'):
            form_data['procurement_comments'] = existing_procurement_comments
            current_app.logger.info(f"✅ Restored Procurement comments after General Manager update")
        if existing_procurement_signature and not form_data.get('procurement_signature'):
            form_data['procurement_signature'] = existing_procurement_signature
            current_app.logger.info(f"✅ Restored Procurement signature after General Manager update")
        
        # Always save General Manager comments and signature to form_data
        if comments:
            form_data['general_manager_comments'] = comments
            current_app.logger.info(f"✅ Saved General Manager comments to form_data")
        if signature:
            # Process and upload General Manager signature if it's a data URL
            if signature and signature.strip() and signature.startswith('data:image'):
                try:
                    save_sig_fn, get_paths_fn, _ = get_module_functions(submission.module_type)
                    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
                    
                    fname, fpath, url = save_sig_fn(signature, UPLOADS_DIR, prefix="gm_sig")
                    if url:
                        form_data['general_manager_signature'] = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
                        current_app.logger.info(f"✅ General Manager signature uploaded and saved to form_data (URL: {url[:80]}...)")
                    else:
                        form_data['general_manager_signature'] = signature
                        current_app.logger.warning(f"⚠️ General Manager signature upload failed, saving as data URL")
                except Exception as e:
                    current_app.logger.error(f"❌ Error uploading General Manager signature: {e}")
                    form_data['general_manager_signature'] = signature
            else:
                form_data['general_manager_signature'] = signature
                current_app.logger.info(f"✅ Saved General Manager signature to form_data")
        
        # Log final state
        current_app.logger.info(f"🔍 General Manager Approval: Final form_data state:")
        current_app.logger.info(f"  - operations_manager_comments: {bool(form_data.get('operations_manager_comments'))}")
        current_app.logger.info(f"  - operations_manager_signature: {bool(form_data.get('operations_manager_signature'))}")
        current_app.logger.info(f"  - business_dev_comments: {bool(form_data.get('business_dev_comments'))}")
        current_app.logger.info(f"  - business_dev_signature: {bool(form_data.get('business_dev_signature'))}")
        current_app.logger.info(f"  - procurement_comments: {bool(form_data.get('procurement_comments'))}")
        current_app.logger.info(f"  - procurement_signature: {bool(form_data.get('procurement_signature'))}")
        current_app.logger.info(f"  - general_manager_comments: {bool(form_data.get('general_manager_comments'))}")
        current_app.logger.info(f"  - general_manager_signature: {bool(form_data.get('general_manager_signature'))}")
        
        submission.form_data = form_data
        submission.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Regenerate documents for all modules (to include General Manager comments/signature and all previous reviewers)
        # This ensures all users (Supervisor, OM, BD, Procurement) see the final version with all signatures
        job_id = None
        try:
            from common.db_utils import create_job_db
            from app.models import Job
            _, get_paths_fn, process_job_fn = get_module_functions(submission.module_type)
            
            # Delete old jobs to force regeneration
            old_jobs = Job.query.filter_by(submission_id=submission.id).all()
            for old_job in old_jobs:
                db.session.delete(old_job)
            db.session.commit()
            
            # Create new job for regeneration
            new_job = create_job_db(submission)
            job_id = new_job.job_id
            
            GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
            
            if EXECUTOR:
                EXECUTOR.submit(
                    process_job_fn,
                    submission.submission_id,
                    job_id,
                    current_app.config,
                    current_app._get_current_object()
                )
                current_app.logger.info(f"✅ Regeneration job {job_id} queued for General Manager approval - submission {submission_id} ({submission.module_type})")
            else:
                current_app.logger.error("ThreadPoolExecutor not available for document regeneration")
        except Exception as regen_err:
            current_app.logger.error(f"Error queuing regeneration job after GM approval: {regen_err}", exc_info=True)
        
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
            # Get existing form_data to preserve Operations Manager and other reviewer data
            existing_form_data = submission.form_data if submission.form_data else {}
            if isinstance(existing_form_data, str):
                try:
                    import json
                    existing_form_data = json.loads(existing_form_data)
                except:
                    existing_form_data = {}
            
            # CRITICAL: Preserve all reviewer data before update (OM, BD, Procurement, Supervisor)
            existing_om_comments = existing_form_data.get('operations_manager_comments')
            existing_om_signature = existing_form_data.get('operations_manager_signature') or existing_form_data.get('opMan_signature')
            existing_bd_comments = existing_form_data.get('business_dev_comments')
            existing_bd_signature = existing_form_data.get('business_dev_signature')
            existing_procurement_comments = existing_form_data.get('procurement_comments')
            existing_procurement_signature = existing_form_data.get('procurement_signature')
            existing_supervisor_comments = existing_form_data.get('supervisor_comments')
            existing_supervisor_signature = existing_form_data.get('supervisor_signature')
            
            # If full form_data is provided, use it directly (like admin endpoint)
            form_data = data['form_data'].copy() if isinstance(data['form_data'], dict) else data['form_data']
            
            # Ensure all reviewer data is preserved if not in new form_data
            if isinstance(form_data, dict):
                # Preserve Operations Manager data
                if existing_om_comments and not form_data.get('operations_manager_comments'):
                    form_data['operations_manager_comments'] = existing_om_comments
                    current_app.logger.info(f"✅ Preserved Operations Manager comments in update_submission for {submission_id}")
                if existing_om_signature and not form_data.get('operations_manager_signature') and not form_data.get('opMan_signature'):
                    form_data['operations_manager_signature'] = existing_om_signature
                    current_app.logger.info(f"✅ Preserved Operations Manager signature in update_submission for {submission_id}")
                
                # Preserve Business Development data
                if existing_bd_comments and not form_data.get('business_dev_comments'):
                    form_data['business_dev_comments'] = existing_bd_comments
                    current_app.logger.info(f"✅ Preserved Business Development comments in update_submission for {submission_id}")
                if existing_bd_signature and not form_data.get('business_dev_signature'):
                    form_data['business_dev_signature'] = existing_bd_signature
                    current_app.logger.info(f"✅ Preserved Business Development signature in update_submission for {submission_id}")
                
                # Preserve Procurement data (unless Procurement is the one updating)
                if user.designation != 'procurement':
                    if existing_procurement_comments and not form_data.get('procurement_comments'):
                        form_data['procurement_comments'] = existing_procurement_comments
                        current_app.logger.info(f"✅ Preserved Procurement comments in update_submission for {submission_id}")
                    if existing_procurement_signature and not form_data.get('procurement_signature'):
                        form_data['procurement_signature'] = existing_procurement_signature
                        current_app.logger.info(f"✅ Preserved Procurement signature in update_submission for {submission_id}")
                
                # Preserve Supervisor data
                if existing_supervisor_comments and not form_data.get('supervisor_comments'):
                    form_data['supervisor_comments'] = existing_supervisor_comments
                    current_app.logger.info(f"✅ Preserved Supervisor comments in update_submission for {submission_id}")
                if existing_supervisor_signature and not form_data.get('supervisor_signature'):
                    form_data['supervisor_signature'] = existing_supervisor_signature
                    current_app.logger.info(f"✅ Preserved Supervisor signature in update_submission for {submission_id}")
            
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
                
                # Process supervisor signature - upload if it's a new data URL
                supervisor_sig_data = form_data.get('supervisor_signature', '')
                if supervisor_sig_data and isinstance(supervisor_sig_data, str) and supervisor_sig_data.startswith('data:image'):
                    # New signature provided as data URL - need to upload it
                    try:
                        save_sig_fn, get_paths_fn, _ = get_module_functions(submission.module_type)
                        GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
                        
                        fname, fpath, url = save_sig_fn(supervisor_sig_data, UPLOADS_DIR, prefix="supervisor_sig")
                        if url:
                            form_data['supervisor_signature'] = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
                            current_app.logger.info(f"✅ Supervisor signature uploaded and saved for submission {submission_id}")
                        else:
                            current_app.logger.warning(f"⚠️ Supervisor signature upload failed for submission {submission_id}")
                            # Preserve old signature if upload fails
                            old_form_data = submission.form_data if submission.form_data else {}
                            if old_form_data.get('supervisor_signature'):
                                form_data['supervisor_signature'] = old_form_data['supervisor_signature']
                    except Exception as e:
                        current_app.logger.error(f"❌ Error uploading supervisor signature: {e}")
                        # Preserve old signature if upload fails
                        old_form_data = submission.form_data if submission.form_data else {}
                        if old_form_data.get('supervisor_signature'):
                            form_data['supervisor_signature'] = old_form_data['supervisor_signature']
                elif 'supervisor_signature' in form_data and form_data['supervisor_signature']:
                    # Signature is already in form_data (object format), ensure it's preserved
                    current_app.logger.info(f"✅ Supervisor signature preserved in form_data for submission {submission_id}")
                else:
                    # No new signature provided - preserve existing one
                    old_form_data = submission.form_data if submission.form_data else {}
                    if old_form_data.get('supervisor_signature'):
                        form_data['supervisor_signature'] = old_form_data['supervisor_signature']
                        current_app.logger.info(f"✅ Preserving existing supervisor signature for submission {submission_id}")
                    else:
                        current_app.logger.warning(f"⚠️ No supervisor signature found for submission {submission_id}")
            
            submission.form_data = form_data
        elif 'form_data_updates' in data:
            # Otherwise merge updates (backward compatibility)
            form_data_updates = data.get('form_data_updates', {})
            form_data = submission.form_data if submission.form_data else {}
            if isinstance(form_data, str):
                try:
                    import json
                    form_data = json.loads(form_data)
                except:
                    form_data = {}
            
            # CRITICAL: Preserve Operations Manager data before merging updates
            existing_om_comments = form_data.get('operations_manager_comments')
            existing_om_signature = form_data.get('operations_manager_signature') or form_data.get('opMan_signature')
            
            form_data.update(form_data_updates)
            
            # Restore Operations Manager data if it was lost during update
            if existing_om_comments and not form_data.get('operations_manager_comments'):
                form_data['operations_manager_comments'] = existing_om_comments
                current_app.logger.info(f"✅ Restored Operations Manager comments after form_data_updates merge for {submission_id}")
            if existing_om_signature and not form_data.get('operations_manager_signature') and not form_data.get('opMan_signature'):
                form_data['operations_manager_signature'] = existing_om_signature
                current_app.logger.info(f"✅ Restored Operations Manager signature after form_data_updates merge for {submission_id}")
            
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
        if should_regenerate:
            try:
                from common.db_utils import create_job_db
                from app.models import Job
                _, get_paths_fn, process_job_fn = get_module_functions(submission.module_type)
                
                # Delete old jobs to force regeneration
                old_jobs = Job.query.filter_by(submission_id=submission.id).all()
                for old_job in old_jobs:
                    db.session.delete(old_job)
                db.session.commit()
                
                # Create new job for regeneration
                new_job = create_job_db(submission)
                job_id = new_job.job_id
                
                GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths_fn()
                
                if EXECUTOR:
                    EXECUTOR.submit(
                        process_job_fn,
                        submission.submission_id,
                        job_id,
                        current_app.config,
                        current_app._get_current_object()
                    )
                    current_app.logger.info(f"✅ Regeneration job {job_id} queued for submission {submission_id} ({submission.module_type})")
                else:
                    current_app.logger.error("ThreadPoolExecutor not available for document regeneration")
            except Exception as regen_err:
                current_app.logger.error(f"Error queuing regeneration job after update_submission: {regen_err}", exc_info=True)
        
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
        
        # Check if supervisor is resubmitting their own form
        is_supervisor_own = (
            user.designation == 'supervisor' and 
            hasattr(submission, 'supervisor_id') and 
            submission.supervisor_id == user.id
        )
        
        # Allow supervisor to resubmit if status is submitted/rejected OR operations_manager_review (but not yet approved by OM)
        if is_supervisor_own and (
            submission.workflow_status in ['submitted', 'rejected', None] or
            (submission.workflow_status == 'operations_manager_review' and not submission.operations_manager_approved_at)
        ):
            return approve_supervisor_resubmission(submission_id)
        
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
