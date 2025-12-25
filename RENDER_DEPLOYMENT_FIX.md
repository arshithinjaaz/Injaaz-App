# 🔧 DEPLOYMENT TROUBLESHOOTING GUIDE

## Issues Fixed

### ✅ Critical Fixes Applied:

1. **PostgreSQL URL Format** - Fixed `postgres://` to `postgresql://` conversion
2. **Database Connection Retry** - Added retry logic in init_db.py for Render startup
3. **Directory Creation** - Ensured directories are created during build
4. **Duplicate Error Handlers** - Removed conflicting error handler definitions
5. **Build Process** - Updated render.yaml to use build.sh

---

## Why Your App Wasn't Working on Render

### Problem 1: Database URL Incompatibility ⚠️ **MOST LIKELY CAUSE**
**Symptom**: App crashes on startup with SQLAlchemy error

**Root Cause**: 
- Render provides DATABASE_URL as `postgres://...`
- SQLAlchemy 1.4+ requires `postgresql://...`
- Your code didn't handle this conversion

**Fix Applied**: 
In `config.py`, we now auto-convert:
```python
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
```

---

### Problem 2: Database Connection Race Condition
**Symptom**: `init_db.py` fails during build

**Root Cause**:
- Database isn't fully ready when build command runs
- No retry logic for connection failures

**Fix Applied**:
Added retry logic in `scripts/init_db.py`:
- 5 retry attempts
- Exponential backoff (2s, 4s, 8s, 16s, 32s)
- Proper error messages

---

### Problem 3: Missing Directories
**Symptom**: File upload fails with "No such file or directory"

**Root Cause**:
- `generated/`, `uploads/`, `jobs/` directories not created
- `build.sh` wasn't being used by render.yaml

**Fix Applied**:
- Updated `render.yaml` to run `build.sh`
- Enhanced `build.sh` to create all necessary directories
- Added directory creation in `Injaaz.py create_app()` as backup

---

### Problem 4: Duplicate Error Handlers
**Symptom**: Flask warnings about duplicate error handlers

**Root Cause**:
- Error handlers defined twice in Injaaz.py (lines 193-208 and 327-349)
- Causes unpredictable behavior

**Fix Applied**:
Removed duplicate handlers, kept only the first set

---

## Deployment Checklist

### Before Deploying:

1. **Test locally first:**
   ```bash
   python diagnose_deployment.py
   ```

2. **Verify environment variables on Render:**
   - ✅ DATABASE_URL (auto-set by PostgreSQL addon)
   - ✅ SECRET_KEY (generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
   - ✅ JWT_SECRET_KEY (generate with same command)
   - ✅ CLOUDINARY_CLOUD_NAME
   - ✅ CLOUDINARY_API_KEY
   - ✅ CLOUDINARY_API_SECRET
   - ✅ FLASK_ENV=production

3. **Commit and push changes:**
   ```bash
   git add .
   git commit -m "Fix Render deployment issues"
   git push origin main
   ```

4. **Trigger manual deploy on Render**

---

## Checking Deployment Status

### View Build Logs on Render:
1. Go to your Render dashboard
2. Click on your web service
3. Click "Logs" tab
4. Look for:
   - ✅ "Database connection successful!"
   - ✅ "Database tables created successfully!"
   - ✅ "Default admin user created!"
   - ❌ Any error messages

### Common Error Messages and Fixes:

#### Error: "could not translate host name"
**Cause**: Database not fully provisioned yet  
**Fix**: Wait 2-3 minutes and redeploy

#### Error: "password authentication failed"
**Cause**: Database credentials not synced  
**Fix**: Check DATABASE_URL environment variable is set correctly

#### Error: "No module named 'psycopg2'"
**Cause**: Missing dependency  
**Fix**: Ensure `psycopg2-binary==2.9.6` is in requirements-prods.txt

#### Error: "disk I/O error"
**Cause**: Trying to write to read-only filesystem  
**Fix**: Ensure using Cloudinary for file storage (already implemented)

#### Error: "Application Error" (no details)
**Cause**: App crashed during startup  
**Fix**: 
1. Check Render logs for Python traceback
2. Run `python diagnose_deployment.py` locally
3. Verify all environment variables are set

---

## Testing Deployed App

### 1. Health Check
```bash
curl https://your-app.onrender.com/health
```
Expected response:
```json
{
  "status": "ok",
  "filesystem": true,
  "executor": true,
  "cloudinary": true
}
```

### 2. Login Page
Visit: `https://your-app.onrender.com/login`
- Should load without errors
- Default credentials:
  - Username: `admin`
  - Password: `Admin@123`
  - **⚠️ CHANGE IMMEDIATELY AFTER LOGIN**

### 3. Test Form Submission
1. Login as admin
2. Go to `/civil/form` or `/hvac-mep/form`
3. Fill in required fields
4. Upload a photo
5. Submit
6. Wait for job completion (check `/civil/job-status/<job_id>`)
7. Download generated reports

---

## If App Still Doesn't Work

### Run Diagnostics on Render:

1. **Add diagnostic endpoint** (temporary):
   
   In `Injaaz.py`, add before the health check:
   ```python
   @app.route('/diagnose')
   def diagnose():
       import subprocess
       result = subprocess.run(['python', 'diagnose_deployment.py'], 
                               capture_output=True, text=True)
       return f"<pre>{result.stdout}\n{result.stderr}</pre>"
   ```

2. **Visit**: `https://your-app.onrender.com/diagnose`

3. **Check the output** for specific errors

### Enable Debug Logging:

In `render.yaml`, add to envVars:
```yaml
- key: LOG_LEVEL
  value: DEBUG
```

### Check Render Service Status:
- Database: Should show "Available"
- Web Service: Should show "Live"
- Logs: Should not show continuous restart loops

---

## Common Render-Specific Issues

### Issue: App works locally but not on Render
**Causes**:
- Environment variables not set
- Database URL format wrong (fixed!)
- Using local file paths instead of Cloudinary
- Hardcoded localhost URLs

### Issue: App deploys but shows "Application Error"
**Causes**:
- Missing environment variables
- Database connection failure
- Import errors
- Unhandled exceptions during startup

### Issue: Forms submit but jobs never complete
**Causes**:
- Background executor not working (check logs)
- Generator functions failing silently
- Cloudinary upload failing (check API keys)
- Database write failing

---

## Support Resources

1. **Render Logs**: https://dashboard.render.com → Your Service → Logs
2. **Render Environment**: https://dashboard.render.com → Your Service → Environment
3. **Database Console**: https://dashboard.render.com → Your Database → Connect

---

## Post-Deployment Security

### Immediate Actions:

1. **Change Admin Password**:
   - Login as admin/Admin@123
   - Go to profile settings
   - Change to strong password

2. **Verify Secrets**:
   - Ensure SECRET_KEY is 32+ characters
   - Ensure JWT_SECRET_KEY is 32+ characters
   - Never commit secrets to git

3. **Enable HTTPS**:
   - Render provides free SSL
   - Verify certificate is active

4. **Monitor Logs**:
   - Check for failed login attempts
   - Watch for 500 errors
   - Monitor job failures

---

## Next Steps After Successful Deployment

1. ✅ Test all three modules (Civil, HVAC/MEP, Cleaning)
2. ✅ Verify PDF and Excel generation
3. ✅ Test photo uploads
4. ✅ Create additional user accounts
5. ✅ Set up monitoring/alerting
6. ✅ Configure custom domain (optional)

---

## Need Help?

If issues persist after applying these fixes:

1. Check Render logs for specific error messages
2. Run `python diagnose_deployment.py` locally
3. Compare local vs production environment variables
4. Verify database is accessible from Render
5. Check Cloudinary dashboard for upload activity

**Remember**: The PostgreSQL URL format issue (postgres:// vs postgresql://) is the #1 cause of Render deployment failures. This is now fixed in your code.
