# module_hvac_mep/routes.py
import os
import json
import time
import base64
import re
import traceback
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, jsonify, url_for, send_from_directory

# common utilities (ensure common/utils.py exists)
from common.utils import (
    random_id,
    save_uploaded_file,
    mark_job_started,
    update_job_progress,
    mark_job_done,
    read_job_state,
)

# try to import generators (placeholders available in hvac_generators.py)
try:
    from .hvac_generators import create_excel_report, create_pdf_report
except Exception:
    # fallback placeholders
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

# import the external generator worker you added
try:
    from . import generator as hvac_generator
except Exception:
    hvac_generator = None  # we'll still allow fallback behavior if needed

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
    Decode a data URL (data:image/png;base64,...) and save as PNG under uploads_dir.
    Returns (saved_filename, public_url) or (None, None) on failure.
    Note: this function uses url_for(), so must be called inside an app/request context.
    """
    if not dataurl:
        return None, None
    m = _DATAURL_RE.match(dataurl)
    if not m:
        return None, None
    mime = m.group("mime")
    b64 = m.group("data")
    ext = "png"
    if mime and "/" in mime:
        ext = mime.split("/")[-1]
    try:
        os.makedirs(uploads_dir, exist_ok=True)
        raw = base64.b64decode(b64)
        fname = f"{prefix}_{int(time.time())}_{random_id()}.{ext}"
        path = os.path.join(uploads_dir, fname)
        with open(path, "wb") as fh:
            fh.write(raw)
        # return filename and external URL via download_generated
        url = url_for("hvac_mep_bp.download_generated", filename=f"uploads/{fname}", _external=True)
        return fname, url
    except Exception:
        traceback.print_exc()
        return None, None


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

        # Signatures (data URLs). We'll persist them to files.
        tech_sig_dataurl = request.form.get("tech_signature") or request.form.get("tech_signature_data") or ""
        opman_sig_dataurl = request.form.get("opMan_signature") or request.form.get("opManSignatureData") or ""

        tech_sig_file = None
        opman_sig_file = None
        if tech_sig_dataurl:
            # save_signature_dataurl uses url_for -> safe here (we are in request/app context)
            fname, url = save_signature_dataurl(tech_sig_dataurl, UPLOADS_DIR, prefix="tech_sig")
            if fname:
                tech_sig_file = {"saved": fname, "url": url}
        if opman_sig_dataurl:
            fname, url = save_signature_dataurl(opman_sig_dataurl, UPLOADS_DIR, prefix="opman_sig")
            if fname:
                opman_sig_file = {"saved": fname, "url": url}

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
                        saved_name = save_uploaded_file(f, UPLOADS_DIR)
                        photos_saved.append(
                            {
                                "field": file_field,
                                "saved": saved_name,
                                "path": os.path.join(UPLOADS_DIR, saved_name),
                                "url": url_for("hvac_mep_bp.download_generated", filename=f"uploads/{saved_name}", _external=True),
                            }
                        )

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
                    saved_name = save_uploaded_file(f, UPLOADS_DIR)
                    saved_files.append(
                        {
                            "field": key,
                            "saved": saved_name,
                            "path": os.path.join(UPLOADS_DIR, saved_name),
                            "url": url_for("hvac_mep_bp.download_generated", filename=f"uploads/{saved_name}", _external=True),
                        }
                    )

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

        # Persist submission JSON (include base_url so background worker can build absolute links)
        sub_id = random_id("sub")
        subs_dir = os.path.join(GENERATED_DIR, "submissions")
        os.makedirs(subs_dir, exist_ok=True)
        submission_path = os.path.join(subs_dir, f"{sub_id}.json")

        submission_record = {
            "id": sub_id,
            "site_name": site_name,
            "visit_date": visit_date,
            "tech_signature": tech_sig_file,
            "opman_signature": opman_sig_file,
            "items": items,
            "base_url": request.host_url.rstrip('/'),   # <- record request origin here
            "created_at": datetime.utcnow().isoformat(),
        }

        with open(submission_path, "w", encoding="utf-8") as sf:
            json.dump(submission_record, sf, indent=2)

        # Create job record and enqueue background task
        os.makedirs(JOBS_DIR, exist_ok=True)
        job_id = random_id("job")
        mark_job_started(JOBS_DIR, job_id, meta={"submission_id": sub_id, "module": "hvac_mep", "created_at": datetime.utcnow().isoformat()})

        # Capture the Flask app object so background worker can push an app context when needed
        app_obj = current_app._get_current_object()

        # If the modular generator is available, delegate the heavy lifting to it.
        if hvac_generator and hasattr(hvac_generator, 'process_submission'):
            try:
                EXECUTOR.submit(hvac_generator.process_submission, job_id, submission_path, app_obj)
            except Exception:
                import threading
                t = threading.Thread(target=hvac_generator.process_submission, args=(job_id, submission_path, app_obj), daemon=True)
                t.start()
        else:
            # Fallback: use the simple inline generation (uses hvac_generators functions)
            def task_generate_reports(job_id_local, submission_path_local, app_obj_local):
                try:
                    # run inside app context so url_for works
                    with app_obj_local.app_context():
                        update_job_progress(JOBS_DIR, job_id_local, 10)
                        data = {}
                        try:
                            if submission_path_local and os.path.exists(submission_path_local):
                                with open(submission_path_local, "r", encoding="utf-8") as sf:
                                    data = json.load(sf)
                        except Exception:
                            data = {}

                        excel_name = create_excel_report(data, output_dir=GENERATED_DIR)
                        update_job_progress(JOBS_DIR, job_id_local, 60)
                        pdf_name = create_pdf_report(data, output_dir=GENERATED_DIR)
                        update_job_progress(JOBS_DIR, job_id_local, 95)

                        # Build result URLs using stored base_url to avoid needing SERVER_NAME config
                        results = []
                        base = data.get("base_url") if isinstance(data, dict) else None
                        if excel_name:
                            rel = url_for("hvac_mep_bp.download_generated", filename=excel_name, _external=False)
                            results.append({"filename": excel_name, "url": f"{base}{rel}" if base else rel})
                        if pdf_name:
                            rel = url_for("hvac_mep_bp.download_generated", filename=pdf_name, _external=False)
                            results.append({"filename": pdf_name, "url": f"{base}{rel}" if base else rel})

                        mark_job_done(JOBS_DIR, job_id_local, results)
                except Exception as exc:
                    traceback.print_exc()
                    update_job_progress(JOBS_DIR, job_id_local, 0, state="failed", results=[{"error": str(exc)}])

            try:
                EXECUTOR.submit(task_generate_reports, job_id, submission_path, app_obj)
            except Exception:
                import threading
                t = threading.Thread(target=task_generate_reports, args=(job_id, submission_path, app_obj), daemon=True)
                t.start()

        return jsonify({"status": "queued", "job_id": job_id, "submission_id": sub_id, "items": len(items)})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@hvac_mep_bp.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    state = read_job_state(JOBS_DIR, job_id)
    if not state:
        return jsonify({"error": "unknown job"}), 404
    return jsonify(state)


@hvac_mep_bp.route("/generated/<path:filename>", methods=["GET"])
def download_generated(filename):
    GENERATED_DIR, UPLOADS_DIR, JOBS_DIR, EXECUTOR = get_paths()
    # allow nested paths like uploads/<name>
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)