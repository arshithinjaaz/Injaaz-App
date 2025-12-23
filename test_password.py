from app.extensions import db, bcrypt
from app.models import User
from Injaaz import create_app

app = create_app()

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin:
        print(f'Admin user found: {admin.username}')
        print(f'Password hash: {admin.password_hash[:20]}...')
        
        # Test password
        test_password = 'Admin@123'
        is_valid = bcrypt.check_password_hash(admin.password_hash, test_password)
        print(f'Password "Admin@123" is valid: {is_valid}')
    else:
        print('Admin user not found')
