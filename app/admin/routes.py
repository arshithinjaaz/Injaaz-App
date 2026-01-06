"""
Admin Routes - User management and access control
"""
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, User, AuditLog
from app.middleware import admin_required
from common.error_responses import error_response, success_response
from datetime import datetime
import secrets
import string

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/api/admin')


def generate_temp_password(length=12):
    """Generate a temporary password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@admin_required
def list_users():
    """Get all users with their details"""
    try:
        # Note: User.submissions, audit_logs, and sessions are dynamic relationships
        # (lazy='dynamic'), so we can't use joinedload. The to_dict() method doesn't
        # include these relationships anyway, so we just query users directly.
        users = User.query.order_by(User.created_at.desc()).all()
        users_data = [user.to_dict() for user in users]
        
        return success_response({
            'users': users_data,
            'count': len(users_data)
        })
    except Exception as e:
        current_app.logger.error(f"Error listing users: {str(e)}", exc_info=True)
        return error_response('Failed to fetch users', status_code=500, error_code='DATABASE_ERROR')


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_user(user_id):
    """Get specific user details"""
    try:
        user = User.query.get_or_404(user_id)
        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching user: {str(e)}")
        return jsonify({'error': 'User not found'}), 404


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@jwt_required()
@admin_required
def reset_user_password(user_id):
    """Reset user password and email temporary password"""
    try:
        admin_id = get_jwt_identity()
        user = User.query.get_or_404(user_id)
        
        # Generate temporary password
        temp_password = generate_temp_password()
        user.set_password(temp_password)
        
        db.session.commit()
        
        # Log the action
        log_audit(admin_id, 'reset_password', 'user', str(user_id), {
            'target_user': user.username,
            'reset_by': User.query.get(admin_id).username if admin_id else 'system'
        })
        
        # Send email with temporary password
        email_sent = False
        try:
            from common.email_service import send_password_reset_email
            email_sent = send_password_reset_email(
                user_email=user.email,
                username=user.username,
                temp_password=temp_password
            )
        except Exception as email_error:
            current_app.logger.warning(f"Failed to send password reset email: {str(email_error)}")
            # Continue - password is reset even if email fails
        
        if email_sent:
            message = 'Password reset successfully. Temporary password has been sent to user\'s email.'
        else:
            # If email fails, return password in response as fallback (admin only)
            message = 'Password reset successfully. Email delivery failed - password returned in response.'
            current_app.logger.warning(f"Password reset email failed for user {user_id}, password returned in response")
        
        response_data = {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        }
        
        if not email_sent:
            response_data['temp_password'] = temp_password
            response_data['warning'] = 'Email delivery failed. Password returned in response (admin only).'
        
        return success_response(response_data, message=message)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resetting password: {str(e)}")
        return error_response('Failed to reset password', status_code=500, error_code='DATABASE_ERROR')


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@jwt_required()
@admin_required
def toggle_user_active(user_id):
    """Activate or deactivate a user"""
    try:
        admin_id = get_jwt_identity()
        user = User.query.get_or_404(user_id)
        
        # Prevent deactivating yourself
        if user_id == admin_id:
            return jsonify({'error': 'Cannot deactivate your own account'}), 400
        
        user.is_active = not user.is_active
        db.session.commit()
        
        # Log the action
        log_audit(admin_id, 'toggle_user_status', 'user', str(user_id), {
            'target_user': user.username,
            'new_status': 'active' if user.is_active else 'inactive',
            'changed_by': User.query.get(admin_id).username if admin_id else 'system'
        })
        
        return jsonify({
            'success': True,
            'message': f'User {"activated" if user.is_active else "deactivated"} successfully',
            'user': user.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling user status: {str(e)}")
        return jsonify({'error': 'Failed to update user status'}), 500


@admin_bp.route('/users/<int:user_id>/update-access', methods=['POST'])
@jwt_required()
@admin_required
def update_user_access(user_id):
    """Update user's module access permissions"""
    try:
        admin_id = get_jwt_identity()
        user = User.query.get_or_404(user_id)
        
        # Parse JSON with better error handling
        current_app.logger.info(f"Update access request for user {user_id}, Content-Type: {request.content_type}")
        
        try:
            data = request.get_json(force=True, silent=True)
        except Exception as json_error:
            current_app.logger.error(f"JSON parsing error: {json_error}")
            return jsonify({'error': 'Invalid JSON format'}), 400
        
        if data is None:
            body_text = request.get_data(as_text=True)
            current_app.logger.error(f"Invalid JSON in update-access request for user {user_id}. Content-Type: {request.content_type}, Body: {body_text[:200]}")
            return jsonify({'error': 'Invalid JSON or missing request body'}), 400
        
        current_app.logger.info(f"Received access data: {data}")
        
        # Get access values from request, defaulting to current values if not provided
        # Handle case where columns might not exist yet (use getattr with default)
        try:
            current_access_hvac = getattr(user, 'access_hvac', False)
            current_access_civil = getattr(user, 'access_civil', False)
            current_access_cleaning = getattr(user, 'access_cleaning', False)
        except AttributeError as attr_error:
            current_app.logger.error(f"User model missing access attributes: {attr_error}")
            return jsonify({'error': 'Database schema error - access columns missing. Please run migration.'}), 500
        
        # Get values from request, use current values as defaults
        access_hvac = data.get('access_hvac', current_access_hvac)
        access_civil = data.get('access_civil', current_access_civil)
        access_cleaning = data.get('access_cleaning', current_access_cleaning)
        
        # Convert to boolean (handles string "true"/"false", None, etc.)
        user.access_hvac = bool(access_hvac)
        user.access_civil = bool(access_civil)
        user.access_cleaning = bool(access_cleaning)
        
        db.session.commit()
        
        # Log the action
        log_audit(admin_id, 'update_user_access', 'user', str(user_id), {
            'target_user': user.username,
            'access_hvac': user.access_hvac,
            'access_civil': user.access_civil,
            'access_cleaning': user.access_cleaning,
            'changed_by': User.query.get(admin_id).username if admin_id else 'system'
        })
        
        return jsonify({
            'success': True,
            'message': 'User access updated successfully',
            'user': user.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user access: {str(e)}", exc_info=True)
        return jsonify({'error': f'Failed to update user access: {str(e)}'}), 500


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_user(user_id):
    """Delete a user account"""
    try:
        admin_id = get_jwt_identity()
        
        # Prevent deleting yourself
        if user_id == admin_id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        user = User.query.get_or_404(user_id)
        
        # Prevent deleting the last admin
        if user.role == 'admin':
            admin_count = User.query.filter_by(role='admin', is_active=True).count()
            if admin_count <= 1:
                return jsonify({'error': 'Cannot delete the last active admin user'}), 400
        
        username = user.username
        
        # Delete user (cascade will handle related records)
        db.session.delete(user)
        db.session.commit()
        
        # Log the action
        log_audit(admin_id, 'delete_user', 'user', str(user_id), {
            'deleted_user': username,
            'deleted_by': User.query.get(admin_id).username if admin_id else 'system'
        })
        
        return jsonify({
            'success': True,
            'message': f'User {username} deleted successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting user: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to delete user'}), 500


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_user(user_id):
    """Update user details"""
    try:
        admin_id = get_jwt_identity()
        user = User.query.get_or_404(user_id)
        
        data = request.get_json()
        
        # Update allowed fields
        if 'full_name' in data:
            user.full_name = data['full_name']
        if 'email' in data:
            # Check if email is already taken
            existing = User.query.filter_by(email=data['email']).first()
            if existing and existing.id != user_id:
                return jsonify({'error': 'Email already in use'}), 400
            user.email = data['email']
        if 'username' in data:
            # Check if username is already taken
            existing = User.query.filter_by(username=data['username']).first()
            if existing and existing.id != user_id:
                return jsonify({'error': 'Username already in use'}), 400
            user.username = data['username']
        if 'role' in data and data['role'] in ['admin', 'inspector', 'user']:
            # Prevent changing your own role
            if user_id == admin_id and data['role'] != 'admin':
                return jsonify({'error': 'Cannot change your own role'}), 400
            user.role = data['role']
        
        db.session.commit()
        
        # Log the action
        log_audit(admin_id, 'update_user', 'user', str(user_id), {
            'target_user': user.username,
            'changed_by': User.query.get(admin_id).username if admin_id else 'system'
        })
        
        return jsonify({
            'success': True,
            'message': 'User updated successfully',
            'user': user.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user: {str(e)}")
        return jsonify({'error': 'Failed to update user'}), 500


@admin_bp.route('/documents', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_documents():
    """Delete one or multiple documents (submissions)"""
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'submission_ids' not in data:
            return error_response('submission_ids array is required', status_code=400, error_code='VALIDATION_ERROR')
        
        submission_ids = data.get('submission_ids', [])
        if not isinstance(submission_ids, list) or len(submission_ids) == 0:
            return error_response('submission_ids must be a non-empty array', status_code=400, error_code='VALIDATION_ERROR')
        
        from app.models import Submission
        
        # Get submissions to delete
        submissions = Submission.query.filter(Submission.submission_id.in_(submission_ids)).all()
        
        if len(submissions) != len(submission_ids):
            found_ids = [s.submission_id for s in submissions]
            missing = [sid for sid in submission_ids if sid not in found_ids]
            return error_response(f'Some submissions not found: {missing}', status_code=404, error_code='NOT_FOUND')
        
        deleted_count = 0
        deleted_ids = []
        
        for submission in submissions:
            submission_id = submission.submission_id
            deleted_ids.append(submission_id)
            db.session.delete(submission)
            deleted_count += 1
        
        db.session.commit()
        
        # Log the action
        log_audit(admin_id, 'delete_documents', 'submission', ','.join(deleted_ids), {
            'count': deleted_count,
            'deleted_by': User.query.get(admin_id).username if admin_id else 'system'
        })
        
        return success_response({
            'deleted_count': deleted_count,
            'deleted_ids': deleted_ids
        }, message=f'Successfully deleted {deleted_count} document(s)')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting documents: {str(e)}", exc_info=True)
        return error_response('Failed to delete documents', status_code=500, error_code='DATABASE_ERROR')


@admin_bp.route('/documents', methods=['GET'])
@jwt_required()
@admin_required
def list_documents():
    """Get all submissions/documents with their details"""
    try:
        from app.models import Submission, Job, File
        
        # Get all submissions with user info
        submissions = Submission.query.order_by(Submission.created_at.desc()).all()
        
        documents = []
        for submission in submissions:
            # Get user info
            user = User.query.get(submission.user_id) if submission.user_id else None
            
            # Get completed jobs for this submission
            jobs = Job.query.filter_by(
                submission_id=submission.id,
                status='completed'
            ).all()
            
            # Extract document URLs from jobs
            excel_url = None
            pdf_url = None
            for job in jobs:
                if job.result_data:
                    excel_url = job.result_data.get('excel_url') or job.result_data.get('excel')
                    pdf_url = job.result_data.get('pdf_url') or job.result_data.get('pdf')
                    if excel_url or pdf_url:
                        break
            
            # If no URLs in jobs, check files table
            if not excel_url and not pdf_url:
                report_files = File.query.filter_by(
                    submission_id=submission.id
                ).filter(
                    File.file_type.in_(['report_excel', 'report_pdf'])
                ).all()
                
                for file in report_files:
                    if file.file_type == 'report_excel' and file.cloud_url:
                        excel_url = file.cloud_url
                    elif file.file_type == 'report_pdf' and file.cloud_url:
                        pdf_url = file.cloud_url
            
            # Format module type for display
            module_display = {
                'hvac_mep': 'HVAC & MEP',
                'civil': 'Civil Works',
                'cleaning': 'Cleaning Services'
            }.get(submission.module_type, submission.module_type.title())
            
            documents.append({
                'id': submission.id,
                'submission_id': submission.submission_id,
                'module_type': submission.module_type,
                'module_display': module_display,
                'site_name': submission.site_name or 'N/A',
                'visit_date': submission.visit_date.isoformat() if submission.visit_date else None,
                'status': submission.status,
                'created_at': submission.created_at.isoformat() + 'Z' if submission.created_at else None,  # Add 'Z' to indicate UTC
                'created_at_timestamp': submission.created_at.timestamp() if submission.created_at else None,
                'user': {
                    'id': user.id if user else None,
                    'username': user.username if user else 'Unknown',
                    'full_name': user.full_name if user else None,
                    'email': user.email if user else 'N/A'
                },
                'excel_url': excel_url,
                'pdf_url': pdf_url,
                'has_documents': bool(excel_url or pdf_url)
            })
        
        return success_response({
            'documents': documents,
            'count': len(documents)
        })
    except Exception as e:
        current_app.logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        return error_response('Failed to fetch documents', status_code=500, error_code='DATABASE_ERROR')


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

