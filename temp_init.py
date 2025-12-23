"""
Temporary initialization endpoint for cloud deployment
DELETE THIS FILE after running once!
"""
from flask import Blueprint, jsonify
from app.models import db, User

init_bp = Blueprint('init_temp', __name__)

@init_bp.route('/init-database-temp-delete-me', methods=['GET'])
def init_database_temp():
    """
    ONE-TIME USE ONLY! 
    Visit this URL once to initialize database, then delete this file!
    """
    try:
        # Create all tables
        db.create_all()
        
        # Check if admin exists
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            # Create admin user
            admin = User(
                username='admin',
                email='admin@injaaz.com',
                full_name='System Administrator',
                role='admin',
                is_active=True
            )
            admin.set_password('Admin@123')
            
            db.session.add(admin)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Database initialized successfully!',
                'admin_username': 'admin',
                'admin_password': 'Admin@123',
                'warning': 'Change admin password immediately!',
                'action_required': 'DELETE THIS FILE (temp_init.py) NOW for security!'
            }), 200
        else:
            return jsonify({
                'status': 'already_initialized',
                'message': 'Database already initialized'
            }), 200
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
