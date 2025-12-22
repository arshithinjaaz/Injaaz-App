# 🗄️ DATABASE MIGRATION STRATEGY - Injaaz App

## Current State Analysis

### Current Storage System (JSON Files)
```
generated/
├── jobs/          # Job status tracking (job_*.json)
├── submissions/   # Form submissions (sub_*.json)
└── uploads/       # Uploaded files (if not using Cloudinary)
```

**Problems:**
- ❌ No transactions (data integrity issues)
- ❌ No relationships (can't join data)
- ❌ Difficult to query (must read all files)
- ❌ No concurrent access control (race conditions)
- ❌ Backup complexity (many small files)
- ❌ No indexing (slow searches)
- ❌ File system limits (millions of files = slow)

### Proposed Database Schema

```sql
-- Users table (for future authentication)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200),
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Submissions table (replaces generated/submissions/*.json)
CREATE TABLE submissions (
    id SERIAL PRIMARY KEY,
    submission_id VARCHAR(50) UNIQUE NOT NULL,  -- sub_abc123
    module VARCHAR(50) NOT NULL,  -- hvac_mep, civil, cleaning
    user_id INTEGER REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    
    -- Common fields
    site_name VARCHAR(200),
    visit_date DATE,
    
    -- JSON blob for module-specific data
    form_data JSONB NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_by_ip VARCHAR(45),
    
    -- Indexes for fast queries
    INDEX idx_submission_id (submission_id),
    INDEX idx_module (module),
    INDEX idx_status (status),
    INDEX idx_visit_date (visit_date),
    INDEX idx_created_at (created_at)
);

-- Jobs table (replaces generated/jobs/*.json)
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) UNIQUE NOT NULL,  -- job_def456
    submission_id INTEGER REFERENCES submissions(id) ON DELETE CASCADE,
    
    status VARCHAR(50) NOT NULL,  -- started, running, done, failed
    progress INTEGER DEFAULT 0,  -- 0-100
    
    -- Results
    excel_url TEXT,
    pdf_url TEXT,
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Indexes
    INDEX idx_job_id (job_id),
    INDEX idx_submission_id (submission_id),
    INDEX idx_status (status)
);

-- Uploaded files table (track Cloudinary uploads)
CREATE TABLE uploaded_files (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER REFERENCES submissions(id) ON DELETE CASCADE,
    
    cloudinary_url TEXT NOT NULL,
    cloudinary_public_id VARCHAR(255),
    file_type VARCHAR(50),  -- photo, signature, report
    original_filename VARCHAR(255),
    file_size INTEGER,
    
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_submission_id (submission_id)
);

-- Audit log table (track all actions)
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,  -- submit_form, generate_report, download_file
    resource_type VARCHAR(50),     -- submission, job, file
    resource_id INTEGER,
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
);
```

## Migration Strategies

### Option 1: Gradual Migration (RECOMMENDED)
**Best for: Production systems with existing data**

#### Phase 1: Dual Write (2-3 days)
```python
# Write to BOTH JSON and database
def save_submission(data):
    # Old way (JSON)
    save_to_json_file(data)
    
    # New way (Database)
    db_submission = Submission(
        submission_id=data['id'],
        module=data['module'],
        form_data=data
    )
    db.session.add(db_submission)
    db.session.commit()
```

**Advantages:**
- ✅ Zero downtime
- ✅ Easy rollback (just stop writing to DB)
- ✅ Can compare outputs

#### Phase 2: Migrate Historical Data (background job)
```python
import os
import json
from app.models import Submission, db

def migrate_json_to_db():
    submissions_dir = 'generated/submissions'
    
    for filename in os.listdir(submissions_dir):
        if not filename.endswith('.json'):
            continue
            
        filepath = os.path.join(submissions_dir, filename)
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Check if already migrated
        existing = Submission.query.filter_by(
            submission_id=data['id']
        ).first()
        
        if existing:
            continue  # Skip duplicates
        
        # Create database record
        submission = Submission(
            submission_id=data['id'],
            module=data.get('module', 'unknown'),
            form_data=data,
            created_at=data.get('created_at'),
            status='completed'  # Historical data is complete
        )
        
        db.session.add(submission)
        db.session.commit()
        
        print(f"Migrated: {filename}")

# Run in background
migrate_json_to_db()
```

#### Phase 3: Read from Database (1 week after migration)
```python
# Switch reads to database
def get_submission(submission_id):
    # New way
    submission = Submission.query.filter_by(
        submission_id=submission_id
    ).first()
    
    if submission:
        return submission.form_data
    
    # Fallback to JSON (for unmigrated data)
    return read_json_file(submission_id)
```

#### Phase 4: Stop Writing to JSON (2 weeks after)
```python
# Remove JSON writes
def save_submission(data):
    # Only database now
    db_submission = Submission(
        submission_id=data['id'],
        module=data['module'],
        form_data=data
    )
    db.session.add(db_submission)
    db.session.commit()
```

#### Phase 5: Archive JSON Files (1 month after)
```bash
# Create backup
tar -czf submissions_backup_$(date +%Y%m%d).tar.gz generated/submissions/

# Move to archive
mkdir -p archives/
mv submissions_backup_*.tar.gz archives/

# Remove JSON files
rm -rf generated/submissions/*.json
```

### Option 2: Big Bang Migration
**Best for: New deployments or small datasets**

```bash
# 1. Stop application
systemctl stop injaaz

# 2. Backup JSON files
tar -czf backup_$(date +%Y%m%d).tar.gz generated/

# 3. Run migration script
python migrate_to_db.py

# 4. Verify migration
python verify_migration.py

# 5. Update code to use database
git checkout feature/database-migration

# 6. Start application
systemctl start injaaz
```

### Option 3: Hybrid Approach (CURRENT RECOMMENDATION)
**Keep JSON for job state (ephemeral), use DB for submissions (permanent)**

```python
# Submissions → Database
class Submission(db.Model):
    __tablename__ = 'submissions'
    # ... (see schema above)

# Jobs → Keep JSON (temporary, cleaned up after 7 days)
# Generated reports → Cloudinary (URLs in database)
```

**Rationale:**
- ✅ Critical data (submissions) in database
- ✅ Transient data (jobs) in fast JSON
- ✅ Simple migration (only submissions)
- ✅ Best of both worlds

## Implementation Guide

### Step 1: Create Models

Create `app/models.py`:

```python
from datetime import datetime
from app.extensions import db

class Submission(db.Model):
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    module = db.Column(db.String(50), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(50), default='pending', index=True)
    
    site_name = db.Column(db.String(200))
    visit_date = db.Column(db.Date, index=True)
    
    form_data = db.Column(db.JSON, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_by_ip = db.Column(db.String(45))
    
    # Relationships
    jobs = db.relationship('Job', backref='submission', cascade='all, delete-orphan')
    files = db.relationship('UploadedFile', backref='submission', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'submission_id': self.submission_id,
            'module': self.module,
            'status': self.status,
            'site_name': self.site_name,
            'visit_date': self.visit_date.isoformat() if self.visit_date else None,
            'form_data': self.form_data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id', ondelete='CASCADE'))
    
    status = db.Column(db.String(50), nullable=False, index=True)
    progress = db.Column(db.Integer, default=0)
    
    excel_url = db.Column(db.Text)
    pdf_url = db.Column(db.Text)
    error_message = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'job_id': self.job_id,
            'status': self.status,
            'progress': self.progress,
            'excel_url': self.excel_url,
            'pdf_url': self.pdf_url,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id', ondelete='CASCADE'))
    
    cloudinary_url = db.Column(db.Text, nullable=False)
    cloudinary_public_id = db.Column(db.String(255))
    file_type = db.Column(db.String(50))
    original_filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### Step 2: Create Migration Script

Create `migrate_json_to_db.py`:

```python
import os
import json
from datetime import datetime
from app import create_app
from app.models import Submission, db

def migrate_submissions():
    app = create_app()
    
    with app.app_context():
        submissions_dir = 'generated/submissions'
        total = 0
        success = 0
        failed = 0
        
        for filename in os.listdir(submissions_dir):
            if not filename.endswith('.json'):
                continue
            
            total += 1
            filepath = os.path.join(submissions_dir, filename)
            
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Check if already exists
                existing = Submission.query.filter_by(
                    submission_id=data['id']
                ).first()
                
                if existing:
                    print(f"⏭️  Skipping {filename} (already migrated)")
                    continue
                
                # Extract common fields
                fields = data.get('fields', {})
                
                # Create submission
                submission = Submission(
                    submission_id=data['id'],
                    module=data.get('module', 'unknown'),
                    status='completed',
                    site_name=fields.get('site_name') or fields.get('project_name'),
                    visit_date=parse_date(fields.get('visit_date') or fields.get('date_of_visit')),
                    form_data=data,
                    created_at=datetime.now(),
                    submitted_by_ip=data.get('ip_address')
                )
                
                db.session.add(submission)
                db.session.commit()
                
                success += 1
                print(f"✅ Migrated: {filename}")
                
            except Exception as e:
                failed += 1
                print(f"❌ Failed {filename}: {e}")
                db.session.rollback()
        
        print(f"\n📊 Migration Summary:")
        print(f"   Total: {total}")
        print(f"   Success: {success}")
        print(f"   Failed: {failed}")

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None

if __name__ == '__main__':
    migrate_submissions()
```

### Step 3: Update Routes to Use Database

Example for Civil module:

```python
# module_civil/routes.py

from app.models import Submission, db

@civil_bp.route('/submit', methods=['POST'])
def submit():
    # ... file upload logic ...
    
    # Create database record
    submission = Submission(
        submission_id=sub_id,
        module='civil',
        status='pending',
        site_name=fields.get('project_name'),
        visit_date=fields.get('visit_date'),
        form_data={
            'id': sub_id,
            'fields': fields,
            'files': saved_files,
            'base_url': request.host_url.rstrip('/')
        },
        submitted_by_ip=request.remote_addr
    )
    
    db.session.add(submission)
    db.session.commit()
    
    # Still create job (can keep JSON for jobs)
    job_id = random_id("job")
    # ...
```

## Rollback Plan

### If Migration Fails

```python
# Restore from backup
tar -xzf backup_20250122.tar.gz

# Revert code
git checkout main

# Clear database (if needed)
flask db downgrade

# Restart application
systemctl restart injaaz
```

## Performance Optimization

### Indexes

```sql
-- Add indexes for common queries
CREATE INDEX idx_submissions_module_date ON submissions(module, visit_date DESC);
CREATE INDEX idx_submissions_status_created ON submissions(status, created_at DESC);
CREATE INDEX idx_jobs_submission_status ON jobs(submission_id, status);
```

### Query Optimization

```python
# Bad: N+1 query
submissions = Submission.query.all()
for sub in submissions:
    jobs = sub.jobs  # Separate query for each submission

# Good: Eager loading
submissions = Submission.query.options(
    db.joinedload(Submission.jobs),
    db.joinedload(Submission.files)
).all()
```

## Timeline Estimate

### Gradual Migration (Recommended)
- **Week 1**: Create models, migrations, dual-write code
- **Week 2**: Deploy dual-write, monitor
- **Week 3**: Run migration script for historical data
- **Week 4**: Switch reads to database, monitor
- **Week 5**: Stop writing JSON, monitor
- **Week 6**: Archive JSON files

**Total: 6 weeks** (safe, production-ready)

### Big Bang Migration
- **Day 1**: Create models, migration script
- **Day 2**: Test migration on staging
- **Day 3**: Production migration

**Total: 3 days** (risky, downtime required)

### Hybrid Approach (Recommended for Now)
- **Week 1**: Create submission models only
- **Week 2**: Migrate submissions to DB
- **Week 3**: Keep jobs as JSON
- **Week 4**: Monitor and optimize

**Total: 4 weeks** (balanced approach)

## Recommendation

**Use Hybrid Approach:**

1. ✅ Move submissions to PostgreSQL (permanent data)
2. ✅ Keep jobs as JSON files (ephemeral, 7-day retention)
3. ✅ Store file URLs in database (track uploads)
4. ✅ Add audit logging (database)

**Next Steps:**
1. Create database models
2. Set up Flask-Migrate
3. Test migration script on staging data
4. Deploy with dual-write
5. Gradually cut over to database reads
6. Archive JSON files after validation

This gives you production-grade data management without overengineering transient job state.
