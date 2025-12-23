# Authentication & Database Implementation Guide

## ✅ Phase 1 Complete - Foundation Setup

### What's Been Implemented

1. **Database Models** ([app/models.py](app/models.py))
   - ✅ User model with bcrypt password hashing
   - ✅ Submission model with JSONB form data storage
   - ✅ Job model for background task tracking
   - ✅ File model for uploaded files/reports
   - ✅ AuditLog model for security tracking
   - ✅ Session model for JWT token management

2. **Authentication System** ([app/auth/routes.py](app/auth/routes.py))
   - ✅ User registration with validation
   - ✅ Login with JWT access/refresh tokens
   - ✅ Token refresh endpoint
   - ✅ Logout with token revocation
   - ✅ Password change functionality
   - ✅ Current user profile endpoint

3. **Security Enhancements**
   - ✅ Moved credentials to environment variables ([config.py](config.py))
   - ✅ Created `.env` file with configuration
   - ✅ Added JWT token blacklisting via session tracking
   - ✅ Password strength validation (8+ chars, uppercase, lowercase, digit)
   - ✅ Email format validation
   - ✅ Audit logging for all auth actions

4. **Frontend Pages**
   - ✅ Login page ([templates/login.html](templates/login.html))
   - ✅ Registration page ([templates/register.html](templates/register.html))
   - ✅ Professional styling with Injaaz branding

5. **Migration Scripts**
   - ✅ Database initialization script ([scripts/init_db.py](scripts/init_db.py))
   - ✅ JSON to database migration script ([scripts/migrate_json_to_db.py](scripts/migrate_json_to_db.py))

6. **Core Integration**
   - ✅ Updated [Injaaz.py](Injaaz.py) with SQLAlchemy and JWT
   - ✅ Added authentication routes
   - ✅ JWT token revocation checking
   - ✅ Security validations for production

---

## 🚀 Next Steps - Implementation Guide

### Step 1: Initialize Database (5 minutes)

```bash
# Make sure PostgreSQL is running (or use SQLite for development)
# Update .env with your database URL

# Run database initialization
python scripts/init_db.py
```

This will:
- Create all database tables
- Create default admin user (username: `admin`, password: `Admin@123`)
- **⚠️ IMPORTANT**: Change the admin password immediately after first login!

### Step 2: Migrate Existing Data (10 minutes)

```bash
# Migrate existing JSON submissions and jobs to database
python scripts/migrate_json_to_db.py
```

This will:
- Import all submissions from `generated/submissions/*.json`
- Import all jobs from `generated/jobs/*.json`
- Preserve all form data, photos, and signatures
- Link submissions with jobs

### Step 3: Test Authentication (5 minutes)

```bash
# Start the application
python Injaaz.py

# The app will run on http://localhost:5000
```

Test the authentication:
1. Visit http://localhost:5000/register - Create a new user account
2. Visit http://localhost:5000/login - Login with your credentials
3. Visit http://localhost:5000/dashboard - Should show dashboard

### Step 4: Secure Your Application (CRITICAL)

**Before deploying to production:**

1. **Generate New Secret Keys**
   ```bash
   # Generate random secret keys
   python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
   python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
   ```

2. **Update .env File**
   ```env
   SECRET_KEY=<your-new-secret-key>
   JWT_SECRET_KEY=<your-new-jwt-secret>
   ```

3. **Set Production Environment**
   ```env
   FLASK_ENV=production
   DEBUG=false
   SESSION_COOKIE_SECURE=true
   ```

4. **Change Admin Password**
   - Login as admin
   - Go to profile/settings
   - Use "Change Password" feature

---

## 📋 Phase 2 - Module Integration (Week 2)

### Update Form Submissions to Use Database

Currently, forms save to JSON files. Next step is to save to database:

**For each module** (HVAC/MEP, Civil, Cleaning):

1. **Update routes.py**
   ```python
   from app.models import db, Submission, File
   from flask_jwt_extended import jwt_required, get_jwt_identity
   
   @hvac_mep_bp.route('/submit', methods=['POST'])
   @jwt_required()  # Require authentication
   def submit():
       user_id = get_jwt_identity()
       
       # Create database submission instead of JSON
       submission = Submission(
           submission_id=random_id('sub'),
           user_id=user_id,
           module_type='hvac_mep',
           site_name=request.form.get('siteName'),
           visit_date=datetime.strptime(request.form.get('visitDate'), '%Y-%m-%d'),
           status='submitted',
           form_data=dict(request.form)
       )
       
       db.session.add(submission)
       db.session.commit()
       
       # Continue with report generation...
   ```

2. **Update job tracking** to use database Job model
3. **Update file uploads** to use database File model

### Add Authentication to Forms

1. **Update form templates** to check authentication
   ```html
   <script>
   // Check if user is logged in
   const token = localStorage.getItem('access_token');
   if (!token) {
       window.location.href = '/login';
   }
   
   // Add token to all API requests
   fetch('/hvac-mep/submit', {
       headers: {
           'Authorization': `Bearer ${token}`
       }
   });
   </script>
   ```

2. **Add JWT middleware** to protect routes
   ```python
   from app.middleware import token_required
   
   @hvac_mep_bp.route('/form')
   @token_required
   def form():
       return render_template('hvac_form.html')
   ```

---

## 🔐 Phase 3 - Advanced Security (Week 3)

### 1. CSRF Protection

Already set up in Injaaz.py, just needs enabling:
```env
ENABLE_CSRF=true
```

Update forms to include CSRF token:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
```

### 2. Rate Limiting

Already configured with Redis. Enable by ensuring Redis is running:
```env
REDIS_URL=redis://localhost:6379/0
```

### 3. Input Validation

Use marshmallow schemas for API validation:
```python
from marshmallow import Schema, fields, validate

class SubmissionSchema(Schema):
    site_name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    visit_date = fields.Date(required=True)
    # ... more fields
```

### 4. Role-Based Access Control

Already implemented in middleware:
```python
from app.middleware import admin_required, inspector_required

@app.route('/admin/users')
@admin_required
def list_users():
    # Only admins can access
    pass

@app.route('/hvac-mep/submit')
@inspector_required
def submit_form():
    # Inspectors and admins can access
    pass
```

---

## 📊 Phase 4 - Dashboard & Reports (Week 4)

### Admin Dashboard Features

1. **User Management**
   - List all users
   - Activate/deactivate users
   - Change user roles
   - View user activity logs

2. **Submission Reports**
   - View all submissions
   - Filter by module, date, user
   - Export to Excel
   - View statistics

3. **Audit Logs**
   - View all system activities
   - Filter by user, action, date
   - Export for compliance

### User Dashboard

1. **My Submissions**
   - View own submissions
   - Track job status
   - Download reports

2. **Profile Management**
   - Change password
   - Update email
   - View login history

---

## 🌐 Phase 5 - Cloud Deployment

### Recommended: Render.com

1. **Create PostgreSQL Database**
   - Go to Render Dashboard
   - Create new PostgreSQL database
   - Copy `External Database URL`
   - Add to .env as `DATABASE_URL`

2. **Deploy Application**
   - Connect GitHub repository
   - Set environment variables from .env
   - Deploy

3. **Run Migrations**
   ```bash
   # Via Render shell
   python scripts/init_db.py
   python scripts/migrate_json_to_db.py
   ```

### Alternative: AWS/Azure/GCP

- Use managed PostgreSQL (RDS/Azure Database/Cloud SQL)
- Use managed Redis (ElastiCache/Azure Cache/Memorystore)
- Deploy with Docker or directly

---

## 🧪 Testing

### Manual Testing Checklist

- [ ] Register new user
- [ ] Login with correct credentials
- [ ] Login with wrong password (should fail)
- [ ] Access protected route without token (should fail)
- [ ] Refresh access token
- [ ] Logout (token should be revoked)
- [ ] Try using revoked token (should fail)
- [ ] Change password
- [ ] Submit form as authenticated user
- [ ] View audit logs

### Automated Testing (TODO)

Create tests using pytest:
```bash
pip install pytest pytest-flask
pytest tests/
```

---

## 📝 API Documentation

### Authentication Endpoints

#### POST /api/auth/register
Register a new user.

**Request:**
```json
{
    "username": "john_doe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "password": "SecurePass123"
}
```

**Response (201):**
```json
{
    "message": "User registered successfully",
    "user": {
        "id": 1,
        "username": "john_doe",
        "email": "john@example.com",
        "full_name": "John Doe",
        "role": "user"
    }
}
```

#### POST /api/auth/login
Authenticate user and get tokens.

**Request:**
```json
{
    "username": "john_doe",
    "password": "SecurePass123"
}
```

**Response (200):**
```json
{
    "message": "Login successful",
    "access_token": "eyJ0eXAiOiJKV1QiLCJ...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJ...",
    "user": {
        "id": 1,
        "username": "john_doe",
        "role": "user"
    }
}
```

#### POST /api/auth/refresh
Refresh access token (requires refresh token).

**Headers:**
```
Authorization: Bearer <refresh_token>
```

**Response (200):**
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJ..."
}
```

#### POST /api/auth/logout
Logout and revoke token (requires access token).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
    "message": "Logout successful"
}
```

#### GET /api/auth/me
Get current user profile (requires access token).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
    "user": {
        "id": 1,
        "username": "john_doe",
        "email": "john@example.com",
        "full_name": "John Doe",
        "role": "user",
        "created_at": "2024-01-15T10:30:00"
    }
}
```

#### POST /api/auth/change-password
Change user password (requires access token).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
    "current_password": "OldPass123",
    "new_password": "NewPass456"
}
```

**Response (200):**
```json
{
    "message": "Password changed successfully"
}
```

---

## 🐛 Troubleshooting

### Database Connection Errors

**Problem:** `sqlalchemy.exc.OperationalError: could not connect to server`

**Solution:**
```bash
# Check if PostgreSQL is running
pg_isready

# For development, use SQLite instead
DATABASE_URL=sqlite:///injaaz.db
```

### JWT Token Errors

**Problem:** `Token has been revoked`

**Solution:**
- User logged out and token was revoked
- Clear localStorage and login again
- Check session expiration

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'flask_jwt_extended'`

**Solution:**
```bash
pip install -r requirements-prods.txt
```

### Migration Errors

**Problem:** `Duplicate entry for submission_id`

**Solution:**
- Submissions already migrated
- Check database before re-running migration
- Clear database if needed: `python scripts/init_db.py --reset`

---

## 📞 Support

For issues or questions:
1. Check this guide first
2. Review [AUTH_DATABASE_PLAN.md](AUTH_DATABASE_PLAN.md) for detailed architecture
3. Check application logs for error messages
4. Review [CODEBASE_ANALYSIS.md](CODEBASE_ANALYSIS.md) for system overview

---

## 🎯 Success Criteria

Your implementation is complete when:

- [✅] Database initialized with all tables
- [✅] Can register new users
- [✅] Can login and receive JWT tokens
- [✅] Tokens work for protected routes
- [✅] Can logout and revoke tokens
- [ ] Forms save to database instead of JSON
- [ ] All modules protected with authentication
- [ ] Admin dashboard functional
- [ ] Deployed to cloud with managed database
- [ ] All credentials in environment variables
- [ ] CSRF protection enabled
- [ ] Rate limiting active

**Current Status: Phase 1 Complete (Foundation Setup) ✅**
**Next: Initialize database and test authentication**
