import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GENERATED_DIR = os.path.join(BASE_DIR, "generated")
UPLOADS_DIR = os.path.join(GENERATED_DIR, "uploads")
JOBS_DIR = os.path.join(GENERATED_DIR, "jobs")

# simple limits
MAX_UPLOAD_FILESIZE = 10 * 1024 * 1024  # 10MB per file
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'csv'}

# To increase total upload size (all files combined):
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB total