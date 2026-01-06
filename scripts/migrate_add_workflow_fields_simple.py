"""
Simple migration script to add workflow and designation fields
No emojis to avoid Windows console encoding issues
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Injaaz import create_app
from app.models import db
from sqlalchemy import text, inspect

def add_workflow_fields():
    """Add missing workflow and designation columns"""
    app = create_app()
    
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Add designation to users table
        if 'users' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            if 'designation' not in columns:
                print("Adding 'designation' column to users table...")
                try:
                    with db.engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN designation VARCHAR(20) DEFAULT NULL"))
                    print("[OK] Added 'designation' column to users table")
                except Exception as e:
                    error_str = str(e).lower()
                    if 'already exists' in error_str or 'duplicate' in error_str:
                        print("[SKIP] Column 'designation' already exists")
                    else:
                        print(f"[ERROR] Failed to add 'designation': {e}")
                        return False
        
        # Add workflow fields to submissions table
        if 'submissions' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('submissions')]
            
            missing_columns = []
            workflow_fields = [
                'workflow_status',
                'supervisor_id',
                'manager_id',
                'supervisor_notified_at',
                'supervisor_reviewed_at',
                'manager_notified_at',
                'manager_reviewed_at'
            ]
            
            for field in workflow_fields:
                if field not in columns:
                    missing_columns.append(field)
            
            if missing_columns:
                print(f"Adding workflow columns to submissions table: {', '.join(missing_columns)}...")
                try:
                    with db.engine.begin() as conn:
                        for col_name in missing_columns:
                            try:
                                if col_name.endswith('_id'):
                                    conn.execute(text(f"ALTER TABLE submissions ADD COLUMN {col_name} INTEGER"))
                                elif col_name.endswith('_at'):
                                    conn.execute(text(f"ALTER TABLE submissions ADD COLUMN {col_name} TIMESTAMP DEFAULT NULL"))
                                elif col_name == 'workflow_status':
                                    conn.execute(text(f"ALTER TABLE submissions ADD COLUMN {col_name} VARCHAR(30) DEFAULT 'submitted'"))
                                print(f"[OK] Added {col_name} column")
                            except Exception as col_error:
                                error_str = str(col_error).lower()
                                if 'already exists' in error_str or 'duplicate' in error_str:
                                    print(f"[SKIP] Column {col_name} already exists")
                                else:
                                    print(f"[ERROR] Failed to add {col_name}: {col_error}")
                                    raise
                except Exception as e:
                    print(f"[ERROR] Migration failed: {e}")
                    return False
            else:
                print("[OK] All workflow columns already exist")
        
        print("\n[SUCCESS] Workflow migration completed successfully!")
        return True

if __name__ == '__main__':
    print("=" * 60)
    print("Workflow Fields Migration Script")
    print("=" * 60)
    print("\nThis script adds:")
    print("  - 'designation' field to users table")
    print("  - Workflow fields to submissions table")
    print("=" * 60)
    print()
    
    success = add_workflow_fields()
    
    if success:
        print("\n[SUCCESS] Migration completed successfully!")
    else:
        print("\n[ERROR] Migration failed. Please check the errors above.")
        sys.exit(1)

