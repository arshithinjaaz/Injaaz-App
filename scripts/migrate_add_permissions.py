"""
Migration script to add module permission columns to User table
Run this once to update existing database schema
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Injaaz import create_app
from app.models import db

def migrate_add_permissions():
    """Add module permission columns to users table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            if 'access_hvac' in columns and 'access_civil' in columns and 'access_cleaning' in columns:
                print("[OK] Permission columns already exist. Migration not needed.")
                return True
            
            print("Adding module permission columns to users table...")
            
            # Add columns using raw SQL (works for both SQLite and PostgreSQL)
            with db.engine.connect() as conn:
                if 'access_hvac' not in columns:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN access_hvac BOOLEAN DEFAULT 0"))
                    print("  [OK] Added access_hvac column")
                
                if 'access_civil' not in columns:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN access_civil BOOLEAN DEFAULT 0"))
                    print("  [OK] Added access_civil column")
                
                if 'access_cleaning' not in columns:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN access_cleaning BOOLEAN DEFAULT 0"))
                    print("  [OK] Added access_cleaning column")
                
                conn.commit()
            
            # Grant all access to existing admin users
            from app.models import User
            admin_users = User.query.filter_by(role='admin').all()
            for admin in admin_users:
                admin.access_hvac = True
                admin.access_civil = True
                admin.access_cleaning = True
            db.session.commit()
            
            print(f"[OK] Migration completed successfully!")
            print(f"   Updated {len(admin_users)} admin users with full access")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Migration failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("Database Migration: Add Module Permissions")
    print("=" * 60)
    print()
    migrate_add_permissions()

