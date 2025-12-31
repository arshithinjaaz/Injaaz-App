# 🧹 Project Cleanup & Structure Guide

## 📋 Overview

This guide helps you clean up the Injaaz project and maintain a professional structure before setting up on your new laptop.

---

## ✅ Files to KEEP (Essential)

### Core Application Files
```
Injaaz.py                    # Main Flask application
config.py                    # Configuration settings
requirements.txt             # Python dependencies
requirements-prods.txt       # Production dependencies
requirements-dev.txt         # Development dependencies
```

### Application Structure
```
app/
  ├── models.py              # Database models
  ├── auth/
  │   └── routes.py          # Authentication routes
  └── admin/
      └── routes.py          # Admin routes

module_hvac_mep/
  ├── routes.py
  └── templates/
      └── hvac_mep_form.html

module_civil/
  ├── routes.py
  └── templates/
      └── civil_form.html

module_cleaning/
  ├── routes.py
  └── templates/
      └── cleaning_form.html
```

### Static Files
```
static/
  ├── logo.png               # App logo
  ├── icons/                 # PWA icons (keep all)
  ├── manifest.json          # PWA manifest
  ├── service-worker.js      # PWA service worker
  ├── pwa-install.js         # PWA installation
  ├── mobile_responsive.css  # Mobile styles
  ├── photo_upload_queue.js  # Photo upload system
  ├── photo_queue_ui.js      # Photo UI
  ├── photo_upload_queue.css # Photo styles
  ├── form.js                # Form utilities
  ├── main.js                # Main JavaScript
  ├── site_form.js           # Site form logic
  └── dropdown_init.js      # Dropdown initialization
```

### Templates
```
templates/
  ├── dashboard.html         # Main dashboard
  ├── login.html             # Login page
  ├── register.html          # Registration page
  ├── admin_dashboard.html   # Admin dashboard
  ├── access_denied.html     # Access denied page
  ├── offline.html           # Offline fallback
  └── pwa_meta.html          # PWA meta tags
```

### Configuration Files
```
.gitignore                   # Git ignore rules
.gitattributes               # Git attributes (if exists)
```

---

## 🗑️ Files to REMOVE (Temporary/Development)

### Documentation Files (Keep only essential)
```
❌ REMOVE:
  - PWA_GUIDE.md             # Can recreate if needed
  - PWA_SUMMARY.md           # Can recreate if needed
  - DEPLOYMENT_CHECKLIST_FINAL.md  # Can recreate
  - NATIVE_APP_GUIDE.md      # Will recreate on new laptop
  - INSTALL_ANDROID_STUDIO.md # Will recreate on new laptop
  - BUILD_APK_GUIDE.md       # Will recreate on new laptop
  - BUILD_APK_QUICK.md       # Will recreate on new laptop
  - NEXT_STEPS.md            # Will recreate on new laptop
  - QUICK_START.md           # Will recreate on new laptop
  - INSTALL_CHECKLIST.md     # Will recreate on new laptop
  - ANDROID_STUDIO_8GB_RAM.md # Will recreate on new laptop

✅ KEEP:
  - PROJECT_CLEANUP_GUIDE.md # This file
  - README.md                # Main project readme (if exists)
```

### Setup Scripts (Can recreate)
```
❌ REMOVE:
  - setup-native-app.sh      # Will recreate on new laptop
  - setup-native-app.bat     # Will recreate on new laptop
```

### Node.js Files (For Android Studio - recreate later)
```
❌ REMOVE (if not using now):
  - package.json             # Will recreate when setting up Android Studio
  - package-lock.json        # Will recreate
  - capacitor.config.ts      # Will recreate
  - node_modules/            # Will recreate
  - android/                 # Will recreate
  - ios/                     # Will recreate
  - .capacitor/              # Will recreate
```

### Python Cache Files
```
❌ REMOVE:
  - __pycache__/             # Python cache (all directories)
  - *.pyc                    # Compiled Python files
  - *.pyo                    # Optimized Python files
  - *.pyd                    # Python extensions
```

### IDE Files
```
❌ REMOVE:
  - .vscode/                 # VS Code settings (personal)
  - .idea/                   # IntelliJ/PyCharm settings
  - *.swp                    # Vim swap files
  - *.swo                    # Vim swap files
  - *~                       # Backup files
```

### OS Files
```
❌ REMOVE:
  - .DS_Store                # macOS
  - Thumbs.db                # Windows
  - desktop.ini              # Windows
```

### Temporary/Generated Files
```
❌ REMOVE:
  - *.log                    # Log files
  - *.tmp                    # Temporary files
  - .env.local               # Local environment (keep .env.example if exists)
  - instance/                # Flask instance folder (if not needed)
```

---

## 📁 Professional Project Structure

### Recommended Structure:
```
Injaaz-App/
├── .git/                    # Git repository
├── .gitignore               # Git ignore rules
├── README.md                 # Project documentation
├── Injaaz.py                 # Main application
├── config.py                 # Configuration
├── requirements.txt          # Dependencies
├── requirements-prods.txt    # Production dependencies
├── requirements-dev.txt      # Development dependencies
│
├── app/                      # Core application
│   ├── __init__.py
│   ├── models.py
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── admin/
│       ├── __init__.py
│       └── routes.py
│
├── module_hvac_mep/          # HVAC Module
│   ├── __init__.py
│   ├── routes.py
│   └── templates/
│       └── hvac_mep_form.html
│
├── module_civil/             # Civil Module
│   ├── __init__.py
│   ├── routes.py
│   └── templates/
│       └── civil_form.html
│
├── module_cleaning/          # Cleaning Module
│   ├── __init__.py
│   ├── routes.py
│   └── templates/
│       └── cleaning_form.html
│
├── templates/                # Shared templates
│   ├── dashboard.html
│   ├── login.html
│   ├── register.html
│   ├── admin_dashboard.html
│   ├── access_denied.html
│   ├── offline.html
│   └── pwa_meta.html
│
├── static/                   # Static assets
│   ├── logo.png
│   ├── icons/                # PWA icons
│   ├── manifest.json
│   ├── service-worker.js
│   ├── pwa-install.js
│   ├── mobile_responsive.css
│   ├── photo_upload_queue.js
│   ├── photo_queue_ui.js
│   ├── photo_upload_queue.css
│   ├── form.js
│   ├── main.js
│   ├── site_form.js
│   └── dropdown_init.js
│
├── generated/                # Generated reports (gitignored)
├── uploads/                  # Uploaded files (gitignored)
└── jobs/                     # Background jobs (gitignored)
```

---

## 🧹 Cleanup Steps

### Step 1: Backup Important Data
```bash
# Create backup of important files
# - Database backups
# - Environment variables
# - Custom configurations
```

### Step 2: Remove Unwanted Files

#### Windows PowerShell:
```powershell
# Remove Python cache
Get-ChildItem -Path . -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -Filter "*.pyc" | Remove-Item -Force

# Remove IDE files
Remove-Item -Recurse -Force .vscode -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .idea -ErrorAction SilentlyContinue

# Remove OS files
Get-ChildItem -Path . -Recurse -Filter ".DS_Store" | Remove-Item -Force
Get-ChildItem -Path . -Recurse -Filter "Thumbs.db" | Remove-Item -Force

# Remove log files
Get-ChildItem -Path . -Recurse -Filter "*.log" | Remove-Item -Force
```

#### Manual Removal:
1. Delete documentation files listed above
2. Delete setup scripts
3. Delete Node.js files (if not using Android Studio yet)
4. Delete IDE-specific folders

### Step 3: Update .gitignore

Ensure `.gitignore` includes:
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv

# Flask
instance/
.webassets-cache

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
desktop.ini

# Logs
*.log

# Environment
.env.local
.env

# Generated files
generated/
uploads/
jobs/

# Node.js (if not using yet)
node_modules/
package-lock.json
android/
ios/
.capacitor/

# Documentation (temporary)
*.md
!README.md
!PROJECT_CLEANUP_GUIDE.md
```

### Step 4: Verify Structure

Check that:
- ✅ All modules have `__init__.py`
- ✅ All routes are properly organized
- ✅ Static files are in `static/`
- ✅ Templates are in respective folders
- ✅ No duplicate files
- ✅ No temporary files

---

## 📝 Checklist for New Laptop Setup

### Before Transfer:
- [ ] Clean up project (follow steps above)
- [ ] Commit all changes to git
- [ ] Push to remote repository
- [ ] Export environment variables
- [ ] Backup database (if local)
- [ ] Document any custom configurations

### On New Laptop:
- [ ] Clone repository
- [ ] Install Python 3.8+
- [ ] Create virtual environment
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Set up environment variables
- [ ] Test application locally
- [ ] Set up Android Studio (when ready)
- [ ] Recreate Node.js setup (when ready)

---

## 🔄 When Ready for Android Studio

### Recreate Native App Setup:

1. **Install Node.js:**
   ```bash
   # Download from nodejs.org
   ```

2. **Initialize Capacitor:**
   ```bash
   npm install
   npx cap init
   npx cap add android
   ```

3. **Sync:**
   ```bash
   npx cap sync
   ```

4. **Open:**
   ```bash
   npx cap open android
   ```

---

## 📚 Documentation to Recreate

When you're ready, recreate these guides:
- Android Studio installation guide
- APK build guide
- Native app setup guide

Or use the guides from the repository if you keep them in a separate docs folder.

---

## ✅ Final Checklist

Before considering cleanup complete:

- [ ] All unwanted files removed
- [ ] Project structure is clean
- [ ] `.gitignore` is updated
- [ ] All changes committed
- [ ] Repository pushed to remote
- [ ] Documentation updated
- [ ] README.md is current (if exists)

---

## 💡 Tips

1. **Keep it simple:** Only keep files you actively use
2. **Document as you go:** Add comments in code, not separate docs
3. **Use git:** Commit frequently, push regularly
4. **Separate concerns:** Keep modules separate
5. **Version control:** Don't commit generated files

---

**Ready to clean up?** Follow the steps above! 🧹

**Questions?** Review the structure and adjust as needed for your workflow.

