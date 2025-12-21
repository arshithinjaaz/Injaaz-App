#!/usr/bin/env python
"""Test Cloudinary connection and credentials"""
import os
import sys

# Load .env
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("CLOUDINARY CONNECTION TEST")
print("=" * 60)

# Check environment variables
cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
api_key = os.environ.get('CLOUDINARY_API_KEY', '')
api_secret = os.environ.get('CLOUDINARY_API_SECRET', '')

print(f"\n1. Environment Variables:")
print(f"   CLOUDINARY_CLOUD_NAME: {'✓ Set' if cloud_name else '✗ Missing'} ({cloud_name})")
print(f"   CLOUDINARY_API_KEY: {'✓ Set' if api_key else '✗ Missing'} ({api_key[:10]}... )" if api_key else '✗ Missing')
print(f"   CLOUDINARY_API_SECRET: {'✓ Set' if api_secret else '✗ Missing'} ({'*' * 10 if api_secret else 'Missing'})")

if not all([cloud_name, api_key, api_secret]):
    print("\n❌ FAILED: Missing credentials")
    sys.exit(1)

# Configure Cloudinary
print(f"\n2. Configuring Cloudinary...")
try:
    import cloudinary
    import cloudinary.uploader
    
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )
    print("   ✓ Cloudinary module configured")
except Exception as e:
    print(f"   ✗ Configuration failed: {e}")
    sys.exit(1)

# Test upload with minimal base64 image (1x1 transparent PNG)
print(f"\n3. Testing upload...")
test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

try:
    result = cloudinary.uploader.upload(
        file=test_image,
        folder="test",
        public_id=f"test_upload_{int(__import__('time').time())}"
    )
    
    url = result.get('secure_url')
    print(f"   ✓ Upload successful!")
    print(f"   URL: {url}")
    print(f"   Public ID: {result.get('public_id')}")
    print(f"   Format: {result.get('format')}")
    
except Exception as e:
    print(f"   ✗ Upload FAILED: {e}")
    print(f"\n   Error details:")
    import traceback
    traceback.print_exc()
    
    print(f"\n   Possible causes:")
    print(f"   - Invalid API credentials")
    print(f"   - Cloudinary account suspended/inactive")
    print(f"   - API rate limit exceeded")
    print(f"   - Network/firewall blocking cloudinary.com")
    print(f"\n   Action: Check https://cloudinary.com/console")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED - Cloudinary is working!")
print("=" * 60)
