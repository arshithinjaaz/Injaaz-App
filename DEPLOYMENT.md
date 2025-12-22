# Deploying Injaaz App to Render

## Prerequisites
1. GitHub account
2. Render account (https://render.com)
3. Cloudinary account (already configured)

## Step-by-Step Deployment

### 1. Push Code to GitHub

If you haven't already initialized Git:

```bash
git init
git add .
git commit -m "Initial commit - Injaaz App ready for deployment"
```

Create a new repository on GitHub and push:

```bash
git remote add origin https://github.com/YOUR_USERNAME/injaaz-app.git
git branch -M main
git push -u origin main
```

### 2. Deploy on Render

#### Option A: Using Blueprint (render.yaml)

1. Go to https://dashboard.render.com/
2. Click "New" → "Blueprint"
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml`
5. Review the configuration
6. Click "Apply"

#### Option B: Manual Setup

1. Go to https://dashboard.render.com/
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `injaaz-app`
   - **Environment**: `Python 3`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Instance Type**: `Free` or `Starter` (recommended)

### 3. Configure Environment Variables

In your Render dashboard, add these environment variables:

**Required:**
- `SECRET_KEY`: (Generate a random string, e.g., using `python -c "import secrets; print(secrets.token_hex(32))"`)
- `JWT_SECRET_KEY`: (Generate another random string)
- `FLASK_ENV`: `production`

**Cloudinary (Required for image uploads):**
- `CLOUDINARY_CLOUD_NAME`: `dv7kljagk`
- `CLOUDINARY_API_KEY`: (Your Cloudinary API key)
- `CLOUDINARY_API_SECRET`: (Your Cloudinary API secret)

**Database (Optional - for auth features):**
- `DATABASE_URL`: (Automatically set if you add a PostgreSQL database)

**Email (Optional - for HVAC/MEP reports):**
- `MAIL_SERVER`: (Your SMTP server)
- `MAIL_PORT`: (e.g., 587)
- `MAIL_USERNAME`: (Your email username)
- `MAIL_PASSWORD`: (Your email password)
- `MAIL_USE_TLS`: `True`
- `MAIL_DEFAULT_SENDER`: (Your from email address)

### 4. Add PostgreSQL Database (Optional)

If you need database features:

1. In Render dashboard, click "New" → "PostgreSQL"
2. Create database named `injaaz-db`
3. Copy the "Internal Database URL"
4. Add it as `DATABASE_URL` environment variable in your web service

### 5. Deploy

1. Click "Create Web Service" or "Apply" (for blueprint)
2. Render will build and deploy your app
3. Monitor the logs for any errors
4. Once deployed, your app will be available at: `https://injaaz-app.onrender.com`

## Important Notes

### File Storage Limitations

⚠️ **Render uses ephemeral file systems** - uploaded files in `generated/` will be deleted on each deployment or dyno restart.

**Solutions:**
1. **Use Cloudinary** (Already implemented): All photos are uploaded to Cloudinary cloud storage
2. **Reports**: Generated reports (Excel/PDF) should be:
   - Downloaded immediately by users (already implemented with auto-download)
   - OR uploaded to cloud storage (Cloudinary/S3)
   - OR sent via email (implemented for HVAC/MEP module)

### Progressive Upload

The app is configured to upload photos to Cloudinary immediately when selected. This means:
- No blob URL errors
- No file size limits
- Photos persist even if deployment restarts
- Fast form submissions

### Performance Considerations

1. **Workers**: App uses 2 Gunicorn workers (configurable in `render.yaml`)
2. **Timeout**: 120 seconds for report generation
3. **Free Tier**: Render free tier spins down after inactivity (first request may be slow)

### Testing Checklist

After deployment, test:
- [ ] HVAC/MEP form submission
- [ ] Civil form submission  
- [ ] Cleaning form submission
- [ ] Photo uploads to Cloudinary
- [ ] Report generation (Excel + PDF)
- [ ] Auto-download functionality
- [ ] Signature capture and embedding

## Troubleshooting

### Build Fails

Check logs for missing dependencies:
```bash
pip install -r requirements-prods.txt
```

### App Crashes

1. Check environment variables are set correctly
2. Verify Cloudinary credentials
3. Check logs: `https://dashboard.render.com/web/YOUR_SERVICE/logs`

### Photos Not Uploading

1. Verify Cloudinary environment variables
2. Check Cloudinary dashboard for upload activity
3. Test Cloudinary connection locally

### Reports Not Generating

1. Check worker timeout (increase if needed)
2. Verify `generated/` directory is created in build script
3. Check logs for Python errors

## Updating the App

To deploy updates:

```bash
git add .
git commit -m "Your update message"
git push origin main
```

Render will automatically detect the push and redeploy.

## Monitoring

Monitor your app at:
- **Render Dashboard**: https://dashboard.render.com
- **Cloudinary Dashboard**: https://cloudinary.com/console
- **App Logs**: Check for errors in real-time

## Support

For issues specific to:
- **Render**: https://render.com/docs
- **Cloudinary**: https://cloudinary.com/documentation
- **Flask**: https://flask.palletsprojects.com/
