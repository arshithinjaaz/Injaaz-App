"""
Quick script to add designation column to users table
"""
import sys
import os
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_URL

def add_designation_column():
    """Add designation column to users table"""
    # Get database path from DATABASE_URL
    if DATABASE_URL.startswith('sqlite'):
        # Extract path from sqlite:///path/to/db
        db_path = DATABASE_URL.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
        
        print(f"Connecting to database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if column exists
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'designation' in columns:
                print("[OK] Column 'designation' already exists")
            else:
                print("Adding 'designation' column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN designation VARCHAR(20) DEFAULT NULL")
                conn.commit()
                print("[OK] Added 'designation' column successfully")
            
            conn.close()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to add column: {e}")
            conn.close()
            return False
    else:
        print("[INFO] This script only works with SQLite. For PostgreSQL, use the migration script.")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Add Designation Column Script")
    print("=" * 60)
    print()
    
    success = add_designation_column()
    
    if success:
        print("\n[SUCCESS] Done!")
    else:
        print("\n[ERROR] Failed. Check errors above.")
        sys.exit(1)

