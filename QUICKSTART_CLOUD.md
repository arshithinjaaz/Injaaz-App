# ☁️ Quick Start: Enable Cloud Storage

## 3-Step Setup

### 1️⃣ Get Cloudinary Account
1. Go to https://cloudinary.com/users/register_free
2. Sign up (free tier: 25GB storage)
3. Go to Dashboard → Account Details

### 2️⃣ Add Credentials
Open your `.env` file and set:
```env
CLOUDINARY_CLOUD_NAME=your_cloud_name_here
CLOUDINARY_API_KEY=your_api_key_here
CLOUDINARY_API_SECRET=your_api_secret_here
```

### 3️⃣ Restart App
```bash
python Injaaz.py
```

## ✅ Verify It's Working

### Check Logs:
```
✅ Uploaded to Cloudinary: https://res.cloudinary.com/...
```

### Submit a Test Form:
1. Go to http://localhost:5000/hvac-mep/form
2. Upload a photo
3. Submit form
4. Download PDF - image should appear

### Check Cloudinary Dashboard:
- Media Library → See your uploaded files
- Usage → Monitor bandwidth

## 🔄 Fallback Mode

If Cloudinary is NOT configured:
```
⚠️ Cloudinary not configured, falling back to local storage
```
- Files save to `generated/uploads/`
- Everything still works
- But not suitable for production hosting

## 📚 More Help

- **Full Guide**: [CLOUD_STORAGE_SETUP.md](CLOUD_STORAGE_SETUP.md)
- **Migration Details**: [CLOUD_STORAGE_MIGRATION.md](CLOUD_STORAGE_MIGRATION.md)
- **Troubleshooting**: Check logs for errors

## 🚀 Deploy to Production

### Render/Heroku:
Set environment variables in dashboard (not in `.env`)

### Docker:
Pass via docker-compose.yml environment section

---

**That's it! Your images are now stored in the cloud. ☁️**
