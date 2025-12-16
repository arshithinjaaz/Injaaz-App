import os
import json
from flask import Blueprint, current_app, render_template, request, jsonify, url_for
from common.utils import random_id, save_uploaded_file, mark_job_started, update_job_progress, mark_job_done

# Try to import your real generators (if you copied them into this module)
try:
    from .hvac_generators import create_excel_report, create_pdf_report
except Exception:
    # If import fails, we'll fallback to placeholders below (the hvac_generators.py file included provides placeholders).
    def create_excel_report(data, output_dir):
        basename = f"hvac_report_{random_id('')}.xlsx"
        path = os.path.join(output_dir, basename)
        with open(path, "wb") as f:
            f.write(b"Dummy HVAC EXCEL")
        return basename

    def create_pdf_report(data, output_dir):
        basename = f"hvac_report_{random_id('')}.pdf"
        path = os.path.join(output_dir, basename)
        with open(path, "wb") as f:
            f.write(b"Dummy HVAC PDF")
        return basename

BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FOLDER = os.path.join(BLUEPRINT_DIR, 'templates')

hvac_mep_bp = Blueprint('hvac_mep_bp', __name__, template_folder=TEMPLATE_FOLDER, static_folder='static')

def app_paths():
    app = current_app
    return app.config['GENERATED_DIR'], app.config['UPLOADS_DIR'], app.config['JOBS_DIR'], app.config['EXECUTOR']

@hvac_mep_bp.route('/form', methods=['GET'])
def index():
    return render_template('hvac_mep_form.html')

@hvac_mep_bp.route('/dropdowns', methods=['GET'])
def dropdowns():
    local = os.path.join(BLUEPRINT_DIR, 'dropdown_data.json')
    if os.path.exists(local):
        with open(local, 'r') as f:
            return jsonify(json.load(f))
    central = os.path.join(current_app.config.get('BASE_DIR', ''), 'data', 'dropdown_data.json')
    if os.path.exists(central):
        with open(central, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({})

@hvac_mep_bp.route('/save-draft', methods=['POST'])
def save_draft():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    payload = request.get_json(force=True)
    draft_id = random_id("draft")
    drafts_dir = os.path.join(GENERATED_DIR, "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    with open(os.path.join(drafts_dir, f"{draft_id}.json"), 'w') as f:
        json.dump(payload, f)
    return jsonify({"status": "ok", "draft_id": draft_id})

@hvac_mep_bp.route('/submit', methods=['POST'])
def submit():
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    # Collect form fields
    fields = dict(request.form)
    # Save uploads
    saved_files = []
    for key in request.files:
        f = request.files.get(key)
        if f and f.filename:
            saved = save_uploaded_file(f, UPLOADS_DIR)
            saved_files.append({
                "field": key,
                "saved": saved,
                "url": url_for('download_generated', filename=f"uploads/{saved}", _external=True)
            })
    # Persist raw submission
    sub_id = random_id("sub")
    subs_dir = os.path.join(GENERATED_DIR, "submissions")
    os.makedirs(subs_dir, exist_ok=True)
    submission_path = os.path.join(subs_dir, f"{sub_id}.json")
    with open(submission_path, 'w') as f:
        json.dump({"id": sub_id, "fields": fields, "files": saved_files}, f)

    # Create job
    job_id = random_id("job")
    meta = {"submission_id": sub_id, "module": "hvac_mep"}
    mark_job_started(JOBS_DIR, job_id, meta=meta)

    # Background task
    def task_generate_reports(job_id_local, submission_path_local):
        try:
            update_job_progress(JOBS_DIR, job_id_local, 10)
            # Load submission data if present
            data = {}
            try:
                if submission_path_local and os.path.exists(submission_path_local):
                    with open(submission_path_local, 'r') as sf:
                        data = json.load(sf)
            except Exception:
                data = {}

            # Call real generators (create_excel_report/create_pdf_report) — they should write to GENERATED_DIR and return basenames
            excel_name = create_excel_report(data, output_dir=GENERATED_DIR)
            update_job_progress(JOBS_DIR, job_id_local, 60)
            pdf_name = create_pdf_report(data, output_dir=GENERATED_DIR)

            results = []
            if excel_name:
                results.append({"filename": excel_name, "url": url_for('download_generated', filename=excel_name, _external=True)})
            if pdf_name:
                results.append({"filename": pdf_name, "url": url_for('download_generated', filename=pdf_name, _external=True)})

            mark_job_done(JOBS_DIR, job_id_local, results)
        except Exception as e:
            update_job_progress(JOBS_DIR, job_id_local, 0, state='failed', results=[{"error": str(e)}])

    EXECUTOR.submit(task_generate_reports, job_id, submission_path)
    return jsonify({"status": "queued", "job_id": job_id, "submission_id": sub_id, "files": saved_files})

@hvac_mep_bp.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = app_paths()
    job_state_file = os.path.join(JOBS_DIR, f"{job_id}.json")
    if not os.path.exists(job_state_file):
        return jsonify({"error": "unknown job"}), 404
    with open(job_state_file, 'r') as f:
        return jsonify(json.load(f))