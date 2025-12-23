import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
# CONFIGURATION FROM ENVIRONMENT VARIABLES
# ============================================================

# SECRET_KEY - Used for session encryption and CSRF protection
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-jwt-secret")

# CLOUDINARY - Image hosting service
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# DATABASE - PostgreSQL for production
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'injaaz.db')}")

# FLASK ENVIRONMENT
FLASK_ENV = os.getenv("FLASK_ENV", "production")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# REDIS (for rate limiting and background tasks)
REDIS_URL = os.getenv("REDIS_URL")

# JWT Settings
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600))  # 1 hour
JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", 2592000))  # 30 days

# EMAIL (Optional - for HVAC module email reports)
MAIL_SERVER = os.getenv("MAIL_SERVER")
MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@injaaz.com")

# Application
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")

# Security
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# SQLALCHEMY
SQLALCHEMY_DATABASE_URI = DATABASE_URL
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
