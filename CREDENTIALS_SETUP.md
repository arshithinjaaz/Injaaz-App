# Production Credentials Setup Guide

## ✅ Credentials Are Now Hardcoded

All credentials have been hardcoded in **`config.py`** for easy deployment. No need to set environment variables!

## 📝 Current Credentials in config.py

```python
# SECRET_KEY - Used for session encryption and CSRF protection
SECRET_KEY = "VhfEWs6mHfBUVBaY-S01jxFXDdIa3sVANTqnm7LJH9I"

# CLOUDINARY - Image hosting service
CLOUDINARY_CLOUD_NAME = "dv7kljagk"
CLOUDINARY_API_KEY = "518838554723373"
CLOUDINARY_API_SECRET = "8VvbqJtaDmPz-1F18iD1dJnKzgI"

# FLASK ENVIRONMENT
FLASK_ENV = "production"  # Set to 'development' for local testing
```

## ⚠️ Cloudinary Credentials

The test shows: **❌ Error 401 - unknown api_key**

This means the Cloudinary API credentials might be incorrect or expired. To fix this:

### Option 1: Get Fresh Cloudinary Credentials
1. Go to https://cloudinary.com/console
2. Copy your credentials from the dashboard:
   - Cloud Name
   - API Key
   - API Secret
3. Update them in **`config.py`** (lines 19-23)

### Option 2: Use Your Existing Cloudinary Account
If you already have a working Cloudinary setup, copy the credentials from:
- `.env` file (if you have one)
- Environment variables on Render
- Cloudinary dashboard

### Where to Update
Edit **`c:\Users\hp\Documents\Injaaz-App\config.py`** lines 19-23:

```python
CLOUDINARY_CLOUD_NAME = "YOUR_CLOUD_NAME_HERE"
CLOUDINARY_API_KEY = "YOUR_API_KEY_HERE"
CLOUDINARY_API_SECRET = "YOUR_API_SECRET_HERE"
```

## ✅ What's Already Done

1. **SECRET_KEY**: ✅ Valid 43-character key (production-ready)
2. **FLASK_ENV**: ✅ Set to "production"
3. **Integration**: ✅ `Injaaz.py` reads from `config.py` and sets environment variables
4. **Validation**: ✅ App checks SECRET_KEY length on startup

## 🚀 How It Works

1. **`config.py`** stores all credentials
2. **`Injaaz.py`** imports config and:
   - Validates SECRET_KEY (exits if weak/missing)
   - Sets `app.config` values
   - Sets `os.environ` for cloudinary library
3. **All modules** automatically use these credentials

## 🧪 Testing

Run the test script to verify credentials:
```bash
python test_credentials.py
```

Expected output:
```
✅ SECRET_KEY: VhfEWs6mHf... (length: 43)
   ✅ SECRET_KEY length is adequate (32+ chars)
✅ FLASK_ENV: production
✅ CLOUDINARY_CLOUD_NAME: your_cloud_name
✅ CLOUDINARY_API_KEY: your_api_key
✅ Cloudinary connection SUCCESSFUL!
```

## 📦 Deployment to Render

Since credentials are hardcoded, deployment is simple:

1. **Push code to Git**:
   ```bash
   git add .
   git commit -m "Hardcoded production credentials"
   git push origin main
   ```

2. **Configure Render**:
   - Build Command: `pip install -r requirements-prods.txt`
   - Start Command: `gunicorn -w 4 -b 0.0.0.0:$PORT wsgi:app`
   - **NO ENVIRONMENT VARIABLES NEEDED!** 🎉

3. **Deploy and test**

## 🔒 Security Note

**⚠️ Important**: Since credentials are hardcoded in the repository:
- Make sure your Git repository is **PRIVATE**
- Do NOT push to public GitHub/GitLab
- Consider using `.gitignore` for `config.py` if sharing code publicly

For production best practices, environment variables are recommended, but hardcoding works fine for private deployments.

## 🔄 Switching Between Dev and Production

To switch between environments, just change one line in `config.py`:

```python
# Development mode (local testing)
FLASK_ENV = "development"

# Production mode (Render deployment)
FLASK_ENV = "production"
```

## ✨ Benefits of This Approach

✅ No environment variable setup needed  
✅ Works identically locally and on Render  
✅ Easy to update (just edit one file)  
✅ No risk of missing env vars  
✅ Immediate deployment ready  

## 📞 Troubleshooting

### App shows "Cloudinary not configured"
- Check credentials in `config.py` are correct
- Run `python test_credentials.py` to verify
- Check Cloudinary dashboard for correct values

### SECRET_KEY validation fails
- Ensure SECRET_KEY in `config.py` is 32+ characters
- Don't use default values like "change-me"

### Forms still not working
- Check browser console for errors
- Verify all 3 modules load (check startup logs)
- Test each form individually (Civil, HVAC, Cleaning)
