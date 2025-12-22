#!/usr/bin/env bash
# Build script for Render deployment

set -o errexit

# Install Python dependencies
pip install -r requirements-prods.txt

# Create necessary directories
mkdir -p generated/uploads
mkdir -p generated/submissions
mkdir -p generated/jobs

echo "Build completed successfully!"
