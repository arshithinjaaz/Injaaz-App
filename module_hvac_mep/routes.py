import os
import json
import time
import traceback
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, jsonify, url_for, send_from_directory

# common utilities (ensure common/utils.py exists)
from common.utils import random_id, save_uploaded_file, mark_job_started, update_job_progress, mark_job_done, read_job_state

# try to import generators (placeholders available in hvac_generators.py)
try:
    from .hvac_generators import create_excel_report, create_pdf_report
except Exception:
    # fallback placeholders are defined there already, but keep defensive code
    def create_excel_report(data, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        ts = int(time.time())
        basename = f"hvac_report_{ts}.xlsx"
        path = os.path.join(output_dir, basename)
        with open(path, "wb") as f:
            f.write(b"Dummy Excel")
        return basename

    def create_pdf_report(data, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        ts = int(time.time())
        basename = f"hvac_report_{ts}.pdf"
        path = os.path.join(output_dir, basename)
        with open(path, "wb") as f:
            f.write(b"Dummy PDF")
        return basename

BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BLUEPRINT_DIR)

# sensible defaults; prefer app config at runtime via get_paths()
DEFAULT_GENERATED_DIR = os.path.join(BASE_DIR, 'generated')
DEFAULT_UPLOADS_DIR = os.path.join(DEFAULT_GENERATED_DIR, 'uploads')
DEFAULT_JOBS_DIR = os.path.join(DEFAULT_GENERATED_DIR, 'jobs')

# fallback executor for background tasks (used if app doesn't provide one)
from concurrent.futures import ThreadPoolExecutor
_FALLBACK_EXECUTOR = ThreadPoolExecutor(max_workers=2)

hvac_mep_bp = Blueprint('hvac_mep_bp', __name__, template_folder='templates', static_folder='static')

def get_paths():
    """
    Return (GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR) using current_app config or defaults.
    Safe to call during request handling.
    """
    gen = current_app.config.get('GENERATED_DIR', DEFAULT_GENERATED_DIR) if current_app else DEFAULT_GENERATED_DIR
    uploads = current_app.config.get('UPLOADS_DIR', DEFAULT_UPLOADS_DIR) if current_app else DEFAULT_UPLOADS_DIR
    jobs = current_app.config.get('JOBS_DIR', DEFAULT_JOBS_DIR) if current_app else DEFAULT_JOBS_DIR
    executor = current_app.config.get('EXECUTOR') if (current_app and current_app.config.get('EXECUTOR')) else _FALLBACK_EXECUTOR
    return gen, uploads, jobs, executor

@hvac_mep_bp.route('/form', methods=['GET'])
def index():
    return render_template('hvac_mep_form.html')

@hvac_mep_bp.route('/dropdowns', methods=['GET'])
def dropdowns():
    local = os.path.join(BLUEPRINT_DIR, 'dropdown_data.json')
    if os.path.exists(local):
        with open(local, 'r') as f:
            return jsonify(json.load(f))
    # fallback: empty object
    return jsonify({})

@hvac_mep_bp.route('/save-draft', methods=['POST'])
def save_draft():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    payload = request.get_json(force=True)
    draft_id = random_id("draft")
    drafts_dir = os.path.join(GENERATED_DIR, "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    with open(os.path.join(drafts_dir, f"{draft_id}.json"), 'w', encoding='utf-8') as f:
        json.dump(payload, f)
    return jsonify({"status": "ok", "draft_id": draft_id})

@hvac_mep_bp.route('/submit', methods=['POST'])
def submit():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    # collect non-file form fields
    fields = {}
    for key in request.form:
        fields[key] = request.form.get(key)

    # Save uploaded files into UPLOADS_DIR
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    saved_files = []
    for key in request.files:
        f = request.files.get(key)
        if f and f.filename:
            saved_name = save_uploaded_file(f, UPLOADS_DIR)
            saved_files.append({
                "field": key,
                "saved": saved_name,
                "path": os.path.join(UPLOADS_DIR, saved_name),
                "url": url_for('hvac_mep_bp.download_generated', filename=f"uploads/{saved_name}", _external=True)
            })

    # Capture signatures from hidden form fields (client should put data URLs into these)
    tech_sig = request.form.get('tech_signature') or request.form.get('tech_signature_data') or ''
    opman_sig = request.form.get('opMan_signature') or request.form.get('opManSignatureData') or ''

    # Persist raw submission
    sub_id = random_id("sub")
    subs_dir = os.path.join(GENERATED_DIR, "submissions")
    os.makedirs(subs_dir, exist_ok=True)
    submission_path = os.path.join(subs_dir, f"{sub_id}.json")
    with open(submission_path, 'w', encoding='utf-8') as f:
        json.dump({"id": sub_id, "fields": fields, "files": saved_files, "tech_signature": bool(tech_sig), "opman_signature": bool(opman_sig)}, f)

    # Create job
    os.makedirs(JOBS_DIR, exist_ok=True)
    job_id = random_id("job")
    meta = {"submission_id": sub_id, "module": "hvac_mep", "created_at": datetime.utcnow().isoformat()}
    mark_job_started(JOBS_DIR, job_id, meta=meta)

    # Background task: generate files and mark job progress/done
    def task_generate_reports(job_id_local, submission_path_local):
        try:
            update_job_progress(JOBS_DIR, job_id_local, 10)
            # load submission data
            data = {}
            try:
                if submission_path_local and os.path.exists(submission_path_local):
                    with open(submission_path_local, 'r', encoding='utf-8') as sf:
                        data = json.load(sf)
            except Exception:
                data = {}

            # generate excel
            excel_name = create_excel_report(data, output_dir=GENERATED_DIR)
            update_job_progress(JOBS_DIR, job_id_local, 60)

            # generate pdf
            pdf_name = create_pdf_report(data, output_dir=GENERATED_DIR)
            update_job_progress(JOBS_DIR, job_id_local, 95)

            results = []
            if excel_name:
                results.append({"filename": excel_name, "url": url_for('hvac_mep_bp.download_generated', filename=excel_name, _external=True)})
            if pdf_name:
                results.append({"filename": pdf_name, "url": url_for('hvac_mep_bp.download_generated', filename=pdf_name, _external=True)})

            mark_job_done(JOBS_DIR, job_id_local, results)
        except Exception as exc:
            traceback.print_exc()
            update_job_progress(JOBS_DIR, job_id_local, 0, state='failed', results=[{"error": str(exc)}])

    # submit to executor (may be fallback ThreadPoolExecutor)
    try:
        EXECUTOR.submit(task_generate_reports, job_id, submission_path)
    except Exception:
        # last resort: run in background thread
        import threading
        t = threading.Thread(target=task_generate_reports, args=(job_id, submission_path), daemon=True)
        t.start()

    return jsonify({"status": "queued", "job_id": job_id, "submission_id": sub_id, "files": saved_files})

@hvac_mep_bp.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    # read job state file produced by common.utils functions
    state = read_job_state(JOBS_DIR, job_id)
    if not state:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(state)

@hvac_mep_bp.route('/generated/<path:filename>', methods=['GET'])
def download_generated(filename):
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    # allow nested paths like uploads/<name>
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)