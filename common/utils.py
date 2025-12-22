import os
import uuid
import json
import time
import logging
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

def random_id(prefix="job"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def save_uploaded_file(file_storage, uploads_dir):
    """
    Save an incoming werkzeug FileStorage securely.
    Returns saved filename (relative to uploads_dir).
    """
    ensure_dir(uploads_dir)
    filename = secure_filename(file_storage.filename)
    if not filename:
        filename = f"file_{int(time.time())}"
    unique = f"{uuid.uuid4().hex[:8]}"
    base, ext = os.path.splitext(filename)
    final_name = f"{base}_{unique}{ext}"
    path = os.path.join(uploads_dir, final_name)
    file_storage.save(path)
    return final_name

def write_job_state(jobs_dir, job_id, state_dict):
    ensure_dir(jobs_dir)
    job_file = os.path.join(jobs_dir, f"{job_id}.json")
    with open(job_file, 'w') as f:
        json.dump(state_dict, f)

def read_job_state(jobs_dir, job_id):
    job_file = os.path.join(jobs_dir, f"{job_id}.json")
    if not os.path.exists(job_file):
        return None
    with open(job_file, 'r') as f:
        return json.load(f)

def mark_job_started(jobs_dir, job_id, meta=None):
    state = {
        "job_id": job_id,
        "state": "started",
        "progress": 0,
        "results": [],
        "meta": meta or {},
        "created_at": time.time()
    }
    write_job_state(jobs_dir, job_id, state)
    return state

def update_job_progress(jobs_dir, job_id, progress, state='running', results=None):
    s = read_job_state(jobs_dir, job_id) or {}
    s.update({
        "state": state,
        "progress": progress,
    })
    if results is not None:
        s['results'] = results
    write_job_state(jobs_dir, job_id, s)

def mark_job_done(jobs_dir, job_id, results):
    s = read_job_state(jobs_dir, job_id) or {}
    s.update({
        "state": "done",
        "progress": 100,
        "results": results,
        "completed_at": time.time()
    })
    write_job_state(jobs_dir, job_id, s)

# Config-aware wrapper functions for background tasks
def mark_job_started_with_config(job_id, config, meta=None):
    """Wrapper that extracts JOBS_DIR from config dict"""
    jobs_dir = config.get('JOBS_DIR')
    return mark_job_started(jobs_dir, job_id, meta)

def update_job_progress_with_config(job_id, progress, config, state='running', results=None):
    """Wrapper that extracts JOBS_DIR from config dict"""
    jobs_dir = config.get('JOBS_DIR')
    return update_job_progress(jobs_dir, job_id, progress, state, results)

def mark_job_done_with_config(job_id, success, config, results=None, error=None):
    """Wrapper that extracts JOBS_DIR from config dict and handles error state"""
    jobs_dir = config.get('JOBS_DIR')
    if not success:
        result_data = {"error": error or "Unknown error"}
        s = read_job_state(jobs_dir, job_id) or {}
        s.update({
            "state": "failed",
            "progress": 0,
            "results": result_data,
            "completed_at": time.time()
        })
        write_job_state(jobs_dir, job_id, s)
    else:
        # Success case - MUST call mark_job_done with correct signature
        # mark_job_done(jobs_dir, job_id, results_dict)
        if results is None:
            results = {}
        mark_job_done(jobs_dir, job_id, results)  # This sets state="done"

def read_job_state_with_config(job_id, config):
    """Wrapper that extracts JOBS_DIR from config dict"""
    jobs_dir = config.get('JOBS_DIR')
    return read_job_state(jobs_dir, job_id)

# ---------- Cloud Storage Integration ----------

def upload_file_to_cloud(file_storage, folder="uploads"):
    """
    Upload file to Cloudinary and return secure URL.
    Falls back to local storage if Cloudinary is not configured.
    Returns (url, is_cloud) tuple.
    """
    try:
        from app.services.cloudinary_service import init_cloudinary, upload_local_file
        
        if not init_cloudinary():
            logger.warning("Cloudinary not configured, falling back to local storage")
            return None, False
        
        # Save temporarily to upload to Cloudinary
        import tempfile
        temp_dir = tempfile.gettempdir()
        filename = secure_filename(file_storage.filename)
        if not filename:
            filename = f"file_{int(time.time())}"
        unique = f"{uuid.uuid4().hex[:8]}"
        base, ext = os.path.splitext(filename)
        temp_filename = f"{base}_{unique}{ext}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        file_storage.save(temp_path)
        
        # Upload to Cloudinary
        public_id_prefix = f"{folder}/{base}_{unique}"
        url = upload_local_file(temp_path, public_id_prefix)
        
        # Clean up temp file
        try:
            os.remove(temp_path)
        except:
            pass
        
        if url:
            logger.info(f"✅ Uploaded to Cloudinary: {url}")
            return url, True
        else:
            logger.error("❌ Cloudinary upload failed")
            return None, False
            
    except Exception as e:
        logger.error(f"❌ Cloud upload error: {e}")
        return None, False

def save_uploaded_file_cloud(file_storage, uploads_dir, folder="uploads"):
    """
    Save file to cloud storage (Cloudinary) - CLOUD ONLY, NO LOCAL FALLBACK.
    Returns dict: {"url": str, "is_cloud": bool, "filename": str or None}
    Raises exception if cloud storage is not configured or upload fails.
    """
    cloud_url, is_cloud = upload_file_to_cloud(file_storage, folder=folder)
    
    if is_cloud and cloud_url:
        return {
            "url": cloud_url,
            "is_cloud": True,
            "filename": None  # Not stored locally
        }
    
    # No fallback - raise error
    logger.error("❌ CLOUD STORAGE REQUIRED: Cloudinary not configured or upload failed")
    raise Exception("Cloud storage (Cloudinary) is required. Please configure CLOUDINARY_* environment variables.")

def upload_base64_to_cloud(data_uri, folder="signatures", prefix="sig"):
    """
    Upload base64 data URI (signature) to Cloudinary - CLOUD ONLY.
    Returns (url, is_cloud) tuple.
    Raises exception if cloud storage fails.
    """
    try:
        from app.services.cloudinary_service import upload_base64_signature
        
        url = upload_base64_signature(data_uri, f"{folder}/{prefix}")
        if url:
            logger.info(f"✅ Uploaded signature to Cloudinary: {url}")
            return url, True
        else:
            logger.error("❌ CLOUD STORAGE REQUIRED: Signature upload to Cloudinary failed")
            raise Exception("Cloud storage (Cloudinary) signature upload failed. Check credentials.")
            
    except Exception as e:
        logger.error(f"❌ Cloud signature upload error: {e}")
        raise Exception(f"Cloud storage required but failed: {e}")

def get_image_for_pdf(image_info):
    """
    Get image data (path or BytesIO) for PDF generation.
    Handles both cloud URLs, local paths, and data URIs.
    
    Args:
        image_info: Can be a dict with 'url' or 'path' keys, or a string path
        
    Returns:
        (image_data, is_url) tuple where image_data is path or BytesIO stream
    """
    import io
    import requests
    import base64
    
    # Handle string path (legacy)
    if isinstance(image_info, str):
        # Check if it's a data URI (base64 encoded image)
        if image_info.startswith('data:image'):
            try:
                # Extract base64 data after comma
                header, encoded = image_info.split(',', 1)
                image_data = base64.b64decode(encoded)
                return io.BytesIO(image_data), True
            except Exception as e:
                logger.error(f"Failed to decode data URI: {e}")
                return None, False
        
        if os.path.exists(image_info):
            return image_info, False
        return None, False
    
    # Handle dict with url or path
    if isinstance(image_info, dict):
        # Try url field first - check if it's a data URI
        url = image_info.get('url', '')
        if url and url.startswith('data:image'):
            try:
                # Extract base64 data after comma
                header, encoded = url.split(',', 1)
                image_data = base64.b64decode(encoded)
                return io.BytesIO(image_data), True
            except Exception as e:
                logger.error(f"Failed to decode data URI: {e}")
                return None, False
        
        # Try cloud URL
        if url and image_info.get('is_cloud'):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                return io.BytesIO(response.content), True
            except Exception as e:
                logger.error(f"Failed to fetch cloud image {url}: {e}")
                # Fall through to try local path
        
        # Try local path
        path = image_info.get('path')
        if path and os.path.exists(path):
            return path, False
    
    return None, False