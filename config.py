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

# ============================================================
# PRODUCTION CREDENTIALS (Hardcoded)
# ============================================================

# SECRET_KEY - Used for session encryption and CSRF protection
SECRET_KEY = "VhfEWs6mHfBUVBaY-S01jxFXDdIa3sVANTqnm7LJH9I"

# CLOUDINARY - Image hosting service
CLOUDINARY_CLOUD_NAME = "dv7kljagk"
CLOUDINARY_API_KEY = "863137649681362"
CLOUDINARY_API_SECRET = "2T8gWf0H--OH2T55rcYS9qXm9Bg"

# FLASK ENVIRONMENT
FLASK_ENV = "production"  # Set to 'development' for local testing

# REDIS (Upstash - for rate limiting and background tasks)
REDIS_URL = "rediss://default:AY6qAAIncDE5ZmJhYTkwN2E3ZWY0ZDY3YTcwZjEyY2E4N2IwMjViM3AxMzY1MjI@casual-wildcat-36522.upstash.io:6379"

# EMAIL (Optional - for HVAC module email reports)
MAIL_SERVER = None  # e.g., "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USERNAME = None
MAIL_PASSWORD = None
MAIL_USE_TLS = True
MAIL_DEFAULT_SENDER = None