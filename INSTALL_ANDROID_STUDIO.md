# 📱 Install Android Studio - Complete Guide for Beginners

## 🎯 What You Need

- **Windows 10/11** (you have this ✅)
- **8GB RAM minimum** (16GB recommended)
- **4GB free disk space** (more is better)
- **Internet connection** (for downloads)

---

## 📥 Step 1: Download Android Studio

1. **Go to:** https://developer.android.com/studio
2. **Click:** "Download Android Studio" (big green button)
3. **File:** `android-studio-*.exe` will download (~1GB)
4. **Wait for download** to complete

---

## 🔧 Step 2: Install Android Studio

1. **Double-click** the downloaded `.exe` file
2. **Click "Next"** on the welcome screen
3. **Choose components:**
   - ✅ Android Studio (required)
   - ✅ Android SDK (required)
   - ✅ Android Virtual Device (recommended - for emulator)
   - ✅ Performance (Intel HAXM) - if you have Intel processor
   - Click **"Next"**

4. **Choose installation location:**
   - Default is fine: `C:\Program Files\Android\Android Studio`
   - Or choose custom location
   - Click **"Next"**

5. **Choose Start Menu folder:**
   - Default is fine
   - Click **"Install"**

6. **Wait for installation** (5-10 minutes)
   - Progress bar will show
   - Don't close the window!

7. **Click "Next"** when done
8. **Click "Finish"**
   - ✅ Check "Start Android Studio" if you want to launch now

---

## 🚀 Step 3: First Launch Setup

### Initial Setup Wizard:

1. **Welcome Screen:**
   - Choose "Do not import settings" (first time)
   - Click **"OK"**

2. **Setup Wizard:**
   - Click **"Next"**

3. **Install Type:**
   - Choose **"Standard"** (recommended)
   - Click **"Next"**

4. **Select UI Theme:**
   - Choose **"IntelliJ"** (light) or **"Darcula"** (dark)
   - Click **"Next"**

5. **Verify Settings:**
   - Review the components to install
   - Click **"Next"**

6. **License Agreement:**
   - Read and accept all licenses
   - Click **"Finish"**

7. **Download Components:**
   - ⏳ **This takes 10-30 minutes!**
   - Android Studio will download:
     - Android SDK
     - Android SDK Platform
     - Android Emulator
     - Google Play services
   - **Don't close Android Studio!**
   - Progress bar will show download status

8. **Click "Finish"** when done

---

## ✅ Step 4: Verify Installation

1. **Android Studio should open**
2. **Check for updates:**
   - Help → Check for Updates
   - Install any updates if available

3. **Verify SDK:**
   - File → Settings → Appearance & Behavior → System Settings → Android SDK
   - You should see SDK platforms installed

---

## 🎓 Step 5: Learn the Interface

### Main Areas:

1. **Toolbar** (top)
   - Run button (green play ▶️)
   - Stop button (red square ⏹️)
   - Device selector

2. **Project Panel** (left)
   - Shows your files
   - Like Windows Explorer

3. **Editor** (center)
   - Where you edit code
   - Shows files you open

4. **Logcat** (bottom)
   - Shows app logs
   - Useful for debugging

---

## 📱 Step 6: Set Up Android Emulator (Optional)

### Create Virtual Device:

1. **Tools → Device Manager**
2. **Click "Create Device"**
3. **Choose device:**
   - Select "Phone" → "Pixel 5" (recommended)
   - Click **"Next"**

4. **Choose system image:**
   - Select latest Android version (e.g., "Android 13")
   - Click **"Download"** if needed (takes 5-10 minutes)
   - Click **"Next"**

5. **Verify configuration:**
   - Click **"Finish"**

6. **Start emulator:**
   - Click ▶️ play button next to device
   - Wait for emulator to boot (2-3 minutes first time)

---

## 🔌 Step 7: Connect Real Device (Alternative)

### Enable USB Debugging:

1. **On your Android phone:**
   - Settings → About Phone
   - Tap "Build Number" 7 times
   - "You are now a developer!" message appears

2. **Go back to Settings:**
   - Settings → Developer Options
   - Enable "USB Debugging"

3. **Connect phone:**
   - Connect via USB cable
   - Allow USB debugging on phone
   - Trust computer if prompted

4. **Verify in Android Studio:**
   - Device should appear in device selector

---

## ✅ Step 8: Test Installation

### Open Your Project:

1. **Open terminal/command prompt**
2. **Navigate to your project:**
   ```bash
   cd C:\Users\hp\Documents\Cursor-Injaaz\Injaaz-App
   ```

3. **Open in Android Studio:**
   ```bash
   npx cap open android
   ```

4. **Wait for Gradle sync:**
   - First time: 5-15 minutes
   - Progress bar at bottom
   - **Don't close Android Studio!**

5. **When sync completes:**
   - Click green ▶️ Run button
   - Select your device/emulator
   - App will build and install!

---

## 🐛 Troubleshooting

### "Gradle sync failed"
- **Check internet connection**
- **Wait longer** (first sync is slow)
- **Try:** File → Invalidate Caches → Restart

### "SDK not found"
- **File → Settings → Android SDK**
- **Click "Edit"** next to SDK location
- **Let it download SDK**

### "Emulator won't start"
- **Enable virtualization in BIOS:**
  - Restart computer
  - Enter BIOS (usually F2 or Delete)
  - Enable "Virtualization Technology" or "VT-x"
  - Save and exit

### "Device not detected"
- **Check USB cable** (use data cable, not charge-only)
- **Enable USB debugging** on phone
- **Install phone drivers** (usually auto-installs)

### "Out of memory"
- **Close other programs**
- **Increase Android Studio memory:**
  - Help → Edit Custom VM Options
  - Change `-Xmx2g` to `-Xmx4g` (if you have 16GB RAM)

---

## 📚 Learning Resources

### Official Guides:
- [Android Studio User Guide](https://developer.android.com/studio/intro)
- [Build Your First App](https://developer.android.com/training/basics/firstapp)

### Keyboard Shortcuts:
- **Run:** `Shift + F10`
- **Stop:** `Ctrl + F2`
- **Save All:** `Ctrl + S`
- **Find:** `Ctrl + F`

---

## ⏱️ Time Estimate

- **Download:** 10-30 minutes (depends on internet)
- **Install:** 5-10 minutes
- **First setup:** 10-30 minutes (SDK download)
- **Total:** ~30-70 minutes

**Worth it!** Once installed, you can build apps forever! 🚀

---

## ✅ Checklist

- [ ] Download Android Studio
- [ ] Install Android Studio
- [ ] Complete setup wizard
- [ ] Wait for SDK download
- [ ] Create emulator OR connect phone
- [ ] Open your project: `npx cap open android`
- [ ] Wait for Gradle sync
- [ ] Run app!

---

## 🎯 Next Steps After Installation

1. **Open your project:**
   ```bash
   npx cap open android
   ```

2. **Wait for Gradle sync** (first time is slow)

3. **Run the app:**
   - Click ▶️ Run button
   - Select device
   - Watch your app launch! 🎉

---

## 💡 Pro Tips

- **Be patient** - First setup takes time
- **Don't close** during downloads
- **Use emulator** for quick testing
- **Use real device** for better performance
- **Keep Android Studio updated**

---

**Ready?** Start with Step 1 above! 📥

Once installed, come back and run: `npx cap open android` 🚀

