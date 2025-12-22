#!/usr/bin/env python3
"""
Quick test script to verify hardcoded credentials work
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SECRET_KEY, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, FLASK_ENV

print("=" * 60)
print("TESTING HARDCODED CREDENTIALS")
print("=" * 60)

# Test SECRET_KEY
print(f"\n✅ SECRET_KEY: {SECRET_KEY[:10]}... (length: {len(SECRET_KEY)})")
if len(SECRET_KEY) >= 32:
    print("   ✅ SECRET_KEY length is adequate (32+ chars)")
else:
    print("   ❌ SECRET_KEY too short!")

# Test Flask Environment
print(f"\n✅ FLASK_ENV: {FLASK_ENV}")

# Test Cloudinary
print(f"\n✅ CLOUDINARY_CLOUD_NAME: {CLOUDINARY_CLOUD_NAME}")
print(f"✅ CLOUDINARY_API_KEY: {CLOUDINARY_API_KEY}")
print(f"✅ CLOUDINARY_API_SECRET: {CLOUDINARY_API_SECRET[:5]}...{CLOUDINARY_API_SECRET[-5:]}")

# Set environment variables (as Injaaz.py does)
os.environ['CLOUDINARY_CLOUD_NAME'] = CLOUDINARY_CLOUD_NAME
os.environ['CLOUDINARY_API_KEY'] = CLOUDINARY_API_KEY
os.environ['CLOUDINARY_API_SECRET'] = CLOUDINARY_API_SECRET

# Test Cloudinary connection
print("\n" + "=" * 60)
print("TESTING CLOUDINARY CONNECTION")
print("=" * 60)

try:
    import cloudinary
    import cloudinary.api
    
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
    
    # Try to get account info
    result = cloudinary.api.ping()
    print(f"\n✅ Cloudinary connection SUCCESSFUL!")
    print(f"   Status: {result.get('status', 'unknown')}")
    
except Exception as e:
    print(f"\n❌ Cloudinary connection FAILED: {e}")

print("\n" + "=" * 60)
print("CREDENTIALS TEST COMPLETE")
print("=" * 60)
