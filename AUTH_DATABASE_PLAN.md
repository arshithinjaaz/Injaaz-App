# Authentication & Database Implementation Plan

## 🎯 Overview
Implement JWT-based authentication with PostgreSQL database for cloud deployment.

---

## 📊 Database Schema Design (PostgreSQL - Cloud Ready)

### 1. **Users Table**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120),
    role VARCHAR(20) DEFAULT 'user',  -- 'admin', 'user', 'inspector'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_username (username)
);
```

**Roles:**
- `admin` - Full access, can manage users
- `inspector` - Can create and view own submissions
- `user` - View only access

### 2. **Submissions Table**
```sql
CREATE TABLE submissions (
    id SERIAL PRIMARY KEY,
    submission_id VARCHAR(50) UNIQUE NOT NULL,  -- 'sub_abc123'
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    module_type VARCHAR(20) NOT NULL,  -- 'hvac_mep', 'civil', 'cleaning'
    site_name VARCHAR(255),
    visit_date DATE,
    status VARCHAR(20) DEFAULT 'draft',  -- 'draft', 'submitted', 'processing', 'completed'
    form_data JSONB NOT NULL,  -- All form fields as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_module_type (module_type),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);
```

### 3. **Jobs Table**
```sql
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) UNIQUE NOT NULL,  -- 'job_def456'
    submission_id INTEGER REFERENCES submissions(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    progress INTEGER DEFAULT 0,  -- 0-100
    result_data JSONB,  -- URLs for Excel/PDF, error messages
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_job_id (job_id),
    INDEX idx_status (status),
    INDEX idx_submission_id (submission_id)
);
```

### 4. **Files Table**
```sql
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(50) UNIQUE NOT NULL,
    submission_id INTEGER REFERENCES submissions(id) ON DELETE CASCADE,
    file_type VARCHAR(20),  -- 'photo', 'signature', 'report_pdf', 'report_excel'
    filename VARCHAR(255),
    file_path VARCHAR(500),  -- Local path or NULL if cloud-only
    cloud_url VARCHAR(500),  -- Cloudinary URL
    is_cloud BOOLEAN DEFAULT TRUE,
    file_size INTEGER,  -- In bytes
    mime_type VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_submission_id (submission_id),
    INDEX idx_file_type (file_type)
);
```

### 5. **Audit Log Table**
```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,  -- 'login', 'logout', 'create_submission', 'download_report'
    resource_type VARCHAR(50),  -- 'submission', 'job', 'user'
    resource_id VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
);
```

### 6. **Sessions Table** (Optional - for token blacklisting)
```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_jti VARCHAR(100) UNIQUE NOT NULL,  -- JWT ID
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_token_jti (token_jti),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at)
);
```

---

## 🔐 Authentication Flow

### JWT-Based Authentication

**Token Structure:**
- **Access Token:** Short-lived (15 minutes)
- **Refresh Token:** Long-lived (7 days)
- **Claims:** user_id, username, role, exp, iat, jti

### Endpoints

```
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/me
PUT  /auth/change-password
```

### Security Features
1. **Password Hashing:** bcrypt with 12 rounds
2. **Token Refresh:** Automatic refresh before expiry
3. **Token Revocation:** Blacklist via sessions table
4. **Rate Limiting:** 5 login attempts per minute
5. **CSRF Protection:** Double-submit cookie pattern
6. **Password Requirements:** 
   - Min 8 characters
   - 1 uppercase, 1 lowercase, 1 number, 1 special char

---

## 🚀 Implementation Steps

### Phase 1: Database Setup (Day 1)
- [ ] Install PostgreSQL locally or use cloud service (Render PostgreSQL)
- [ ] Create SQLAlchemy models
- [ ] Set up Flask-Migrate for migrations
- [ ] Create initial migration
- [ ] Seed admin user

### Phase 2: Authentication (Days 2-3)
- [ ] Create auth blueprint
- [ ] Implement JWT token generation/validation
- [ ] Add login/register endpoints
- [ ] Create middleware for protected routes
- [ ] Add CSRF protection

### Phase 3: Migration (Days 4-5)
- [ ] Update form submission to save to database
- [ ] Migrate job tracking from JSON to database
- [ ] Update file handling to use files table
- [ ] Create migration script for existing JSON data

### Phase 4: Security Hardening (Day 6)
- [ ] Move credentials to environment variables
- [ ] Add input validation with marshmallow
- [ ] Implement rate limiting
- [ ] Add audit logging

### Phase 5: UI Updates (Day 7)
- [ ] Add login/register pages
- [ ] Update forms to require authentication
- [ ] Add user dashboard
- [ ] Add logout functionality

---

## 📦 Cloud Database Options

### Option 1: Render PostgreSQL (Recommended)
- **Pros:** Same platform as app, easy integration, free tier available
- **Cons:** Free tier has limitations (90 days retention)
- **Pricing:** Free tier or $7/month for persistent storage
- **Setup:** Automatic with Render, get DATABASE_URL env var

### Option 2: Neon (Serverless Postgres)
- **Pros:** Serverless, auto-scaling, generous free tier
- **Cons:** Newer service, fewer features
- **Pricing:** Free tier 0.5 GB, paid from $19/month
- **Setup:** Create project, get connection string

### Option 3: Supabase
- **Pros:** PostgreSQL + auth + storage + realtime, great free tier
- **Cons:** Overkill if just need database
- **Pricing:** Free 500MB, paid from $25/month
- **Setup:** Create project, get DATABASE_URL

### Option 4: AWS RDS PostgreSQL
- **Pros:** Enterprise-grade, highly scalable
- **Cons:** More complex setup, expensive
- **Pricing:** From $15/month (t3.micro)
- **Setup:** Create RDS instance, configure security groups

**Recommendation: Render PostgreSQL** (Same platform, easiest integration)

---

## 🔧 Configuration Changes

### Environment Variables (Use in Production)
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/injaaz_db

# JWT
JWT_SECRET_KEY=<generate-strong-secret-64-chars>
JWT_ACCESS_TOKEN_EXPIRES=900  # 15 minutes
JWT_REFRESH_TOKEN_EXPIRES=604800  # 7 days

# Flask
SECRET_KEY=<generate-strong-secret-64-chars>
FLASK_ENV=production

# Cloudinary
CLOUDINARY_CLOUD_NAME=<your-cloud-name>
CLOUDINARY_API_KEY=<your-api-key>
CLOUDINARY_API_SECRET=<your-api-secret>

# Redis (Optional - for rate limiting)
REDIS_URL=<your-redis-url>

# Admin User (Initial Setup)
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@injaaz.com
ADMIN_PASSWORD=<secure-password>
```

---

## 📝 Migration Strategy

### Migrating Existing JSON Data

1. **Submissions:**
   ```python
   # Read all sub_*.json files
   # Create Submission records
   # Link to default admin user
   ```

2. **Jobs:**
   ```python
   # Read all job_*.json files
   # Create Job records
   # Link to corresponding submissions
   ```

3. **Files:**
   ```python
   # Scan uploads directory
   # Create File records
   # Match to submissions by filename patterns
   ```

### Zero-Downtime Migration
1. Run migration script on staging
2. Keep JSON files as backup
3. Deploy with dual-write (JSON + DB) for 1 week
4. Verify data consistency
5. Switch to DB-only mode
6. Archive JSON files

---

## 🎨 User Dashboard Features

### For Inspectors:
- View all own submissions
- Filter by module, date, status
- Download reports
- Edit drafts
- View submission history

### For Admins:
- View all submissions (all users)
- User management (create, edit, deactivate)
- System statistics
- Audit log viewer
- Export data

---

## 🔒 Security Checklist

- [x] Passwords hashed with bcrypt
- [x] JWT tokens with expiry
- [x] Token refresh mechanism
- [x] CSRF protection
- [x] Rate limiting (login attempts)
- [x] Input validation (marshmallow)
- [x] SQL injection protection (SQLAlchemy ORM)
- [x] XSS protection (Jinja2 auto-escaping)
- [x] Audit logging
- [ ] Two-factor authentication (Future)
- [ ] Password reset via email (Future)
- [ ] Account lockout after failed attempts (Future)

---

## 📈 Performance Considerations

### Database Indexing
- Indexes on frequently queried columns (user_id, status, created_at)
- Composite indexes for common query patterns
- JSONB indexes for form_data queries

### Query Optimization
- Use eager loading for relationships
- Pagination for large result sets
- Database connection pooling (SQLAlchemy)

### Caching Strategy
- Redis cache for user sessions
- Cache dropdown data (30 min TTL)
- Cache report URLs (24 hour TTL)

---

## 🧪 Testing Strategy

### Unit Tests
- Test all database models
- Test authentication functions
- Test JWT token generation/validation

### Integration Tests
- Test full login/register flow
- Test authenticated form submission
- Test job processing with database

### Load Tests
- 100 concurrent users
- Measure response times
- Identify bottlenecks

---

## 📊 Monitoring & Maintenance

### Metrics to Track
- Active users
- Submissions per day/week/month
- Average report generation time
- Failed jobs percentage
- Database size growth

### Backup Strategy
- Daily automated backups (Render handles this)
- Weekly full backup to S3
- Keep 30 days of backups
- Test restore procedure monthly

---

## 💡 Future Enhancements

1. **Multi-tenancy:** Support multiple organizations
2. **API Access:** REST API for mobile apps
3. **Webhooks:** Notify external systems
4. **Advanced Reports:** Analytics dashboard
5. **Offline Sync:** Queue submissions offline, sync when online
6. **Template System:** Reusable form templates
7. **Approval Workflow:** Multi-stage approval process

---

## ✅ Acceptance Criteria

Before going live:
- [ ] All tests passing (80%+ coverage)
- [ ] Admin user created
- [ ] 10 test submissions migrated successfully
- [ ] Reports generate correctly with authentication
- [ ] Login/logout working on mobile
- [ ] Password reset flow tested
- [ ] Backup/restore tested
- [ ] Performance tested (100 concurrent users)
- [ ] Security audit passed
- [ ] Documentation updated

---

## 🎯 Timeline

**Week 1:** Database & Authentication  
**Week 2:** Migration & Security  
**Week 3:** UI & Testing  
**Week 4:** Deployment & Monitoring

**Total Effort:** 4 weeks for full implementation
