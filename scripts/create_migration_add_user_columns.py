"""
Migration script to add user permission columns
Run this once to add missing columns to the users table
This replaces the runtime ALTER TABLE logic
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Injaaz import create_app
from app.models import db, User
from sqlalchemy import text, inspect

def add_user_columns():
    """Add missing columns to users table if they don't exist"""
    app = create_app()
    
    with app.app_context():
        inspector = inspect(db.engine)
        
        if 'users' not in inspector.get_table_names():
            print("❌ Users table does not exist. Run 'flask db upgrade' first.")
            return False
        
        columns = [col['name'] for col in inspector.get_columns('users')]
        print(f"Found users table with {len(columns)} columns")
        
        missing_columns = []
        if 'password_changed' not in columns:
            missing_columns.append('password_changed')
        if 'access_hvac' not in columns:
            missing_columns.append('access_hvac')
        if 'access_civil' not in columns:
            missing_columns.append('access_civil')
        if 'access_cleaning' not in columns:
            missing_columns.append('access_cleaning')
        
        if not missing_columns:
            print("✅ All permission columns already exist")
            return True
        
        print(f"Missing columns detected: {', '.join(missing_columns)}. Adding them...")
        
        try:
            with db.engine.begin() as conn:
                for col_name in missing_columns:
                    try:
                        print(f"Adding {col_name} column to users table...")
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} BOOLEAN DEFAULT FALSE"))
                        print(f"✅ Added {col_name} column")
                    except Exception as col_error:
                        error_str = str(col_error).lower()
                        if 'already exists' in error_str or 'duplicate' in error_str:
                            print(f"Column {col_name} already exists, skipping")
                        else:
                            print(f"❌ Failed to add {col_name}: {col_error}")
                            raise
            
            # Grant full access to existing admin users
            admin_users = User.query.filter_by(role='admin').all()
            for admin in admin_users:
                admin.access_hvac = True
                admin.access_civil = True
                admin.access_cleaning = True
            db.session.commit()
            
            if admin_users:
                print(f"✅ Granted full access to {len(admin_users)} admin user(s)")
            
            print("✅ Migration completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("User Columns Migration Script")
    print("=" * 60)
    print("\n⚠️  NOTE: This is a one-time migration script.")
    print("For future migrations, use Flask-Migrate: 'flask db migrate' and 'flask db upgrade'")
    print("=" * 60)
    print()
    
    success = add_user_columns()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("You can now remove this script or keep it for reference.")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
        sys.exit(1)

