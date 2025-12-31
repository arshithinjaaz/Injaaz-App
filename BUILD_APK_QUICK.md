# ⚡ Quick APK Build Guide

## 🎯 Get APK in 5 Steps

### 1️⃣ Open Project
```bash
npx cap open android
```

### 2️⃣ Wait for Gradle Sync
- Wait 5-15 minutes (first time)
- Don't close Android Studio!

### 3️⃣ Build APK
- **Build → Build Bundle(s) / APK(s) → Build APK(s)**
- Wait 2-5 minutes

### 4️⃣ Find APK
- Click "locate" in notification
- Or: `android\app\build\outputs\apk\debug\app-debug.apk`

### 5️⃣ Install on Phone
- Copy APK to phone
- Tap to install
- Allow "unknown sources"

---

## 🏪 For Play Store (Release APK)

### Create Keystore (One-Time):
1. **Build → Generate Signed Bundle / APK**
2. **Click "Create new..."**
3. **Fill form, save password!**
4. **Select "release" variant**
5. **Choose "Android App Bundle"** (for Play Store)
6. **Click "Create"**

### APK Location:
```
android\app\release\app-release.apk
```

---

## 📱 Install APK

**Method 1:** Connect phone → Click Run ▶️ in Android Studio

**Method 2:** Copy APK to phone → Tap to install

---

**That's it!** See `BUILD_APK_GUIDE.md` for detailed steps.

