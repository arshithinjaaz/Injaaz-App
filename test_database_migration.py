"""
Test Database Setup
Run this locally to verify database migration is working
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_database_setup():
    """Test that database is properly configured"""
    print("🧪 Testing Database Setup...\n")
    
    # Test 1: Import models
    print("1. Testing model imports...")
    try:
        from app.models import db, User, Submission, Job, File, Session, AuditLog
        print("   ✅ All models imported successfully")
    except Exception as e:
        print(f"   ❌ Failed to import models: {e}")
        return False
    
    # Test 2: Import database utilities
    print("\n2. Testing database utilities...")
    try:
        from common.db_utils import (
            create_submission_db,
            create_job_db,
            update_job_progress_db,
            complete_job_db,
            get_submission_db,
            get_job_status_db
        )
        print("   ✅ Database utilities imported successfully")
    except Exception as e:
        print(f"   ❌ Failed to import utilities: {e}")
        return False
    
    # Test 3: Create Flask app
    print("\n3. Testing Flask app creation...")
    try:
        from Injaaz import create_app
        app = create_app()
        print("   ✅ Flask app created successfully")
    except Exception as e:
        print(f"   ❌ Failed to create app: {e}")
        return False
    
    # Test 4: Initialize database tables
    print("\n4. Testing database initialization...")
    try:
        with app.app_context():
            db.create_all()
            print("   ✅ Database tables created successfully")
            
            # Show created tables
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"   📋 Tables created: {', '.join(tables)}")
    except Exception as e:
        print(f"   ❌ Failed to create tables: {e}")
        return False
    
    # Test 5: Test submission creation
    print("\n5. Testing submission creation...")
    try:
        with app.app_context():
            test_data = {
                "site_name": "Test Site",
                "visit_date": "2025-12-24",
                "test_field": "Test value"
            }
            
            submission = create_submission_db(
                module_type='civil',
                form_data=test_data,
                site_name="Test Site",
                visit_date="2025-12-24"
            )
            
            print(f"   ✅ Test submission created: {submission.submission_id}")
            
            # Test 6: Test job creation
            print("\n6. Testing job creation...")
            job = create_job_db(submission)
            print(f"   ✅ Test job created: {job.job_id}")
            
            # Test 7: Test retrieval
            print("\n7. Testing data retrieval...")
            retrieved = get_submission_db(submission.submission_id)
            if retrieved and retrieved['submission_id'] == submission.submission_id:
                print(f"   ✅ Submission retrieved successfully")
            else:
                print(f"   ❌ Failed to retrieve submission")
                return False
            
            job_status = get_job_status_db(job.job_id)
            if job_status and job_status['job_id'] == job.job_id:
                print(f"   ✅ Job status retrieved successfully")
            else:
                print(f"   ❌ Failed to retrieve job status")
                return False
            
            # Test 8: Test progress update
            print("\n8. Testing progress updates...")
            update_job_progress_db(job.job_id, 50, status='processing')
            updated_job = get_job_status_db(job.job_id)
            if updated_job['progress'] == 50 and updated_job['status'] == 'processing':
                print(f"   ✅ Job progress updated successfully")
            else:
                print(f"   ❌ Failed to update job progress")
                return False
            
            # Test 9: Complete job
            print("\n9. Testing job completion...")
            complete_job_db(job.job_id, {
                "excel": "http://test.com/report.xlsx",
                "pdf": "http://test.com/report.pdf"
            })
            completed_job = get_job_status_db(job.job_id)
            if completed_job['status'] == 'completed' and completed_job['progress'] == 100:
                print(f"   ✅ Job completed successfully")
            else:
                print(f"   ❌ Failed to complete job")
                return False
            
            # Cleanup test data
            print("\n10. Cleaning up test data...")
            Job.query.filter_by(job_id=job.job_id).delete()
            Submission.query.filter_by(submission_id=submission.submission_id).delete()
            db.session.commit()
            print("   ✅ Test data cleaned up")
    
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    print("\n🎉 Your database is properly configured and ready for production!")
    print("\nNext steps:")
    print("1. Push to GitHub: git push origin main")
    print("2. Render will auto-deploy and initialize database")
    print("3. Test submission on production site")
    print("4. Change admin password (default: Admin@123)")
    
    return True


if __name__ == '__main__':
    success = test_database_setup()
    sys.exit(0 if success else 1)
