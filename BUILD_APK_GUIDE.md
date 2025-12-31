# 📱 Build APK File - Complete Step-by-Step Guide

## 🎯 Goal: Get Your APK File

This guide will help you create an APK file that you can install on Android phones.

---

## 📋 Prerequisites

- ✅ Android Studio installed
- ✅ Your project set up with Capacitor
- ✅ Android platform added

---

## 🚀 Step 1: Open Your Project in Android Studio

### Option A: From Command Line (Easiest)

1. **Open terminal/command prompt**
2. **Navigate to your project:**
   ```bash
   cd C:\Users\hp\Documents\Cursor-Injaaz\Injaaz-App
   ```

3. **Open in Android Studio:**
   ```bash
   npx cap open android
   ```

4. **Wait for Android Studio to open** (30 seconds - 2 minutes)

### Option B: From Android Studio

1. **Open Android Studio**
2. **Click "Open"** (or File → Open)
3. **Navigate to:** `C:\Users\hp\Documents\Cursor-Injaaz\Injaaz-App\android`
4. **Click "OK"**

---

## ⏳ Step 2: Wait for Gradle Sync

**First time only (5-15 minutes):**

1. **Android Studio will show:** "Gradle Sync" at bottom
2. **Progress bar** will show download progress
3. **Don't close Android Studio!** ⚠️
4. **Wait until it says:** "Gradle sync completed"

**If sync fails:**
- Check internet connection
- Click "Try Again"
- Or: File → Invalidate Caches → Restart

---

## 🔨 Step 3: Build Debug APK (For Testing)

### Quick Method - Debug APK:

1. **Build → Build Bundle(s) / APK(s) → Build APK(s)**
2. **Wait for build** (2-5 minutes)
3. **When done, click:** "locate" in the notification
4. **APK location:** 
   ```
   android\app\build\outputs\apk\debug\app-debug.apk
   ```

**This APK is for testing only!** Not for Play Store.

---

## 🏪 Step 4: Build Release APK (For Play Store)

### Method 1: Generate Signed APK (Recommended)

#### A. Create Keystore (One-Time Setup)

1. **Build → Generate Signed Bundle / APK**

2. **Select "APK"** (or "Android App Bundle" for Play Store)
   - **APK** = Install directly on phones
   - **AAB** = Upload to Play Store (recommended)

3. **Click "Create new..."** (to create keystore)

4. **Fill in the form:**
   - **Key store path:** Click folder icon, choose location
     - Example: `C:\Users\hp\Documents\injaaz-keystore.jks`
   - **Password:** Create strong password (SAVE THIS!)
   - **Confirm password:** Enter again
   - **Key alias:** `injaaz-key`
   - **Key password:** Same as keystore password (or different)
   - **Validity:** 25 years (default)
   - **Certificate info:**
     - First and Last Name: `Injaaz`
     - Organizational Unit: `Development`
     - Organization: `Injaaz`
     - City: Your city
     - State: Your state
     - Country Code: `US` (or your country)

5. **Click "OK"**

6. **IMPORTANT:** Save keystore password somewhere safe!
   - You'll need it for every update
   - If lost, you can't update the app!

#### B. Generate Signed APK

1. **Keystore path:** Should be filled automatically
2. **Enter passwords:**
   - Key store password
   - Key password
3. **Build variant:** Select **"release"**
4. **Click "Next"**

5. **Select build type:**
   - **APK:** For direct installation
   - **Android App Bundle (AAB):** For Play Store (recommended)
6. **Click "Create"**

7. **Wait for build** (2-5 minutes)

8. **When done:**
   - Click "locate" in notification
   - Or go to: `android\app\release\app-release.apk`

---

## 📁 Step 5: Find Your APK File

### Debug APK Location:
```
C:\Users\hp\Documents\Cursor-Injaaz\Injaaz-App\android\app\build\outputs\apk\debug\app-debug.apk
```

### Release APK Location:
```
C:\Users\hp\Documents\Cursor-Injaaz\Injaaz-App\android\app\release\app-release.apk
```

### Release AAB Location (Play Store):
```
C:\Users\hp\Documents\Cursor-Injaaz\Injaaz-App\android\app\release\app-release.aab
```

---

## 📲 Step 6: Install APK on Phone

### Method 1: Via USB

1. **Connect phone to computer** via USB
2. **Enable USB debugging** on phone
3. **Copy APK file** to phone
4. **On phone:** Open file manager → Find APK → Tap to install
5. **Allow "Install from unknown sources"** if prompted

### Method 2: Via Email/Cloud

1. **Upload APK** to Google Drive / Dropbox
2. **Download on phone**
3. **Tap to install**

### Method 3: Direct Install from Android Studio

1. **Connect phone** via USB
2. **Click Run button** ▶️ in Android Studio
3. **Select your phone**
4. **App installs automatically!**

---

## 🎯 Quick Reference: Build Types

| Type | Use For | Location |
|------|---------|----------|
| **Debug APK** | Testing | `app\build\outputs\apk\debug\` |
| **Release APK** | Direct install | `app\release\` |
| **Release AAB** | Play Store | `app\release\` |

---

## 🔄 Step 7: Update App (After Changes)

### When you make changes to your Flask app:

1. **Update web files** (templates, static files, etc.)

2. **Sync to native:**
   ```bash
   npx cap sync
   ```

3. **Rebuild APK:**
   - Build → Generate Signed Bundle / APK
   - Use same keystore
   - Enter password
   - Build!

---

## 🐛 Troubleshooting

### "Gradle sync failed"
- **Check internet** connection
- **Wait longer** (first time is slow)
- **Try:** File → Invalidate Caches → Restart

### "Build failed"
- **Check Logcat** for errors (bottom panel)
- **Common issues:**
  - Missing SDK
  - Network error
  - Syntax error in code

### "Keystore password wrong"
- **Check password** you saved
- **If lost:** You need to create new keystore (can't update old app)

### "APK not installing"
- **Enable "Install from unknown sources"** on phone
- **Settings → Security → Unknown sources** (enable)
- **Or:** Settings → Apps → Special access → Install unknown apps

### "App crashes on phone"
- **Check Logcat** in Android Studio
- **Connect phone** → Run app → Check errors
- **Common:** Missing permissions, network error

---

## ✅ Checklist

- [ ] Android Studio installed
- [ ] Project opened in Android Studio
- [ ] Gradle sync completed
- [ ] Keystore created (for release)
- [ ] APK built successfully
- [ ] APK file found
- [ ] APK installed on phone
- [ ] App works on phone!

---

## 📚 Visual Guide

### Android Studio Menu Path:
```
Build
  └── Build Bundle(s) / APK(s)
      └── Build APK(s) [Debug]
      
Build
  └── Generate Signed Bundle / APK
      └── Create new keystore
      └── Select release variant
      └── Generate APK/AAB
```

---

## 💡 Pro Tips

1. **Save keystore password** in password manager
2. **Backup keystore file** (if lost, can't update app)
3. **Test debug APK first** before building release
4. **Use AAB for Play Store** (smaller file size)
5. **Increment version** in `build.gradle` for each release

---

## 🎯 Next Steps After Getting APK

### For Testing:
- Install on your phone
- Test all features
- Fix any bugs
- Rebuild if needed

### For Play Store:
- Use AAB file (not APK)
- Follow Play Store submission guide
- Upload AAB to Google Play Console

---

## 🚀 Quick Start Commands

```bash
# 1. Open project
npx cap open android

# 2. After making changes
npx cap sync

# 3. Build in Android Studio
# (Use GUI - Build → Generate Signed Bundle / APK)
```

---

**Ready?** Follow the steps above to build your APK! 🎉

**Need help?** Check troubleshooting section or ask! 💪

