# Production Deployment Checklist ✅

## Pre-Deployment

- [ ] **Test locally:**
  ```bash
  python test_database_migration.py
  ```

- [ ] **Verify all modules import:**
  ```bash
  python -c "from Injaaz import create_app; app = create_app(); print('✅ OK')"
  ```

- [ ] **Check environment variables in `.env` (local only):**
  - SECRET_KEY
  - JWT_SECRET_KEY
  - CLOUDINARY_CLOUD_NAME
  - CLOUDINARY_API_KEY
  - CLOUDINARY_API_SECRET
  - DATABASE_URL (optional for local testing)

- [ ] **Commit all changes:**
  ```bash
  git add .
  git commit -m "Database migration complete - production ready"
  git push origin main
  ```

---

## Render Setup

- [ ] **Verify environment variables on Render dashboard:**
  - ✅ `DATABASE_URL` - Auto-set from PostgreSQL addon
  - ✅ `SECRET_KEY` - Auto-generated (32+ characters)
  - ✅ `JWT_SECRET_KEY` - Auto-generated
  - ✅ `FLASK_ENV=production`
  - ✅ `CLOUDINARY_CLOUD_NAME` - Your cloud name
  - ✅ `CLOUDINARY_API_KEY` - Your API key
  - ✅ `CLOUDINARY_API_SECRET` - Your API secret

- [ ] **Verify render.yaml is correct:**
  ```yaml
  buildCommand: pip install -r requirements-prods.txt && python scripts/init_db.py
  ```

- [ ] **Check PostgreSQL database is created:**
  - Database name: `injaaz`
  - Free tier: 1GB storage
  - Should be linked in render.yaml

---

## First Deployment

- [ ] **Monitor build logs:**
  - Watch for "Database tables created successfully"
  - Look for "Default admin user created"
  - Check for any import errors

- [ ] **Wait for deployment to complete:**
  - Usually takes 2-5 minutes
  - Status should show "Live"

- [ ] **Test health endpoint:**
  ```bash
  curl https://your-app.onrender.com/health
  ```

- [ ] **Test login page:**
  - Visit: `https://your-app.onrender.com/login`
  - Should load without errors

---

## Post-Deployment Testing

- [ ] **Login as admin:**
  - Username: `admin`
  - Password: `Admin@123`
  - **CHANGE THIS PASSWORD IMMEDIATELY!**

- [ ] **Test Civil module:**
  - Go to `/civil/form`
  - Fill form with test data
  - Upload photos
  - Submit
  - Wait for job completion
  - Download Excel and PDF

- [ ] **Test HVAC/MEP module:**
  - Go to `/hvac-mep/form`
  - Fill form with test data
  - Upload photos
  - Submit
  - Wait for job completion
  - Download Excel and PDF

- [ ] **Test Cleaning module:**
  - Go to `/cleaning/form`
  - Fill form with test data
  - Upload photos
  - Submit
  - Wait for job completion
  - Download Excel and PDF

- [ ] **Verify database persistence:**
  - Submit a form
  - Restart app (on Render dashboard)
  - Try to regenerate the report:
    ```
    GET /api/reports/regenerate/<submission_id>/excel
    ```
  - Should work even after restart!

---

## Report Regeneration Testing

- [ ] **Test on-demand Excel regeneration:**
  ```bash
  curl https://your-app.onrender.com/api/reports/regenerate/<submission_id>/excel
  ```

- [ ] **Test on-demand PDF regeneration:**
  ```bash
  curl https://your-app.onrender.com/api/reports/regenerate/<submission_id>/pdf
  ```

- [ ] **Test submission listing:**
  ```bash
  curl https://your-app.onrender.com/api/reports/list/civil
  curl https://your-app.onrender.com/api/reports/list/hvac_mep
  curl https://your-app.onrender.com/api/reports/list/cleaning
  ```

---

## Security Verification

- [ ] **Verify HTTPS is enforced**
- [ ] **Check secret keys are not default values**
- [ ] **Change admin password from default**
- [ ] **Test rate limiting (if Redis configured)**
- [ ] **Verify CSRF protection is active**

---

## Monitoring

- [ ] **Check Render logs for errors:**
  - https://dashboard.render.com
  - Look for any exceptions or warnings

- [ ] **Monitor database size:**
  - Render dashboard → PostgreSQL → Metrics
  - Should stay well under 1GB

- [ ] **Check Cloudinary usage:**
  - https://cloudinary.com/console
  - Monitor storage and bandwidth

---

## If Something Goes Wrong

### Database not initialized:
```bash
# SSH into Render shell
python scripts/init_db.py
```

### Reports not generating:
- Check logs for import errors
- Verify generator files exist
- Test locally first

### Files not uploading:
- Verify Cloudinary credentials
- Check network connectivity
- Look for CORS errors

### Job stuck in "pending":
- Check ThreadPoolExecutor is running
- Look for exceptions in logs
- Restart app

---

## Success Metrics

✅ **All submissions saved to database**  
✅ **Files uploaded to Cloudinary**  
✅ **Reports generated on-demand**  
✅ **Data persists across restarts**  
✅ **No storage bloat (ephemeral disk)**  
✅ **Under 1GB database usage**  

---

## Maintenance

### Weekly:
- Check database size
- Review error logs
- Test critical paths

### Monthly:
- Backup database (Render does this automatically)
- Review Cloudinary storage
- Update dependencies if needed

### As Needed:
- Add users via dashboard
- Delete old test submissions
- Regenerate old reports

---

## Support Resources

- **Render Docs:** https://render.com/docs
- **Flask Docs:** https://flask.palletsprojects.com
- **Cloudinary Docs:** https://cloudinary.com/documentation
- **PostgreSQL Docs:** https://www.postgresql.org/docs/

---

## Notes

- Render free tier: App sleeps after 15 min inactivity (first request takes ~30s)
- PostgreSQL free tier: 1GB storage, 1M rows
- Cloudinary free tier: 25GB storage, 25GB bandwidth/month
- Reports are temporary - regenerated on-demand from database
- All photos/signatures stored on Cloudinary (not database)

---

**🎉 When all checkboxes are ✅, you're production ready!**
