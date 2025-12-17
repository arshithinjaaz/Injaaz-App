import os
import uuid
import json
import time
from werkzeug.utils import secure_filename

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