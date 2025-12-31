# 📱 Native App Development Guide - Injaaz

## 🎯 Overview

Convert your PWA into **native Android & iOS apps** for Play Store and App Store using **Capacitor**.

## ✅ Why Capacitor?

- ✅ **Keep your existing code** - No need to rewrite
- ✅ **Publish to both stores** - Android & iOS from one codebase
- ✅ **Native features** - Camera, file system, push notifications
- ✅ **Fast development** - Build on your existing PWA
- ✅ **Free & Open Source** - No licensing fees

---

## 🚀 Quick Start

### Step 1: Install Capacitor

```bash
npm install @capacitor/core @capacitor/cli
npm install @capacitor/android @capacitor/ios
```

### Step 2: Initialize Capacitor

```bash
npx cap init
```

**When prompted:**
- **App name:** Injaaz
- **App ID:** com.injaaz.app
- **Web dir:** static (or wherever your static files are)

### Step 3: Add Platforms

```bash
# Add Android
npx cap add android

# Add iOS (Mac only)
npx cap add ios
```

### Step 4: Sync Your Web App

```bash
# Copy web files to native projects
npx cap sync
```

### Step 5: Build & Run

```bash
# Android
npx cap open android
# Then build in Android Studio

# iOS (Mac only)
npx cap open ios
# Then build in Xcode
```

---

## 📦 Required Setup Files

### 1. `package.json`
Create this in your project root:

```json
{
  "name": "injaaz-app",
  "version": "1.0.0",
  "description": "Injaaz Professional Site Reporting App",
  "main": "index.js",
  "scripts": {
    "build": "echo 'Build your Flask app'",
    "sync": "npx cap sync",
    "android": "npx cap open android",
    "ios": "npx cap open ios"
  },
  "dependencies": {
    "@capacitor/core": "^5.0.0",
    "@capacitor/cli": "^5.0.0",
    "@capacitor/android": "^5.0.0",
    "@capacitor/ios": "^5.0.0",
    "@capacitor/app": "^5.0.0",
    "@capacitor/camera": "^5.0.0",
    "@capacitor/filesystem": "^5.0.0",
    "@capacitor/network": "^5.0.0",
    "@capacitor/status-bar": "^5.0.0",
    "@capacitor/splash-screen": "^5.0.0"
  }
}
```

### 2. `capacitor.config.ts`
Create this in your project root:

```typescript
import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.injaaz.app',
  appName: 'Injaaz',
  webDir: 'static',
  server: {
    // For development - point to your Render URL
    url: 'https://your-app.onrender.com',
    cleartext: true
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: "#125435",
      androidSplashResourceName: "splash",
      androidScaleType: "CENTER_CROP",
      showSpinner: true,
      androidSpinnerStyle: "large",
      iosSpinnerStyle: "small",
      spinnerColor: "#ffffff",
      splashFullScreen: true,
      splashImmersive: true
    },
    StatusBar: {
      style: "dark",
      backgroundColor: "#125435"
    }
  }
};

export default config;
```

---

## 🎨 App Icons & Splash Screens

### Generate Icons

Capacitor can use your existing PWA icons. Place them in:

**Android:**
```
android/app/src/main/res/
├── mipmap-mdpi/icon.png (48x48)
├── mipmap-hdpi/icon.png (72x72)
├── mipmap-xhdpi/icon.png (96x96)
├── mipmap-xxhdpi/icon.png (144x144)
└── mipmap-xxxhdpi/icon.png (192x192)
```

**iOS:**
```
ios/App/App/Assets.xcassets/AppIcon.appiconset/
```

### Generate Splash Screens

Use your logo on green background (#125435).

---

## 🔧 Configuration

### Update `Injaaz.py` for Native App

Add CORS headers for native app:

```python
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    
    # Enable CORS for native app
    CORS(app, resources={
        r"/api/*": {"origins": ["capacitor://localhost", "ionic://localhost", "http://localhost", "http://localhost:8080"]}
    })
    
    # ... rest of your code
```

### Update API Routes

Ensure all API routes work with native app headers.

---

## 📱 Native Features You Can Add

### 1. Camera Plugin
```bash
npm install @capacitor/camera
```

```javascript
import { Camera } from '@capacitor/camera';

const takePicture = async () => {
  const image = await Camera.getPhoto({
    quality: 90,
    allowEditing: false,
    resultType: 'base64'
  });
  return image.base64String;
};
```

### 2. File System
```bash
npm install @capacitor/filesystem
```

### 3. Network Status
```bash
npm install @capacitor/network
```

### 4. Push Notifications
```bash
npm install @capacitor/push-notifications
```

---

## 🏗️ Build Process

### Android (Play Store)

1. **Open in Android Studio:**
   ```bash
   npx cap open android
   ```

2. **Build APK:**
   - Build → Generate Signed Bundle / APK
   - Choose "Android App Bundle" for Play Store
   - Create keystore (save password!)

3. **Upload to Play Store:**
   - Go to Google Play Console
   - Create new app
   - Upload AAB file
   - Fill store listing
   - Submit for review

### iOS (App Store)

1. **Open in Xcode:**
   ```bash
   npx cap open ios
   ```

2. **Configure:**
   - Set Bundle Identifier
   - Add signing certificates
   - Set version number

3. **Archive & Upload:**
   - Product → Archive
   - Distribute App
   - Upload to App Store Connect

4. **Submit:**
   - Go to App Store Connect
   - Fill app information
   - Submit for review

---

## 🔄 Development Workflow

### 1. Make Changes to Web App
Edit your Flask templates, static files, etc.

### 2. Sync to Native
```bash
npx cap sync
```

### 3. Test
```bash
# Android
npx cap open android

# iOS
npx cap open ios
```

### 4. Build & Deploy
Follow platform-specific build steps above.

---

## 📋 Checklist for Store Submission

### Android Play Store
- [ ] App icon (512x512)
- [ ] Feature graphic (1024x500)
- [ ] Screenshots (at least 2)
- [ ] Privacy policy URL
- [ ] App description
- [ ] Category selection
- [ ] Content rating
- [ ] Signed AAB file

### iOS App Store
- [ ] App icon (1024x1024)
- [ ] Screenshots (all required sizes)
- [ ] Privacy policy URL
- [ ] App description
- [ ] Category selection
- [ ] Age rating
- [ ] Signed IPA file

---

## 🎯 Next Steps

1. **Install Node.js** (if not already installed)
2. **Run:** `npm install` in project root
3. **Initialize:** `npx cap init`
4. **Add platforms:** `npx cap add android` (and iOS if on Mac)
5. **Sync:** `npx cap sync`
6. **Open:** `npx cap open android`

---

## 💡 Tips

- **Development:** Use `server.url` in `capacitor.config.ts` to point to your Render URL
- **Production:** Remove `server.url` to use bundled web assets
- **Testing:** Use Android Studio emulator or physical device
- **Updates:** After web changes, always run `npx cap sync`

---

## 🆘 Troubleshooting

### "Web assets not found"
- Check `webDir` in `capacitor.config.ts`
- Run `npx cap sync`

### "Build failed"
- Check Android SDK is installed
- Check Xcode is updated (iOS)

### "App not loading"
- Check `server.url` in config
- Check CORS settings in Flask

---

## 📚 Resources

- [Capacitor Docs](https://capacitorjs.com/docs)
- [Android Guide](https://capacitorjs.com/docs/android)
- [iOS Guide](https://capacitorjs.com/docs/ios)
- [Play Store Guide](https://support.google.com/googleplay/android-developer)
- [App Store Guide](https://developer.apple.com/app-store/)

---

**Ready to build?** Start with Step 1 above! 🚀

