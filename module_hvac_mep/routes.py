# module_hvac_mep/routes.py
import os
import json
import time
import base64
import re
import traceback
import logging
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, jsonify, url_for, send_from_directory

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
from app.models import db
from app.services.cloudinary_service import upload_local_file
from app.services.cloudinary_service import upload_local_file

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
def index():
    return render_template("hvac_mep_form.html")


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
            return jsonify({"error": "Site name is required"}), 400
        
        # Validate date
        if visit_date:
            try:
                parsed_date = datetime.strptime(visit_date, '%Y-%m-%d').date()
                if parsed_date > datetime.now().date():
                    return jsonify({"error": "Visit date cannot be in the future"}), 400
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

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

        submission = create_submission_db(
            module_type='hvac_mep',
            form_data=submission_record,
            site_name=site_name,
            visit_date=visit_date
        )
        sub_id = submission.submission_id

        # Create job in database
        job = create_job_db(submission)
        job_id = job.job_id

        logger.info(f"Starting background task for job {job_id}")

        # Submit to executor with submission_id instead of record
        executor = current_app.config.get('EXECUTOR')
        if executor:
            executor.submit(
                process_job,
                sub_id,
                job_id,
                current_app.config,
                current_app._get_current_object()
            )
        else:
            logger.error("ThreadPoolExecutor not found in app config")
            return jsonify({'error': 'Background processing not available'}), 500

        return jsonify({"status": "queued", "job_id": job_id, "submission_id": sub_id, "items": len(items)})
    
    except Exception as e:
        logger.error(f"Submission failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@hvac_mep_bp.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    try:
        job_data = get_job_status_db(job_id)
        if not job_data:
            return jsonify({"error": "unknown job"}), 404
        return jsonify(job_data)
    except Exception as e:
        logger.error(f"Status check failed for {job_id}: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Status check failed", "details": str(e)}), 500


@hvac_mep_bp.route("/generated/<path:filename>", methods=["GET"])
def download_generated(filename):
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    # allow nested paths like uploads/<name>
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)

def process_job(sub_id, job_id, config, app):
    """Background worker: Generate BOTH Excel AND PDF reports"""
    logger.info(f"🔴 DEBUG: process_job called for {job_id}")
    with app.app_context():
        try:
            GENERATED_DIR = config.get('GENERATED_DIR')
            
            logger.info(f"🔄 Processing job {job_id}")
            
            # Update progress: Starting
            update_job_progress_db(job_id, 10, status='processing')
        
            # Get submission data from database
            submission_data = get_submission_db(sub_id)
            if not submission_data:
                fail_job_db(job_id, "Submission not found")
                return
            
            # Use form_data from database
            submission_record = submission_data.get('form_data', {})
            
            # Generate Excel
            logger.info("📊 Generating Excel report...")
            update_job_progress_db(job_id, 30)
            excel_path = create_excel_report(submission_record, GENERATED_DIR)
            excel_filename = os.path.basename(excel_path)
            logger.info(f"✅ Excel created: {excel_filename}")
            
            # Upload Excel to Cloudinary
            update_job_progress_db(job_id, 45)
            excel_url = upload_local_file(excel_path, f"hvac_excel_{sub_id}")
            if not excel_url:
                base_url = submission_record.get('base_url', '')
                excel_url = f"{base_url}/generated/{excel_filename}"
                logger.warning("⚠️ Excel cloud upload failed, using local URL")
            else:
                logger.info(f"✅ Excel uploaded to cloud: {excel_url}")
            
            # Generate PDF
            logger.info("📄 Generating PDF report...")
            update_job_progress_db(job_id, 60)
            pdf_path = create_pdf_report(submission_record, GENERATED_DIR)
            pdf_filename = os.path.basename(pdf_path)
            logger.info(f"✅ PDF created: {pdf_filename}")
            
            # Upload PDF to Cloudinary
            update_job_progress_db(job_id, 80)
            pdf_url = upload_local_file(pdf_path, f"hvac_pdf_{sub_id}")
            if not pdf_url:
                base_url = submission_record.get('base_url', '')
                pdf_url = f"{base_url}/generated/{pdf_filename}"
                logger.warning("⚠️ PDF cloud upload failed, using local URL")
            else:
                logger.info(f"✅ PDF uploaded to cloud: {pdf_url}")
            
            # Mark complete
            results = {
                'excel': excel_url,
                'pdf': pdf_url,
                'excel_filename': excel_filename,
                'pdf_filename': pdf_filename
            }
            
            complete_job_db(job_id, results)
            logger.info(f"✅ Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {str(e)}")
            logger.error(traceback.format_exc())
            fail_job_db(job_id, str(e))


# ---------- Progressive Upload Endpoints ----------

@hvac_mep_bp.route("/upload-photo", methods=["POST"])
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
            return jsonify({"success": False, "error": "No photo file provided"}), 400
        
        photo_file = request.files['photo']
        if photo_file.filename == '':
            logger.error("Empty filename provided")
            return jsonify({"success": False, "error": "Empty filename"}), 400
        
        logger.info(f"Uploading photo: {photo_file.filename}")
        
        # Upload directly to cloud storage with proper error handling
        try:
            result = save_uploaded_file_cloud(photo_file, UPLOADS_DIR)
            
            if not result or not result.get("url"):
                logger.error("Upload returned no URL")
                return jsonify({"success": False, "error": "Upload failed - no URL returned"}), 500
            
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
                return jsonify({"success": False, "error": f"Both cloud and local upload failed: {str(local_error)}"}), 500
        
    except Exception as e:
        logger.error(f"❌ Photo upload failed completely: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@hvac_mep_bp.route("/submit-with-urls", methods=["POST"])
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
        
        # Save submission to database
        submission_db = create_submission_db(
            module_type='hvac_mep',
            form_data=submission_data,
            site_name=site_name,
            visit_date=visit_date
        )
        sub_id = submission_db.submission_id
        
        logger.info(f"✅ Submission {sub_id} saved to database with {len(items)} items")
        
        # Create job in database
        job = create_job_db(submission_db)
        job_id = job.job_id
        
        logger.info(f"Starting background task for job {job_id}")
        
        # Submit to executor
        executor = current_app.config.get('EXECUTOR')
        if executor:
            executor.submit(
                process_job,
                sub_id,
                job_id,
                current_app.config,
                current_app._get_current_object(),
                current_app._get_current_object()
            )
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