"""
Admin Routes - User management and access control
"""
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, User, AuditLog
from app.middleware import admin_required
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
        users = User.query.order_by(User.created_at.desc()).all()
        users_data = [user.to_dict() for user in users]
        
        return jsonify({
            'success': True,
            'users': users_data,
            'count': len(users_data)
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error listing users: {str(e)}")
        return jsonify({'error': 'Failed to fetch users'}), 500


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
    """Reset user password and return temporary password"""
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
        
        return jsonify({
            'success': True,
            'message': 'Password reset successfully',
            'temp_password': temp_password,  # Only returned to admin
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resetting password: {str(e)}")
        return jsonify({'error': 'Failed to reset password'}), 500


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
        
        data = request.get_json()
        access_hvac = data.get('access_hvac', user.access_hvac)
        access_civil = data.get('access_civil', user.access_civil)
        access_cleaning = data.get('access_cleaning', user.access_cleaning)
        
        # Update permissions
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
        current_app.logger.error(f"Error updating user access: {str(e)}")
        return jsonify({'error': 'Failed to update user access'}), 500


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

