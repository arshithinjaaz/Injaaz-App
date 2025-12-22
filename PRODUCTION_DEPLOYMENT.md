# 🚀 PRODUCTION DEPLOYMENT GUIDE - Injaaz App

## ✅ Pre-Deployment Checklist

### 1. Generate Secure Secrets

```bash
# Generate SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate JWT_SECRET_KEY
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in ALL placeholders:

```bash
cp .env.example .env
# Edit .env with your actual values
```

**Required Variables:**
- `SECRET_KEY` - Flask session secret (generate new!)
- `JWT_SECRET_KEY` - JWT token secret (generate new!)
- `CLOUDINARY_CLOUD_NAME` - Your Cloudinary cloud name
- `CLOUDINARY_API_KEY` - Your Cloudinary API key
- `CLOUDINARY_API_SECRET` - Your Cloudinary API secret
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string (for rate limiting)
- `APP_BASE_URL` - Your app's public URL

### 3. Install Dependencies

```bash
pip install -r requirements-prods.txt
```

### 4. Run Database Migrations (if using database)

```bash
# Initialize database
flask db init

# Create migration
flask db migrate -m "Initial migration"

# Apply migration
flask db upgrade
```

### 5. Test Health Check

```bash
# Local test
curl http://localhost:5000/health

# Expected response:
{
  "status": "ok",
  "filesystem": true,
  "executor": true,
  "cloudinary": true,
  "redis": true
}
```

## 🔒 Security Configuration

### Enable CSRF Protection (Production)

Set environment variable:
```bash
ENABLE_CSRF=true
```

### Enable Rate Limiting

Ensure `REDIS_URL` is set for rate limiting storage:
```bash
REDIS_URL=redis://your-redis-url
RATELIMIT_DEFAULT="100 per hour"
```

### Configure Allowed Hosts (if needed)

For production, consider adding:
```python
# In Injaaz.py
app.config['SERVER_NAME'] = 'yourdomain.com'
```

## 🐳 Docker Deployment

### Build Image

```bash
docker build -t injaaz-app .
```

### Run Container

```bash
docker run -d \
  --name injaaz \
  -p 5000:5000 \
  --env-file .env \
  -v $(pwd)/generated:/app/generated \
  injaaz-app
```

## 🌐 Render Deployment

### 1. Connect Repository

1. Go to Render Dashboard
2. Click "New +" → "Web Service"
3. Connect your GitHub repository

### 2. Configure Service

- **Name**: `injaaz-app`
- **Region**: Choose closest to your users
- **Branch**: `main`
- **Root Directory**: `.` (root)
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements-prods.txt`
- **Start Command**: `gunicorn wsgi:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT`

### 3. Environment Variables

Add in Render dashboard:

| Key | Value | Secret |
|-----|-------|--------|
| `FLASK_ENV` | `production` | No |
| `SECRET_KEY` | (generated secret) | **Yes** |
| `JWT_SECRET_KEY` | (generated secret) | **Yes** |
| `CLOUDINARY_CLOUD_NAME` | your-cloud-name | No |
| `CLOUDINARY_API_KEY` | your-api-key | **Yes** |
| `CLOUDINARY_API_SECRET` | your-api-secret | **Yes** |
| `CLOUDINARY_UPLOAD_PRESET` | your-preset | No |
| `APP_BASE_URL` | https://your-app.onrender.com | No |
| `DATABASE_URL` | (Render PostgreSQL URL) | **Yes** |
| `REDIS_URL` | (Render Redis URL) | **Yes** |
| `ENABLE_CSRF` | `true` | No |

### 4. Add PostgreSQL Database

1. In Render Dashboard, create new PostgreSQL database
2. Copy the Internal Database URL
3. Add as `DATABASE_URL` environment variable

### 5. Add Redis Instance

1. In Render Dashboard, create new Redis instance
2. Copy the Internal Redis URL
3. Add as both `REDIS_URL` and `RATELIMIT_STORAGE_URL`

## 📊 Monitoring & Logging

### View Logs

```bash
# Render: Click on "Logs" tab in dashboard

# Docker: 
docker logs -f injaaz

# Direct:
tail -f /var/log/injaaz/app.log
```

### Health Check Endpoint

Monitor: `https://your-app.onrender.com/health`

Set up Render's built-in health checks:
- **Path**: `/health`
- **Expected Status**: `200`
- **Timeout**: `30 seconds`

### Error Tracking (Optional but Recommended)

Add Sentry for error tracking:

```bash
pip install sentry-sdk[flask]
```

```python
# In Injaaz.py
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    integrations=[FlaskIntegration()],
    environment=os.environ.get('FLASK_ENV', 'production')
)
```

## 🔧 Post-Deployment Verification

### 1. Test All Modules

```bash
# HVAC/MEP Form
curl https://your-app.onrender.com/hvac-mep/form

# Civil Form
curl https://your-app.onrender.com/civil/form

# Cleaning Form
curl https://your-app.onrender.com/cleaning/form
```

### 2. Test File Upload

1. Visit each form
2. Upload a test image
3. Verify Cloudinary upload successful
4. Submit form
5. Verify report generation

### 3. Test Rate Limiting

```bash
# Make 101 requests quickly
for i in {1..101}; do
  curl https://your-app.onrender.com/health
done

# Should see 429 error after 100
```

### 4. Test CSRF Protection (if enabled)

```bash
# Should fail without CSRF token
curl -X POST https://your-app.onrender.com/civil/submit \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Expected: 400 Bad Request (CSRF token missing)
```

## 🚨 Troubleshooting

### App Won't Start

1. Check logs for import errors
2. Verify all environment variables are set
3. Check database connectivity: `pg_isready -h <host>`
4. Check Redis connectivity: `redis-cli -u $REDIS_URL ping`

### Uploads Failing

1. Verify Cloudinary credentials
2. Check Cloudinary quotas
3. Verify file size limits (10MB per file, 100MB total)

### Rate Limiting Not Working

1. Verify `REDIS_URL` is set correctly
2. Check Redis connection: `redis-cli -u $REDIS_URL ping`
3. Check Flask-Limiter installed: `pip show Flask-Limiter`

### Reports Not Generating

1. Check executor workers: should be 2
2. Check disk space for `generated/` directory
3. Check job state files in `generated/jobs/`
4. Verify fonts installed for PDF generation

## 📈 Performance Tuning

### Gunicorn Workers

For Render or production:
```bash
# Formula: (2 x CPU cores) + 1
gunicorn wsgi:app --workers 4 --threads 4 --timeout 120
```

### Database Connection Pooling

Already configured in `app/config.py`:
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
```

### Redis Connection Pooling

Automatic with `redis-py` when using `redis.from_url()`

## 🔄 Updates & Maintenance

### Deploy New Version

```bash
# Git push triggers auto-deploy on Render
git push origin main

# Or manual deploy in Render dashboard
```

### Database Backup

```bash
# Render: Automatic daily backups

# Manual backup:
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

### Clear Generated Files

```bash
# Remove old jobs (older than 30 days)
find generated/jobs/ -name "*.json" -mtime +30 -delete

# Remove old submissions (older than 30 days)
find generated/submissions/ -name "*.json" -mtime +30 -delete
```

## 📞 Support Contacts

- **App Issues**: Check application logs
- **Cloudinary**: https://support.cloudinary.com/
- **Render**: https://render.com/docs/support
- **Database**: Check PostgreSQL logs

## ✨ Success Metrics

After deployment, monitor:
- ✅ Health check returns 200
- ✅ All forms load successfully
- ✅ File uploads work to Cloudinary
- ✅ Reports generate within 2 minutes
- ✅ Rate limiting blocks > 100 req/hour
- ✅ No 500 errors in logs
- ✅ Response times < 2 seconds

---

**Deployment Complete!** 🎉

Your Injaaz App is now securely deployed and production-ready.
