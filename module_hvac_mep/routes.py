# module_hvac_mep/routes.py
import os
import json
import time
import base64
import re
import traceback
import logging
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, jsonify, url_for, send_from_directory, send_file, Response
import requests
from io import BytesIO

# CRITICAL FIX: Define logger FIRST before using it
logger = logging.getLogger(__name__)

# common utilities (ensure common/utils.py exists)
from common.utils import (
    random_id,
    save_uploaded_file,
    save_uploaded_file_cloud,
    upload_base64_to_cloud,
)
from common.db_utils import (
    create_submission_db,
    create_job_db,
    update_job_progress_db,
    complete_job_db,
    fail_job_db,
    get_job_status_db,
    get_submission_db
)
from app.models import db, User
from app.middleware import token_required, module_access_required
from app.services.cloudinary_service import upload_local_file
from flask_jwt_extended import get_jwt_identity, jwt_required

# Rate limiting helper (import from auth routes)
def get_limiter():
    """Get rate limiter from current app"""
    try:
        return current_app.limiter
    except (AttributeError, RuntimeError):
        return None

def rate_limit_if_available(limit_str):
    """Decorator to apply rate limiting if limiter is available"""
    def decorator(f):
        limiter = get_limiter()
        if limiter:
            return limiter.limit(limit_str)(f)
        return f
    return decorator

# Import BOTH report generators
try:
    from .hvac_generators import create_excel_report, create_pdf_report
    logger.info("✅ Successfully imported hvac_generators")
except Exception as e:
    logger.error(f"❌ Failed to import generators: {e}")
    def create_excel_report(data, output_dir):
        raise NotImplementedError("Excel generator not available")
    def create_pdf_report(data, output_dir):
        raise NotImplementedError("PDF generator not available")

# import the external generator worker you added
try:
    from . import generator as hvac_generator
except Exception:
    hvac_generator = None  # we'll still allow fallback behavior if needed

try:
    from .generator import process_submission
except ImportError:
    # Fallback if generator.py doesn't exist
    def process_submission(submission_data, job_id, config):
        from common.db_utils import fail_job_db
        fail_job_db(job_id, "Generator not implemented")

BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BLUEPRINT_DIR)

# sensible defaults; prefer app config at runtime via get_paths()
DEFAULT_GENERATED_DIR = os.path.join(BASE_DIR, "generated")
DEFAULT_UPLOADS_DIR = os.path.join(DEFAULT_GENERATED_DIR, "uploads")
DEFAULT_JOBS_DIR = os.path.join(DEFAULT_GENERATED_DIR, "jobs")

# fallback executor for background tasks (used if app doesn't provide one)
from concurrent.futures import ThreadPoolExecutor

_FALLBACK_EXECUTOR = ThreadPoolExecutor(max_workers=2)

hvac_mep_bp = Blueprint(
    "hvac_mep_bp", __name__, template_folder="templates", static_folder="static"
)


def get_paths():
    """
    Return (GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR) using current_app config or defaults.
    Safe to call during request handling.
    """
    gen = (
        current_app.config.get("GENERATED_DIR", DEFAULT_GENERATED_DIR)
        if current_app
        else DEFAULT_GENERATED_DIR
    )
    uploads = (
        current_app.config.get("UPLOADS_DIR", DEFAULT_UPLOADS_DIR)
        if current_app
        else DEFAULT_UPLOADS_DIR
    )
    jobs = (
        current_app.config.get("JOBS_DIR", DEFAULT_JOBS_DIR)
        if current_app
        else DEFAULT_JOBS_DIR
    )
    executor = (
        current_app.config.get("EXECUTOR")
        if (current_app and current_app.config.get("EXECUTOR"))
        else _FALLBACK_EXECUTOR
    )
    return gen, uploads, jobs, executor


@hvac_mep_bp.route("/form", methods=["GET"])
@jwt_required()
def index():
    """HVAC&MEP form - requires authentication and module access"""
    from flask import redirect, url_for
    from flask_jwt_extended import get_jwt_identity
    
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return render_template('access_denied.html', 
                                 module='HVAC & MEP',
                                 message='Your account is inactive. Please contact an administrator.'), 403
        
        if not user.has_module_access('hvac_mep'):
            return render_template('access_denied.html',
                                 module='HVAC & MEP',
                                 message='You do not have access to this module. Please contact an administrator to grant access.'), 403
        
        return render_template("hvac_mep_form.html")
    except Exception as e:
        logger.error(f"Error checking module access: {str(e)}")
        # If JWT check fails, redirect to login
        return redirect(url_for('login_page'))


@hvac_mep_bp.route("/dropdowns", methods=["GET"])
def dropdowns():
    # prefer module-level dropdown_data.json (BLUEPRINT_DIR/dropdown_data.json)
    local = os.path.join(BLUEPRINT_DIR, "dropdown_data.json")
    if os.path.exists(local):
        with open(local, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    # fallback to empty object
    return jsonify({})


@hvac_mep_bp.route("/save-draft", methods=["POST"])
def save_draft():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    payload = request.get_json(force=True)
    draft_id = random_id("draft")
    drafts_dir = os.path.join(GENERATED_DIR, "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    with open(os.path.join(drafts_dir, f"{draft_id}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return jsonify({"status": "ok", "draft_id": draft_id})


# ---------- Helpers for signatures ----------
_DATAURL_RE = re.compile(r"data:(?P<mime>[^;]+);base64,(?P<data>.+)")


def save_signature_dataurl(dataurl, uploads_dir, prefix="signature"):
    """
    Upload signature to cloud storage - CLOUD ONLY.
    Returns (saved_filename_or_none, file_path_or_none, public_url) tuple.
    Raises exception if cloud upload fails.
    """
    if not dataurl:
        return None, None, None
    
    # Cloud upload only - no fallback
    cloud_url, is_cloud = upload_base64_to_cloud(dataurl, folder="signatures", prefix=prefix)
    if is_cloud and cloud_url:
        logger.info(f"✅ Signature uploaded to cloud: {cloud_url}")
        return None, None, cloud_url  # No local file
    
    # Should never reach here due to exception in upload_base64_to_cloud
    raise Exception("Cloud storage required but signature upload failed")


# ---------- Submit route (handles multi-item + per-item photos + signatures) ----------
@hvac_mep_bp.route("/submit", methods=["POST"])
@rate_limit_if_available('10 per minute')  # Limit form submissions
def submit():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()

    # Ensure directories exist
    os.makedirs(GENERATED_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(JOBS_DIR, exist_ok=True)

    try:
        # If the client used the multi-item UI, it will post items_count and item_* fields.
        # We'll handle both cases: multi-item (items_count present) and legacy single-file uploads.

        # Basic form fields
        site_name = request.form.get("site_name", "")
        visit_date = request.form.get("visit_date", "")
        
        # Validate required fields
        if not site_name or not site_name.strip():
            return error_response("Site name is required", status_code=400, error_code='VALIDATION_ERROR')
        
        # Validate date
        if visit_date:
            try:
                parsed_date = datetime.strptime(visit_date, '%Y-%m-%d').date()
                if parsed_date > datetime.now().date():
                    return error_response("Visit date cannot be in the future", status_code=400, error_code='VALIDATION_ERROR')
            except ValueError:
                return error_response("Invalid date format. Use YYYY-MM-DD", status_code=400, error_code='VALIDATION_ERROR')

        # Signatures (data URLs). We'll persist them to files.
        tech_sig_dataurl = request.form.get("tech_signature") or request.form.get("tech_signature_data") or ""
        opman_sig_dataurl = request.form.get("opMan_signature") or request.form.get("opManSignatureData") or ""

        tech_sig_file = None
        opman_sig_file = None
        if tech_sig_dataurl:
            # Upload to cloud and get URL
            fname, fpath, url = save_signature_dataurl(tech_sig_dataurl, UPLOADS_DIR, prefix="tech_sig")
            if url:  # Check for URL, not fname (cloud upload returns None for fname)
                tech_sig_file = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
        if opman_sig_dataurl:
            fname, fpath, url = save_signature_dataurl(opman_sig_dataurl, UPLOADS_DIR, prefix="opman_sig")
            if url:  # Check for URL, not fname (cloud upload returns None for fname)
                opman_sig_file = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}

        # Determine items_count
        try:
            items_count = int(request.form.get("items_count", "0") or 0)
        except Exception:
            items_count = 0

        items = []

        if items_count and items_count > 0:
            # Parse each item and its files
            for i in range(items_count):
                asset = request.form.get(f"item_{i}_asset", "")
                system = request.form.get(f"item_{i}_system", "")
                description = request.form.get(f"item_{i}_description", "")

                photos_saved = []
                # Files for this item are expected with field name item_{i}_photo (can appear multiple times)
                file_field = f"item_{i}_photo"
                uploaded_files = request.files.getlist(file_field) or []
                for f in uploaded_files:
                    if f and getattr(f, "filename", None):
                        try:
                            # Upload to cloud (required)
                            result = save_uploaded_file_cloud(f, UPLOADS_DIR, folder="hvac_photos")
                            photos_saved.append({
                                "field": file_field,
                                "saved": None,
                                "path": None,
                                "url": result["url"],
                                "is_cloud": True
                            })
                        except Exception as e:
                            logger.error(f"Failed to upload photo: {e}")
                            return jsonify({"error": f"Cloud storage error: {str(e)}"}), 500

                items.append(
                    {
                        "asset": asset,
                        "system": system,
                        "description": description,
                        "photos": photos_saved,
                    }
                )
        else:
            # Legacy/fallback: collect any file fields in request.files and attach them as top-level files
            # Also attempt to parse a single item from form fields if present
            # Collect files
            saved_files = []
            for key in request.files:
                # Ignore any item_x_photo style keys if they existed but items_count was 0
                f = request.files.get(key)
                if f and getattr(f, "filename", None):
                    try:
                        result = save_uploaded_file_cloud(f, UPLOADS_DIR, folder="hvac_photos")
                        saved_files.append({
                            "field": key,
                            "saved": None,
                            "path": None,
                            "url": result["url"],
                            "is_cloud": True
                        })
                    except Exception as e:
                        logger.error(f"Failed to upload file: {e}")
                        return jsonify({"error": f"Cloud storage error: {str(e)}"}), 500

            # If there are explicit item fields (single item), capture them
            asset = request.form.get("asset") or request.form.get("item_0_asset") or ""
            system = request.form.get("system") or request.form.get("item_0_system") or ""
            description = request.form.get("description") or request.form.get("item_0_description") or ""

            if asset or system or description or saved_files:
                items.append(
                    {
                        "asset": asset,
                        "system": system,
                        "description": description,
                        "photos": saved_files,
                    }
                )

        # Create submission in database
        submission_record = {
            "site_name": site_name,
            "visit_date": visit_date,
            "tech_signature": tech_sig_file,
            "opman_signature": opman_sig_file,
            "items": items,
            "base_url": request.host_url.rstrip('/'),
            "created_at": datetime.utcnow().isoformat(),
        }

        # Get user_id from JWT token if available
        user_id = None
        try:
            from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
            try:
                verify_jwt_in_request(optional=True)
                user_id = get_jwt_identity()
                if user_id:
                    logger.info(f"✅ Submission will be associated with user_id: {user_id}")
                else:
                    logger.warning("⚠️ JWT token verified but no user_id found")
            except Exception as jwt_error:
                logger.debug(f"JWT token not available or invalid: {jwt_error}")
                # No token or invalid token - submission will be anonymous
        except Exception as e:
            logger.debug(f"JWT verification error: {e}")
            pass  # JWT not available
        
        submission = create_submission_db(
            module_type='hvac_mep',
            form_data=submission_record,
            site_name=site_name,
            visit_date=visit_date,
            user_id=user_id
        )
        sub_id = submission.submission_id

        # Create job in database
        job = create_job_db(submission)
        job_id = job.job_id

        logger.info(f"Starting background task for job {job_id}")
        logger.debug(f"Executor object: {EXECUTOR}")
        
        # Submit to executor with submission_id instead of record
        if EXECUTOR:
            # Add callback to catch any errors
            future = EXECUTOR.submit(
                process_job,
                sub_id,
                job_id,
                current_app.config,
                current_app._get_current_object()
            )
            
            # Add error callback
            def log_exception(fut):
                try:
                    fut.result()  # This will raise if the worker had an exception
                except Exception as e:
                    logger.error(f"❌ FATAL: Background job {job_id} crashed: {e}")
                    logger.error(traceback.format_exc())
            
            future.add_done_callback(log_exception)
            logger.info(f"✅ Background job {job_id} submitted to executor")
        else:
            logger.error("ThreadPoolExecutor not found in app config")
            return jsonify({'error': 'Background processing not available'}), 500

        return jsonify({"status": "queued", "job_id": job_id, "submission_id": sub_id, "items": len(items)})
    
    except Exception as e:
        logger.error(f"Submission failed: {str(e)}")
        logger.error(traceback.format_exc())
        return error_response('Submission failed', status_code=500, error_code='INTERNAL_ERROR')


@hvac_mep_bp.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    try:
        job_data = get_job_status_db(job_id)
        if not job_data:
            return error_response("Job not found", status_code=404, error_code='NOT_FOUND')
        return jsonify(job_data)
    except Exception as e:
        logger.error(f"Status check failed for {job_id}: {e}")
        logger.error(traceback.format_exc())
        return error_response("Status check failed", status_code=500, error_code='INTERNAL_ERROR')


@hvac_mep_bp.route("/generated/<path:filename>", methods=["GET"])
def download_generated(filename):
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    # allow nested paths like uploads/<name>
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)


@hvac_mep_bp.route("/download/<job_id>/<file_type>", methods=["GET"])
def download_file(job_id, file_type):
    """
    Download proxy route that fetches files from Cloudinary or local storage
    and serves them with proper download headers for auto-download.
    
    Args:
        job_id: Job ID to get file URLs from
        file_type: 'excel' or 'pdf'
    """
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    
    try:
        # Get job data from database
        job_data = get_job_status_db(job_id)
        if not job_data:
            logger.error(f"Job not found: {job_id}")
            return jsonify({"error": "Job not found"}), 404
        
        # Log the job_data structure (debug level only)
        logger.debug(f"Job data for {job_id}: {type(job_data)}")
        logger.debug(f"Job data keys: {list(job_data.keys()) if isinstance(job_data, dict) else 'Not a dict'}")
        
        # Extract results - try multiple possible keys
        results = {}
        if isinstance(job_data, dict):
            results = job_data.get('results', {}) or job_data.get('result_data', {}) or job_data.get('results_data', {})
            # If results is a string (JSON), parse it
            if isinstance(results, str):
                try:
                    import json
                    results = json.loads(results)
                except:
                    logger.warning(f"Failed to parse results as JSON")
                    results = {}
        
        if not results:
            logger.error(f"Job results not found for {job_id}")
            return error_response("Job results not found", status_code=404, error_code='NOT_FOUND')
        
        logger.debug(f"Results for {job_id}: {list(results.keys()) if isinstance(results, dict) else type(results)}")
        
        # Get file URL and filename based on file_type
        if file_type == 'excel':
            file_url = results.get('excel') or results.get('excel_url')
            filename = results.get('excel_filename', 'hvac_report.xlsx')
        elif file_type == 'pdf':
            file_url = results.get('pdf') or results.get('pdf_url')
            filename = results.get('pdf_filename', 'hvac_report.pdf')
        else:
            return error_response("Invalid file type. Use 'excel' or 'pdf'", status_code=400, error_code='VALIDATION_ERROR')
        
        if not file_url:
            return error_response(f"{file_type.upper()} file URL not found", status_code=404, error_code='NOT_FOUND')
        
        # Check if it's a Cloudinary URL or local URL
        if file_url.startswith('http://') or file_url.startswith('https://'):
            # Cloudinary URL - fetch and serve
            try:
                logger.debug(f"Fetching {file_type.upper()} file from Cloudinary: {file_url}")
                # Remove ?attachment=true if present
                clean_url = file_url.split('?')[0]
                logger.debug(f"Clean URL (removed query params): {clean_url}")
                
                # Use the original URL directly - Cloudinary URLs work fine as-is
                response = requests.get(clean_url, timeout=60, stream=True)
                response.raise_for_status()
                logger.debug(f"Successfully fetched {file_type.upper()} file, status: {response.status_code}, content-length: {response.headers.get('Content-Length', 'unknown')}")
                
                # Read file content into BytesIO
                file_content = response.content
                file_data = BytesIO(file_content)
                file_data.seek(0)  # Reset to beginning
                
                # Determine content type
                if file_type == 'excel':
                    mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                else:  # pdf
                    mimetype = 'application/pdf'
                
                # Verify file content is not empty
                if len(file_content) == 0:
                    logger.error(f"Empty file content received from Cloudinary: {file_url}")
                    return jsonify({"error": "File content is empty"}), 500
                
                logger.debug(f"Serving file: {filename}, size: {len(file_content)} bytes, type: {mimetype}")
                
                # Serve with download headers
                return send_file(
                    file_data,
                    mimetype=mimetype,
                    as_attachment=True,
                    download_name=filename
                )
            except Exception as e:
                logger.error(f"Error fetching from Cloudinary: {str(e)}")
                logger.error(traceback.format_exc())
                return error_response("Failed to fetch file from Cloudinary", status_code=500, error_code='STORAGE_ERROR')
        else:
            # Local URL - extract filename and serve from local storage
            # Remove leading slash and 'generated/' if present
            local_filename = file_url.lstrip('/').replace('generated/', '')
            local_path = os.path.join(GENERATED_DIR, local_filename)
            
            if not os.path.exists(local_path):
                return error_response("File not found locally", status_code=404, error_code='NOT_FOUND')
            
            return send_file(local_path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        logger.error(traceback.format_exc())
        return error_response("Download failed", status_code=500, error_code='INTERNAL_ERROR')

def process_job(sub_id, job_id, config, app):
    """Background worker: Generate BOTH Excel AND PDF reports"""
    logger.debug(f"process_job called with sub_id={sub_id}, job_id={job_id}")
    from common.module_base import process_report_job
    from .hvac_generators import create_excel_report, create_pdf_report
    
    process_report_job(
        sub_id=sub_id,
        job_id=job_id,
        app=app,
        module_name='hvac',
        create_excel_report=create_excel_report,
        create_pdf_report=create_pdf_report
    )


# ---------- Progressive Upload Endpoints ----------

@hvac_mep_bp.route("/upload-photo", methods=["POST"])
@rate_limit_if_available('20 per minute')  # Allow multiple photos per submission
def upload_photo():
    """
    Upload a single photo immediately to cloud storage.
    Used by progressive upload to upload photos when adding each item.
    Returns: {"success": true, "url": "cloudinary_url"}
    """
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    
    try:
        # Expect a single file with field name 'photo'
        if 'photo' not in request.files:
            logger.error("No photo file in request")
            return error_response("No photo file provided", status_code=400, error_code='VALIDATION_ERROR')
        
        photo_file = request.files['photo']
        if photo_file.filename == '':
            logger.error("Empty filename provided")
            return error_response("Empty filename", status_code=400, error_code='VALIDATION_ERROR')
        
        logger.info(f"Uploading photo: {photo_file.filename}")
        
        # Upload directly to cloud storage with proper error handling
        try:
            result = save_uploaded_file_cloud(photo_file, UPLOADS_DIR)
            
            if not result or not result.get("url"):
                logger.error("Upload returned no URL")
                return error_response("Upload failed - no URL returned", status_code=500, error_code='STORAGE_ERROR')
            
            logger.info(f"✅ Photo uploaded successfully: {result['url']}")
            
            return jsonify({
                "success": True,
                "url": result["url"],
                "is_cloud": result.get("is_cloud", False),
                "filename": photo_file.filename
            })
            
        except Exception as upload_error:
            logger.error(f"Upload error: {str(upload_error)}")
            logger.error(traceback.format_exc())
            
            # Try to save locally as fallback
            try:
                logger.info("Attempting local fallback save...")
                local_filename = save_uploaded_file(photo_file, UPLOADS_DIR)
                local_url = url_for('download_generated', filename=f"uploads/{local_filename}", _external=False)
                
                logger.info(f"✅ Saved locally as fallback: {local_url}")
                return jsonify({
                    "success": True,
                    "url": local_url,
                    "is_cloud": False,
                    "filename": local_filename,
                    "warning": "Saved locally (cloud upload failed)"
                })
            except Exception as local_error:
                logger.error(f"Local fallback also failed: {str(local_error)}")
                return error_response("Both cloud and local upload failed", status_code=500, error_code='STORAGE_ERROR')
        
    except Exception as e:
        logger.error(f"❌ Photo upload failed completely: {str(e)}")
        logger.error(traceback.format_exc())
        return error_response("Photo upload failed", status_code=500, error_code='INTERNAL_ERROR')


@hvac_mep_bp.route("/submit-with-urls", methods=["POST"])
@rate_limit_if_available('10 per minute')  # Limit form submissions
def submit_with_urls():
    """
    Submit form data where photos are already uploaded to cloud.
    Expects JSON payload with:
    {
        "site_name": "...",
        "visit_date": "...",
        "tech_signature": "data:image/png;base64,...",
        "opMan_signature": "data:image/png;base64,...",
        "items": [
            {
                "asset": "...",
                "system": "...",
                "description": "...",
                "photo_urls": ["cloudinary_url1", "cloudinary_url2", ...]
            }
        ]
    }
    """
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    
    # Ensure directories exist
    os.makedirs(GENERATED_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(JOBS_DIR, exist_ok=True)
    
    try:
        # Parse JSON payload
        payload = request.get_json(force=True)
        
        site_name = payload.get("site_name", "")
        visit_date = payload.get("visit_date", "")
        
        # Process signatures
        tech_sig_dataurl = payload.get("tech_signature", "")
        opman_sig_dataurl = payload.get("opMan_signature", "")
        
        tech_sig_file = None
        opman_sig_file = None
        
        if tech_sig_dataurl:
            fname, fpath, url = save_signature_dataurl(tech_sig_dataurl, UPLOADS_DIR, prefix="tech_sig")
            if url:  # Check for URL, not fname (cloud upload returns None for fname)
                tech_sig_file = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
        
        if opman_sig_dataurl:
            fname, fpath, url = save_signature_dataurl(opman_sig_dataurl, UPLOADS_DIR, prefix="opman_sig")
            if url:  # Check for URL, not fname (cloud upload returns None for fname)
                opman_sig_file = {"saved": fname, "path": fpath, "url": url, "is_cloud": True}
        
        # Process items with photo URLs
        items_data = payload.get("items", [])
        items = []
        
        for item_data in items_data:
            asset = item_data.get("asset", "")
            system = item_data.get("system", "")
            description = item_data.get("description", "")
            photo_urls = item_data.get("photo_urls", [])
            
            # Convert photo URLs to the format expected by generators
            photos_saved = []
            for url in photo_urls:
                photos_saved.append({
                    "saved": None,    # No local filename since already in cloud
                    "path": None,     # No local path
                    "url": url,       # Cloud URL
                    "is_cloud": True  # Flag for PDF generator to fetch from cloud
                })
            
            items.append({
                "asset": asset,
                "system": system,
                "description": description,
                "photos": photos_saved
            })
        
        # Create submission ID and save
        sub_id = random_id("sub")
        sub_dir = os.path.join(GENERATED_DIR, "submissions")
        os.makedirs(sub_dir, exist_ok=True)
        
        submission_data = {
            "submission_id": sub_id,
            "site_name": site_name,
            "visit_date": visit_date,
            "tech_signature": tech_sig_file,
            "opMan_signature": opman_sig_file,
            "items": items,
            "timestamp": datetime.now().isoformat(),
            "base_url": request.host_url.rstrip('/')
        }
        
        # Get user_id from JWT token if available
        user_id = None
        try:
            from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
            try:
                verify_jwt_in_request(optional=True)
                user_id = get_jwt_identity()
                if user_id:
                    logger.info(f"✅ Submission will be associated with user_id: {user_id}")
                else:
                    logger.warning("⚠️ JWT token verified but no user_id found")
            except Exception as jwt_error:
                logger.debug(f"JWT token not available or invalid: {jwt_error}")
                # No token or invalid token - submission will be anonymous
        except Exception as e:
            logger.debug(f"JWT verification error: {e}")
            pass  # JWT not available
        
        # Save submission to database
        submission_db = create_submission_db(
            module_type='hvac_mep',
            form_data=submission_data,
            site_name=site_name,
            visit_date=visit_date,
            user_id=user_id
        )
        sub_id = submission_db.submission_id
        
        logger.info(f"✅ Submission {sub_id} saved to database with {len(items)} items")
        
        # Create job in database
        job = create_job_db(submission_db)
        job_id = job.job_id
        
        logger.info(f"Starting background task for job {job_id}")
        
        # Submit to executor
        if EXECUTOR:
            future = EXECUTOR.submit(
                process_job,
                sub_id,
                job_id,
                current_app.config,
                current_app._get_current_object()
            )
            
            # Add error callback to catch silent failures
            def log_exception(fut):
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"❌ FATAL: Background job {job_id} crashed: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            future.add_done_callback(log_exception)
            logger.info(f"✅ Background job {job_id} submitted to executor")
        else:
            logger.error("ThreadPoolExecutor not found in app config")
            return jsonify({'error': 'Background processing not available'}), 500
        
        logger.info(f"🚀 Job {job_id} queued for submission {sub_id}")
        
        return jsonify({
            "status": "ok",
            "submission_id": sub_id,
            "job_id": job_id,
            "job_status_url": url_for("hvac_mep_bp.status", job_id=job_id, _external=False)
        })
        
    except Exception as e:
        logger.error(f"❌ Submit with URLs failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"status": "error", "error": str(e)}), 500