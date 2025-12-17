"""
Health check script to identify issues in the Injaaz app
"""
import os
import sys
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ MISSING {description}: {filepath}")
        return False

def check_directory_exists(dirpath, description):
    """Check if a directory exists"""
    if os.path.isdir(dirpath):
        print(f"✅ {description}: {dirpath}")
        return True
    else:
        print(f"❌ MISSING {description}: {dirpath}")
        return False

def main():
    print("=" * 60)
    print("🔍 INJAAZ APP HEALTH CHECK")
    print("=" * 60)
    
    base = Path(__file__).parent
    issues = []
    
    # Check critical files
    print("\n📄 Checking Critical Files:")
    if not check_file_exists(base / "Injaaz.py", "Main app file"):
        issues.append("Missing Injaaz.py")
    if not check_file_exists(base / "config.py", "Config file"):
        issues.append("Missing config.py")
    
    # Check static assets
    print("\n🎨 Checking Static Assets:")
    if not check_file_exists(base / "static" / "logo.png", "Logo"):
        issues.append("Missing static/logo.png")
    if not check_file_exists(base / "static" / "dropdown_init.js", "Dropdown JS"):
        issues.append("Missing static/dropdown_init.js")
    if not check_file_exists(base / "static" / "form.js", "Form JS"):
        issues.append("Missing static/form.js")
    
    # Check templates
    print("\n📝 Checking Templates:")
    if not check_file_exists(base / "templates" / "dashboard.html", "Dashboard"):
        issues.append("Missing templates/dashboard.html")
    
    # Check HVAC/MEP module
    print("\n🔧 Checking HVAC/MEP Module:")
    if not check_directory_exists(base / "module_hvac_mep", "HVAC/MEP directory"):
        issues.append("Missing module_hvac_mep directory")
    else:
        if not check_file_exists(base / "module_hvac_mep" / "routes.py", "HVAC routes"):
            issues.append("Missing module_hvac_mep/routes.py")
        if not check_file_exists(base / "module_hvac_mep" / "templates" / "hvac_mep_form.html", "HVAC template"):
            issues.append("Missing module_hvac_mep/templates/hvac_mep_form.html")
        if not check_file_exists(base / "module_hvac_mep" / "dropdown_data.json", "HVAC dropdowns"):
            issues.append("Missing module_hvac_mep/dropdown_data.json")
    
    # Check common utilities
    print("\n🛠️ Checking Common Utilities:")
    if not check_file_exists(base / "common" / "utils.py", "Common utils"):
        issues.append("Missing common/utils.py")
    
    # Check generated directories
    print("\n📁 Checking Generated Directories:")
    check_directory_exists(base / "generated", "Generated directory")
    check_directory_exists(base / "generated" / "uploads", "Uploads directory")
    check_directory_exists(base / "generated" / "jobs", "Jobs directory")
    
    # Check dependencies
    print("\n📦 Checking Python Dependencies:")
    try:
        import flask
        print(f"✅ Flask installed: {flask.__version__}")
    except ImportError:
        print("❌ Flask NOT installed")
        issues.append("Flask not installed")
    
    try:
        import openpyxl
        print(f"✅ openpyxl installed")
    except ImportError:
        print("⚠️ openpyxl NOT installed (needed for Excel generation)")
    
    try:
        import reportlab
        print(f"✅ ReportLab installed")
    except ImportError:
        print("⚠️ ReportLab NOT installed (needed for PDF generation)")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    if issues:
        print(f"❌ Found {len(issues)} issues:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print("\n🔧 Fix these issues and re-run the check.")
        return 1
    else:
        print("✅ All checks passed! Your app is healthy.")
        print("\n🚀 You can run: python Injaaz.py")
        return 0

if __name__ == "__main__":
    sys.exit(main())
