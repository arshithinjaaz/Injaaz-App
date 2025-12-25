#!/usr/bin/env python3
"""
Deployment Diagnostic Script
Run this on Render to diagnose deployment issues
"""
import os
import sys
import json

print("=" * 60)
print("🔍 INJAAZ APP DEPLOYMENT DIAGNOSTICS")
print("=" * 60)

# 1. Check Python version
print(f"\n✓ Python Version: {sys.version}")

# 2. Check environment variables
print("\n📋 Environment Variables:")
critical_vars = [
    'DATABASE_URL', 'SECRET_KEY', 'JWT_SECRET_KEY', 
    'CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'FLASK_ENV'
]

for var in critical_vars:
    value = os.getenv(var)
    if value:
        # Mask sensitive values
        if 'SECRET' in var or 'PASSWORD' in var:
            display = f"{value[:8]}..." if len(value) > 8 else "***"
        elif var == 'DATABASE_URL':
            # Show only scheme and host
            try:
                from urllib.parse import urlparse
                parsed = urlparse(value)
                display = f"{parsed.scheme}://{parsed.hostname}"
            except:
                display = value[:30] + "..."
        else:
            display = value[:30] + ("..." if len(value) > 30 else "")
        print(f"  ✓ {var}: {display}")
    else:
        print(f"  ✗ {var}: NOT SET")

# 3. Check database connection
print("\n🗄️  Database Connection:")
try:
    db_url = os.getenv('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        print(f"  ⚠️  WARNING: DATABASE_URL uses old 'postgres://' scheme")
        print(f"     SQLAlchemy requires 'postgresql://'")
        fixed_url = db_url.replace('postgres://', 'postgresql://', 1)
        print(f"  ℹ️  Will auto-convert to: {fixed_url[:30]}...")
    elif db_url.startswith('postgresql://'):
        print(f"  ✓ DATABASE_URL uses correct 'postgresql://' scheme")
    else:
        print(f"  ℹ️  Using default/local database")
    
    # Try to connect
    from Injaaz import create_app
    from app.models import db
    
    app = create_app()
    with app.app_context():
        db.engine.connect()
        print("  ✓ Database connection successful!")
        
        # Check tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"  ✓ Tables found: {', '.join(tables) if tables else 'NONE'}")
        
except Exception as e:
    print(f"  ✗ Database connection failed: {e}")
    import traceback
    traceback.print_exc()

# 4. Check file system
print("\n📁 File System:")
dirs = ['generated', 'generated/uploads', 'generated/jobs', 'generated/submissions']
for dir_path in dirs:
    exists = os.path.exists(dir_path)
    writable = os.access(dir_path, os.W_OK) if exists else False
    print(f"  {'✓' if exists else '✗'} {dir_path}: {'exists' if exists else 'MISSING'}, {'writable' if writable else 'NOT WRITABLE'}")

# 5. Check imports
print("\n📦 Module Imports:")
modules = [
    'flask', 'flask_sqlalchemy', 'flask_jwt_extended', 
    'cloudinary', 'reportlab', 'openpyxl', 'pandas'
]

for module in modules:
    try:
        __import__(module)
        print(f"  ✓ {module}")
    except ImportError as e:
        print(f"  ✗ {module}: {e}")

# 6. Check blueprint imports
print("\n🔌 Blueprint Imports:")
blueprints = [
    ('module_hvac_mep.routes', 'hvac_mep_bp'),
    ('module_civil.routes', 'civil_bp'),
    ('module_cleaning.routes', 'cleaning_bp'),
    ('app.auth.routes', 'auth_bp')
]

for module_path, attr_name in blueprints:
    try:
        module = __import__(module_path, fromlist=[attr_name])
        bp = getattr(module, attr_name, None)
        if bp:
            print(f"  ✓ {module_path}.{attr_name}")
        else:
            print(f"  ✗ {module_path}.{attr_name} - attribute not found")
    except Exception as e:
        print(f"  ✗ {module_path}.{attr_name}: {e}")

# 7. Check Cloudinary
print("\n☁️  Cloudinary Configuration:")
try:
    import cloudinary
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    if cloud_name:
        print(f"  ✓ Cloud Name: {cloud_name}")
        print(f"  ✓ API Key: {'SET' if os.getenv('CLOUDINARY_API_KEY') else 'NOT SET'}")
        print(f"  ✓ API Secret: {'SET' if os.getenv('CLOUDINARY_API_SECRET') else 'NOT SET'}")
    else:
        print("  ⚠️  Cloudinary not configured")
except Exception as e:
    print(f"  ✗ Cloudinary check failed: {e}")

# 8. Try to create app
print("\n🚀 App Creation Test:")
try:
    from Injaaz import create_app
    app = create_app()
    print(f"  ✓ Flask app created successfully")
    print(f"  ✓ Debug mode: {app.debug}")
    print(f"  ✓ Environment: {app.config.get('FLASK_ENV', 'unknown')}")
    
    # List registered blueprints
    blueprints = [bp.name for bp in app.blueprints.values()]
    print(f"  ✓ Registered blueprints: {', '.join(blueprints)}")
    
except Exception as e:
    print(f"  ✗ App creation failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 60)
print("\nIf you see errors above, fix them before deployment.")
print("Run this script on Render using: python diagnose_deployment.py")
