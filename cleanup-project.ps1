# PowerShell Script to Clean Up Injaaz Project
# Run this script to remove temporary and unwanted files

Write-Host "🧹 Starting Project Cleanup..." -ForegroundColor Green
Write-Host ""

# Remove Python cache
Write-Host "Removing Python cache files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path . -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "✅ Python cache removed" -ForegroundColor Green

# Remove IDE files
Write-Host "Removing IDE files..." -ForegroundColor Yellow
Remove-Item -Recurse -Force .vscode -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .idea -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Filter "*.swp" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path . -Recurse -Filter "*.swo" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "✅ IDE files removed" -ForegroundColor Green

# Remove OS files
Write-Host "Removing OS files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Filter ".DS_Store" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path . -Recurse -Filter "Thumbs.db" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path . -Recurse -Filter "desktop.ini" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "✅ OS files removed" -ForegroundColor Green

# Remove log files
Write-Host "Removing log files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "✅ Log files removed" -ForegroundColor Green

# Remove temporary files
Write-Host "Removing temporary files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Filter "*.tmp" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "✅ Temporary files removed" -ForegroundColor Green

# Optional: Remove documentation files (uncomment if needed)
# Write-Host "Removing documentation files..." -ForegroundColor Yellow
# $docsToRemove = @(
#     "PWA_GUIDE.md",
#     "PWA_SUMMARY.md",
#     "DEPLOYMENT_CHECKLIST_FINAL.md",
#     "NATIVE_APP_GUIDE.md",
#     "INSTALL_ANDROID_STUDIO.md",
#     "BUILD_APK_GUIDE.md",
#     "BUILD_APK_QUICK.md",
#     "NEXT_STEPS.md",
#     "QUICK_START.md",
#     "INSTALL_CHECKLIST.md",
#     "ANDROID_STUDIO_8GB_RAM.md"
# )
# foreach ($doc in $docsToRemove) {
#     if (Test-Path $doc) {
#         Remove-Item -Force $doc
#         Write-Host "  Removed: $doc" -ForegroundColor Gray
#     }
# }
# Write-Host "✅ Documentation files removed" -ForegroundColor Green

# Optional: Remove Node.js files (uncomment if not using Android Studio)
# Write-Host "Removing Node.js files..." -ForegroundColor Yellow
# Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
# Remove-Item -Force package.json -ErrorAction SilentlyContinue
# Remove-Item -Force package-lock.json -ErrorAction SilentlyContinue
# Remove-Item -Force capacitor.config.ts -ErrorAction SilentlyContinue
# Remove-Item -Recurse -Force android -ErrorAction SilentlyContinue
# Remove-Item -Recurse -Force ios -ErrorAction SilentlyContinue
# Remove-Item -Recurse -Force .capacitor -ErrorAction SilentlyContinue
# Write-Host "✅ Node.js files removed" -ForegroundColor Green

Write-Host ""
Write-Host "✅ Cleanup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Review removed files" -ForegroundColor White
Write-Host "  2. Test your application" -ForegroundColor White
Write-Host "  3. Commit changes to git" -ForegroundColor White
Write-Host "  4. Push to repository" -ForegroundColor White
Write-Host ""

