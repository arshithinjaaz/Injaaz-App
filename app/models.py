"""
Database Models for Injaaz App
SQLAlchemy ORM models for PostgreSQL/SQLite
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy import JSON

db = SQLAlchemy()
bcrypt = Bcrypt()


class User(db.Model):
    """User accounts with role-based access"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(20), default='user')  # 'admin', 'user'
    designation = db.Column(db.String(30), default=None)  # 'supervisor', 'operations_manager', 'business_development', 'procurement', 'general_manager'
    is_active = db.Column(db.Boolean, default=True)
    password_changed = db.Column(db.Boolean, default=False)  # Track if password was changed from default
    # Module access permissions (admin has access to all by default)
    access_hvac = db.Column(db.Boolean, default=False)  # HVAC&MEP form access
    access_civil = db.Column(db.Boolean, default=False)  # Civil works form access
    access_cleaning = db.Column(db.Boolean, default=False)  # Cleaning form access
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    submissions = db.relationship('Submission', foreign_keys='Submission.user_id', backref='user', lazy='dynamic')
    supervised_submissions = db.relationship('Submission', foreign_keys='Submission.supervisor_id', backref='supervisor', lazy='dynamic')
    ops_manager_submissions = db.relationship('Submission', foreign_keys='Submission.operations_manager_id', backref='operations_manager', lazy='dynamic')
    business_dev_submissions = db.relationship('Submission', foreign_keys='Submission.business_dev_id', backref='business_dev', lazy='dynamic')
    procurement_submissions = db.relationship('Submission', foreign_keys='Submission.procurement_id', backref='procurement_user', lazy='dynamic')
    general_manager_submissions = db.relationship('Submission', foreign_keys='Submission.general_manager_id', backref='general_manager', lazy='dynamic')
    # Legacy
    managed_submissions = db.relationship('Submission', foreign_keys='Submission.manager_id', backref='manager', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    sessions = db.relationship('Session', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Verify password against hash"""
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def has_module_access(self, module):
        """Check if user has access to a specific module"""
        if self.role == 'admin':
            return True  # Admins have access to all modules
        module_map = {
            'hvac_mep': self.access_hvac,
            'civil': self.access_civil,
            'cleaning': self.access_cleaning
        }
        return module_map.get(module, False)
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'access_hvac': self.access_hvac if self.role != 'admin' else True,
            'access_civil': self.access_civil if self.role != 'admin' else True,
            'access_cleaning': self.access_cleaning if self.role != 'admin' else True,
            'password_changed': self.password_changed if hasattr(self, 'password_changed') else True,
            'designation': self.designation if hasattr(self, 'designation') else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        return data
    
    def __repr__(self):
        return f'<User {self.username}>'


class Submission(db.Model):
    """Form submissions from all modules"""
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    module_type = db.Column(db.String(20), nullable=False, index=True)  # 'hvac_mep', 'civil', 'cleaning'
    site_name = db.Column(db.String(255))
    visit_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='draft', index=True)  # 'draft', 'submitted', 'processing', 'completed'
    workflow_status = db.Column(db.String(40), default='submitted', index=True)  # 'submitted', 'operations_manager_review', 'operations_manager_approved', 'bd_procurement_review', 'bd_approved', 'procurement_approved', 'general_manager_review', 'general_manager_approved', 'completed', 'rejected'
    
    # Workflow participants
    supervisor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Original submitter
    operations_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    business_dev_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    procurement_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    general_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Legacy fields (kept for backwards compatibility, deprecated)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Deprecated - use operations_manager_id
    supervisor_notified_at = db.Column(db.DateTime, nullable=True)  # Deprecated
    supervisor_reviewed_at = db.Column(db.DateTime, nullable=True)  # Deprecated
    manager_notified_at = db.Column(db.DateTime, nullable=True)  # Deprecated
    manager_reviewed_at = db.Column(db.DateTime, nullable=True)  # Deprecated
    
    # New workflow timestamps
    operations_manager_notified_at = db.Column(db.DateTime, nullable=True)
    operations_manager_approved_at = db.Column(db.DateTime, nullable=True)
    business_dev_notified_at = db.Column(db.DateTime, nullable=True)
    business_dev_approved_at = db.Column(db.DateTime, nullable=True)
    procurement_notified_at = db.Column(db.DateTime, nullable=True)
    procurement_approved_at = db.Column(db.DateTime, nullable=True)
    general_manager_notified_at = db.Column(db.DateTime, nullable=True)
    general_manager_approved_at = db.Column(db.DateTime, nullable=True)
    
    # Approval comments and signatures
    operations_manager_comments = db.Column(db.Text, nullable=True)
    business_dev_comments = db.Column(db.Text, nullable=True)
    procurement_comments = db.Column(db.Text, nullable=True)
    general_manager_comments = db.Column(db.Text, nullable=True)
    
    # Rejection tracking
    rejection_stage = db.Column(db.String(40), nullable=True)  # Which stage rejected
    rejection_reason = db.Column(db.Text, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    rejected_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    form_data = db.Column(JSON, nullable=False)  # All form fields as JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = db.relationship('Job', backref='submission', lazy='dynamic', cascade='all, delete-orphan')
    files = db.relationship('File', backref='submission', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary"""
        # Get the latest completed job for this submission (for downloads)
        latest_job = None
        try:
            # Use the jobs relationship (defined via db.relationship)
            if hasattr(self, 'jobs'):
                # Access the relationship - it will query Job model at runtime
                completed_jobs = [j for j in self.jobs if hasattr(j, 'status') and j.status == 'completed']
                if completed_jobs:
                    # Sort by completed_at descending to get latest
                    latest_job = max(completed_jobs, key=lambda j: j.completed_at if (hasattr(j, 'completed_at') and j.completed_at) else datetime.min)
        except Exception:
            # If query fails, skip - downloads won't be available
            pass
        
        return {
            'id': self.id,
            'submission_id': self.submission_id,
            'user_id': self.user_id,
            'module_type': self.module_type,
            'module': self.module_type,  # Alias for frontend compatibility
            'site_name': self.site_name,
            'visit_date': self.visit_date.isoformat() if self.visit_date else None,
            'status': self.status,
            'workflow_status': getattr(self, 'workflow_status', 'submitted'),
            'supervisor_id': getattr(self, 'supervisor_id', None),
            'operations_manager_id': getattr(self, 'operations_manager_id', None),
            'business_dev_id': getattr(self, 'business_dev_id', None),
            'procurement_id': getattr(self, 'procurement_id', None),
            'general_manager_id': getattr(self, 'general_manager_id', None),
            'manager_id': getattr(self, 'manager_id', None),
            'rejection_reason': getattr(self, 'rejection_reason', None),
            'rejected_at': getattr(self, 'rejected_at', None).isoformat() if hasattr(self, 'rejected_at') and getattr(self, 'rejected_at', None) else None,
            'supervisor_notified_at': getattr(self, 'supervisor_notified_at', None).isoformat() if hasattr(self, 'supervisor_notified_at') and getattr(self, 'supervisor_notified_at', None) else None,
            'supervisor_reviewed_at': getattr(self, 'supervisor_reviewed_at', None).isoformat() if hasattr(self, 'supervisor_reviewed_at') and getattr(self, 'supervisor_reviewed_at', None) else None,
            'manager_notified_at': getattr(self, 'manager_notified_at', None).isoformat() if hasattr(self, 'manager_notified_at') and getattr(self, 'manager_notified_at', None) else None,
            'manager_reviewed_at': getattr(self, 'manager_reviewed_at', None).isoformat() if hasattr(self, 'manager_reviewed_at') and getattr(self, 'manager_reviewed_at', None) else None,
            'operations_manager_approved_at': getattr(self, 'operations_manager_approved_at', None).isoformat() if hasattr(self, 'operations_manager_approved_at') and getattr(self, 'operations_manager_approved_at', None) else None,
            'business_dev_approved_at': getattr(self, 'business_dev_approved_at', None).isoformat() if hasattr(self, 'business_dev_approved_at') and getattr(self, 'business_dev_approved_at', None) else None,
            'procurement_approved_at': getattr(self, 'procurement_approved_at', None).isoformat() if hasattr(self, 'procurement_approved_at') and getattr(self, 'procurement_approved_at', None) else None,
            'general_manager_approved_at': getattr(self, 'general_manager_approved_at', None).isoformat() if hasattr(self, 'general_manager_approved_at') and getattr(self, 'general_manager_approved_at', None) else None,
            'form_data': self.form_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'latest_job_id': latest_job.job_id if latest_job else None  # Latest completed job for downloads
        }
    
    def __repr__(self):
        return f'<Submission {self.submission_id} - {self.module_type}>'


class Job(db.Model):
    """Background jobs for report generation"""
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)  # 'pending', 'processing', 'completed', 'failed'
    progress = db.Column(db.Integer, default=0)  # 0-100
    result_data = db.Column(JSON)  # URLs for Excel/PDF, error messages
    error_message = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'job_id': self.job_id,
            'submission_id': self.submission_id,
            'status': self.status,
            'progress': self.progress,
            'result_data': self.result_data,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Job {self.job_id} - {self.status}>'


class File(db.Model):
    """Uploaded files (photos, signatures, reports)"""
    __tablename__ = 'files'
    
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.String(50), unique=True, nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False)
    file_type = db.Column(db.String(20), index=True)  # 'photo', 'signature', 'report_pdf', 'report_excel'
    filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))  # Local path or NULL if cloud-only
    cloud_url = db.Column(db.String(500))  # Cloudinary URL
    is_cloud = db.Column(db.Boolean, default=True)
    file_size = db.Column(db.Integer)  # In bytes
    mime_type = db.Column(db.String(100))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'file_id': self.file_id,
            'submission_id': self.submission_id,
            'file_type': self.file_type,
            'filename': self.filename,
            'file_path': self.file_path,
            'cloud_url': self.cloud_url,
            'is_cloud': self.is_cloud,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }
    
    def __repr__(self):
        return f'<File {self.filename} - {self.file_type}>'


class AuditLog(db.Model):
    """Audit trail for security and compliance"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False, index=True)  # 'login', 'logout', 'create_submission', etc.
    resource_type = db.Column(db.String(50))  # 'submission', 'job', 'user'
    resource_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    details = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<AuditLog {self.action} - User {self.user_id}>'


class Session(db.Model):
    """JWT session management for token revocation"""
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_jti = db.Column(db.String(100), unique=True, nullable=False, index=True)  # JWT ID
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    is_revoked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token_jti': self.token_jti,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_revoked': self.is_revoked,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Session {self.token_jti[:8]}... - User {self.user_id}>'
