@echo off
REM Setup script for converting Injaaz PWA to Native App (Windows)

echo 🚀 Setting up Injaaz Native App with Capacitor...
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Node.js is not installed. Please install Node.js from https://nodejs.org/
    exit /b 1
)

echo ✅ Node.js version:
node --version
echo ✅ npm version:
npm --version
echo.

REM Install Capacitor dependencies
echo 📦 Installing Capacitor dependencies...
call npm install

REM Initialize Capacitor (if not already initialized)
if not exist "capacitor.config.ts" (
    echo 🔧 Capacitor config not found. Please run: npx cap init
    echo    When prompted:
    echo    - App name: Injaaz
    echo    - App ID: com.injaaz.app
    echo    - Web dir: static
) else (
    echo ✅ Capacitor config found
)

REM Add Android platform
if not exist "android" (
    echo 📱 Adding Android platform...
    call npx cap add android
) else (
    echo ✅ Android platform already exists
)

REM Sync web assets
echo 🔄 Syncing web assets to native platforms...
call npx cap sync

echo.
echo ✅ Setup complete!
echo.
echo 📱 Next steps:
echo    1. Android: npx cap open android
echo    2. Open Android Studio and build your app
echo.
echo 📚 See NATIVE_APP_GUIDE.md for detailed instructions
pause

