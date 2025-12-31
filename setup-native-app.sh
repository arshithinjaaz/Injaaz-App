#!/bin/bash
# Setup script for converting Injaaz PWA to Native App

echo "🚀 Setting up Injaaz Native App with Capacitor..."
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js from https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js version: $(node --version)"
echo "✅ npm version: $(npm --version)"
echo ""

# Install Capacitor dependencies
echo "📦 Installing Capacitor dependencies..."
npm install

# Initialize Capacitor (if not already initialized)
if [ ! -f "capacitor.config.ts" ]; then
    echo "🔧 Capacitor config not found. Please run: npx cap init"
    echo "   When prompted:"
    echo "   - App name: Injaaz"
    echo "   - App ID: com.injaaz.app"
    echo "   - Web dir: static"
else
    echo "✅ Capacitor config found"
fi

# Add Android platform
if [ ! -d "android" ]; then
    echo "📱 Adding Android platform..."
    npx cap add android
else
    echo "✅ Android platform already exists"
fi

# Add iOS platform (Mac only)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [ ! -d "ios" ]; then
        echo "🍎 Adding iOS platform..."
        npx cap add ios
    else
        echo "✅ iOS platform already exists"
    fi
else
    echo "ℹ️  iOS platform skipped (not on Mac)"
fi

# Sync web assets
echo "🔄 Syncing web assets to native platforms..."
npx cap sync

echo ""
echo "✅ Setup complete!"
echo ""
echo "📱 Next steps:"
echo "   1. Android: npx cap open android"
echo "   2. iOS (Mac): npx cap open ios"
echo ""
echo "📚 See NATIVE_APP_GUIDE.md for detailed instructions"

