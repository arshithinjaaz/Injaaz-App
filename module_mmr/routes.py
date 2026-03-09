"""
MMR Blueprint – admin-only routes for Report Generation.
URL prefix: /admin/mmr
"""
import os
import json
import logging
from datetime import datetime, timedelta
from io import BytesIO

from flask import (Blueprint, request, jsonify, render_template,
                   current_app, send_file)
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.middleware import admin_required

logger = logging.getLogger(__name__)

mmr_bp = Blueprint('mmr_bp', __name__, url_prefix='/admin/mmr',
                   template_folder='templates')

ALLOWED_DOMAIN = 'injaaz.ae'


def _validate_injaaz_emails(raw: str) -> tuple[list[str], str | None]:
    """
    Parse a comma-separated list of emails and enforce @injaaz.ae domain.

    Returns:
        (valid_list, error_message)  – error_message is None when all pass.
    """
    if not raw or not raw.strip():
        return [], None
    emails = [e.strip() for e in raw.split(',') if e.strip()]
    bad = [e for e in emails if not e.lower().endswith(f'@{ALLOWED_DOMAIN}')]
    if bad:
        quoted = ', '.join(bad)
        return [], (
            f"Only @{ALLOWED_DOMAIN} addresses are allowed. "
            f"Invalid: {quoted}"
        )
    return emails, None

_CONFIG_FILE    = 'mmr_email_config.json'
_UPLOAD_FILE    = 'mmr_latest.xlsx'
_CYCLE_LOG_FILE = 'mmr_cycle_log.json'

_DEFAULT_CONFIG = {
    'to': 'dennis@injaaz.ae, shakeel@injaaz.ae, araki@injaaz.ae, abbas@injaaz.ae, a.mohammed@injaaz.ae',
    'cc': 'taha@injaaz.ae, george@injaaz.ae, arshith@injaaz.ae, eslam@injaaz.ae, alaa@injaaz.ae, mona@injaaz.ae, siraj@injaaz.ae, jismon@injaaz.ae, ousman@injaaz.ae',
    'subject': 'Daily Report on Resolved and Pending Complaints for {{REPORT_DATE}}',
    'body': (
        'Dear FM Team,\n\n'
        'Please find below comprehensive Daily Report of ({{REPORT_DATE}}) '
        'generated from our CAFM system / Injaaz Application for all Pending & Resolved work orders.\n\n'
        'Regards,\n'
        'CAFM Team'
    ),
    'schedule_enabled': False,
    'schedule_hour': 10,
    'schedule_minute': 0,
    'schedule_paused': False,
}

_REPORT_DATE_PLACEHOLDER = '{{REPORT_DATE}}'


def _format_report_date(dt: datetime) -> str:
    """Format as '28th of February 2026' (previous day's date for report)."""
    d = dt.day
    suffix = 'th' if 11 <= d <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')
    return f"{d}{suffix} of {dt.strftime('%B %Y')}"


def _report_filename() -> str:
    """Excel filename: 'Daily Report on Resolved and Pending Complaints for 28th of February 2026.xlsx'"""
    yesterday = datetime.now() - timedelta(days=1)
    date_str = _format_report_date(yesterday)
    return f"Daily Report on Resolved and Pending Complaints for {date_str}.xlsx"


# ──────────────────────────────────────────────────────────────────────────────
# Config helpers (stored in GENERATED_DIR as a JSON file)
# ──────────────────────────────────────────────────────────────────────────────

def _config_path():
    return os.path.join(current_app.config['GENERATED_DIR'], _CONFIG_FILE)

def _upload_path():
    return os.path.join(current_app.config['GENERATED_DIR'], _UPLOAD_FILE)


def _reports_folder():
    """Folder for saved reports (sent via email or Save to Folder)."""
    folder = os.path.join(current_app.config['GENERATED_DIR'], 'mmr_reports')
    os.makedirs(folder, exist_ok=True)
    return folder


# TrueNAS / network drive path for Save to Drive (set TRUENAS_CAFM_PATH in .env to override)
_TRUENAS_CAFM_PATH = os.environ.get('TRUENAS_CAFM_PATH') or r'\\172.25.70.137\Injaaz\CAFM\Daily Generated Report'


def _save_report_to_folder(report_bytes: bytes, base_filename: str, suffix: str = '',
                          filters: dict | None = None) -> str | None:
    """Save report to folder with timestamp. Optionally save filter state to restore dashboard.
    Returns saved filename or None."""
    try:
        folder = _reports_folder()
        now = datetime.now()
        ts = now.strftime('%Y-%m-%d_%H-%M-%S')
        name = base_filename.replace('.xlsx', '') + (f'_{suffix}' if suffix else '') + f'_{ts}.xlsx'
        path = os.path.join(folder, name)
        with open(path, 'wb') as f:
            f.write(report_bytes)
        # Save filter state for restoring dashboard when opening report
        if filters is not None:
            filters_path = path.replace('.xlsx', '_filters.json')
            with open(filters_path, 'w') as f:
                json.dump(filters, f, indent=2)
        return name
    except Exception as e:
        logger.warning(f'MMR save to folder failed: {e}')
        return None


def _save_report_to_drive(report_bytes: bytes, filename: str, save_path: str | None = None) -> tuple[str | None, str | None, bool]:
    """Save report to given path or default TrueNAS path. Returns (full_path, None) on success or (None, error_message) on failure."""
    base = (save_path or '').strip() or _TRUENAS_CAFM_PATH
    # Normalize path for Windows UNC (avoid double backslashes)
    base = os.path.normpath(base)
    try:
        # Create target directory if it doesn't exist
        if not os.path.exists(base):
            try:
                os.makedirs(base, exist_ok=True)
            except OSError as e:
                return None, f'Cannot create folder {base}. {e}'
        path = os.path.join(base, filename)
        with open(path, 'wb') as f:
            f.write(report_bytes)
        return path, None, False
    except PermissionError as e:
        logger.warning(f'MMR save to drive permission error: {e}')
        return None, 'Permission denied. Check TrueNAS share permissions.', False
    except OSError as e:
        logger.warning(f'MMR save to drive failed: {e}')
        err = str(e)
        # Fallback: save to local report folder if network drive fails
        try:
            local_name = _save_report_to_folder(report_bytes, filename, 'drive_fallback')
            if local_name:
                local_path = os.path.join(_reports_folder(), local_name)
                return local_path, None, True  # Success, saved locally
        except Exception:
            pass
        if 'cannot find' in err.lower() or 'no such file' in err.lower() or 'network' in err.lower():
            return None, f'Cannot reach TrueNAS. Ensure {base} is accessible. ({err})', False
        return None, err, False
    except Exception as e:
        logger.warning(f'MMR save to drive failed: {e}')
        # Fallback to local
        try:
            local_name = _save_report_to_folder(report_bytes, filename, 'drive_fallback')
            if local_name:
                return os.path.join(_reports_folder(), local_name), None, True
        except Exception:
            pass
        return None, str(e), False

def _load_config() -> dict:
    try:
        p = _config_path()
        if os.path.exists(p):
            with open(p) as f:
                return {**_DEFAULT_CONFIG, **json.load(f)}
    except Exception:
        pass
    return dict(_DEFAULT_CONFIG)

def _save_config(config: dict):
    with open(_config_path(), 'w') as f:
        json.dump(config, f, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
# Cycle log helpers  (stored as mmr_cycle_log.json next to the config)
# ──────────────────────────────────────────────────────────────────────────────

def _cycle_log_path():
    return os.path.join(current_app.config['GENERATED_DIR'], _CYCLE_LOG_FILE)


def _get_caller_identity() -> str:
    """Safely extract a username string from the current JWT identity."""
    try:
        identity = get_jwt_identity()
        if isinstance(identity, str):
            return identity
        if isinstance(identity, dict):
            return identity.get('username') or identity.get('sub') or 'admin'
        return str(identity) or 'admin'
    except Exception:
        return 'admin'


def _load_cycle_log() -> dict:
    try:
        p = _cycle_log_path()
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    except Exception:
        pass
    return {'current': None, 'history': [], 'next_cycle_id': 1}


def _save_cycle_log(log: dict):
    try:
        with open(_cycle_log_path(), 'w') as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        logger.warning(f'MMR cycle log save failed: {e}')


def _start_new_cycle(uploaded_by: str = 'admin') -> dict:
    """Begin a fresh dispatch cycle. Pushes any existing current cycle to history."""
    log = _load_cycle_log()
    current = log.get('current')
    if current and current.get('upload_at'):
        history = log.get('history', [])
        history.insert(0, current)
        log['history'] = history[:50]
    cycle_id = int(log.get('next_cycle_id', 1))
    log['next_cycle_id'] = cycle_id + 1
    log['current'] = {
        'cycle_id': cycle_id,
        'upload_at': datetime.now().isoformat(),
        'upload_by': uploaded_by,
        'approved_at': None,
        'approved_by': None,
        'sent_at': None,
        'sent_by': None,
        'recipient_count': 0,
        'subject': '',
        'report_filename': '',
        'status': 'uploaded',
    }
    _save_cycle_log(log)
    return log['current']


def _approve_current_cycle(approved_by: str = 'admin') -> bool:
    """Mark current cycle as reviewed. Returns False if nothing to approve."""
    log = _load_cycle_log()
    current = log.get('current')
    if not current or current.get('status') != 'uploaded':
        return False
    current['approved_at'] = datetime.now().isoformat()
    current['approved_by'] = approved_by
    current['status'] = 'approved'
    log['current'] = current
    _save_cycle_log(log)
    return True


def _complete_current_cycle(sent_by: str, subject: str,
                             recipient_count: int, report_filename: str):
    """Record a successful email send against the current cycle."""
    try:
        log = _load_cycle_log()
        current = log.get('current')
        if not current:
            cycle_id = int(log.get('next_cycle_id', 1))
            log['next_cycle_id'] = cycle_id + 1
            current = {
                'cycle_id': cycle_id,
                'upload_at': datetime.now().isoformat(),
                'upload_by': 'system',
                'approved_at': None,
                'approved_by': None,
                'status': 'uploaded',
            }
        current['sent_at'] = datetime.now().isoformat()
        current['sent_by'] = sent_by
        current['recipient_count'] = recipient_count
        current['subject'] = subject
        current['report_filename'] = report_filename
        current['status'] = 'sent'
        log['current'] = current
        _save_cycle_log(log)
    except Exception as e:
        logger.warning(f'MMR complete cycle failed: {e}')


def _save_last_run(status: str, to_list: list, cc_list: list | None, subject: str, recipient_count: int):
    """Persist last automation run for status display. Called from scheduler."""
    config = _load_config()
    config['last_run_at'] = datetime.now().isoformat()
    config['last_run_status'] = status
    config['last_run_to'] = ', '.join(to_list) if to_list else ''
    config['last_run_cc'] = ', '.join(cc_list) if cc_list else ''
    config['last_run_subject'] = subject or ''
    config['last_run_recipient_count'] = recipient_count
    if status == 'success':
        config['schedule_paused'] = True
    _save_config(config)


# ──────────────────────────────────────────────────────────────────────────────
# Page render
# ──────────────────────────────────────────────────────────────────────────────

@mmr_bp.route('/', methods=['GET'])
@jwt_required()
@admin_required
def dashboard():
    return render_template('mmr_dashboard.html')


# ──────────────────────────────────────────────────────────────────────────────
# Upload
# ──────────────────────────────────────────────────────────────────────────────

@mmr_bp.route('/api/upload', methods=['POST'])
@jwt_required()
@admin_required
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Invalid file format – upload .xlsx or .xls'}), 400

    dest = _upload_path()
    file.save(dest)

    try:
        from .mmr_service import parse_excel, compute_dashboard, df_to_rows, _resolve_chargeable
        df = parse_excel(dest)
        dashboard_data = compute_dashboard(df)
        rows = df_to_rows(df)
        for r in rows:
            r['Space'] = _resolve_chargeable(
                r.get('Space', ''), r.get('BaseUnit', ''), r.get('Client', ''),
                r.get('Service Group', ''), r.get('Contract', '')
            )
        # Start a new dispatch cycle for this upload
        try:
            _start_new_cycle(_get_caller_identity())
        except Exception:
            pass

        # Auto-resume automation when new file uploaded (each run needs fresh Excel)
        config = _load_config()
        if config.get('schedule_enabled') and config.get('schedule_paused'):
            config['schedule_paused'] = False
            _save_config(config)
            try:
                from .scheduler import update_schedule
                update_schedule(config, current_app._get_current_object())
            except Exception:
                pass
        return jsonify({'success': True, 'dashboard': dashboard_data, 'rows': rows,
                        'total': len(rows)})
    except Exception as e:
        logger.error(f'MMR upload parse error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Download report
# ──────────────────────────────────────────────────────────────────────────────

@mmr_bp.route('/api/download-report', methods=['GET'])
@jwt_required()
@admin_required
def download_report():
    path = _upload_path()
    if not os.path.exists(path):
        return jsonify({'error': 'No file uploaded yet. Please upload an Excel file first.'}), 404

    try:
        from .mmr_service import parse_excel, generate_report_excel
        df = parse_excel(path)
        report_bytes = generate_report_excel(df)
        filename = _report_filename()
        return send_file(
            BytesIO(report_bytes),
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f'MMR report generation error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Save to folder & Report folder
# ──────────────────────────────────────────────────────────────────────────────

@mmr_bp.route('/api/save-to-folder', methods=['POST'])
@jwt_required()
@admin_required
def save_to_folder():
    """Save current (optionally filtered) report to the report folder."""
    path = _upload_path()
    if not os.path.exists(path):
        return jsonify({'error': 'No file uploaded yet. Please upload an Excel file first.'}), 400

    data = request.get_json() or {}
    rows = data.get('rows')
    filters = data.get('filters')  # { client, contract, serviceGroup, space, status, priority }

    try:
        from .mmr_service import parse_excel, generate_report_excel, rows_to_df
        if rows:
            df = rows_to_df(rows)
            if df.empty:
                return jsonify({'error': 'No rows to save. Apply filters or upload data.'}), 400
        else:
            df = parse_excel(path)
        report_bytes = generate_report_excel(df)
        filename = _report_filename()
        saved = _save_report_to_folder(report_bytes, filename, 'saved', filters=filters)
        if saved:
            return jsonify({'success': True, 'filename': saved})
        return jsonify({'error': 'Failed to save to folder'}), 500
    except Exception as e:
        logger.error(f'MMR save to folder error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@mmr_bp.route('/api/save-to-drive', methods=['POST'])
@jwt_required()
@admin_required
def save_to_drive():
    """Save current (optionally filtered) report to TrueNAS CAFM drive (\\\\172.25.70.137\\Injaaz\\CAFM)."""
    path = _upload_path()
    if not os.path.exists(path):
        return jsonify({'error': 'No file uploaded yet. Please upload an Excel file first.'}), 400

    data = request.get_json() or {}
    rows = data.get('rows')
    filters = data.get('filters')
    save_path = data.get('save_path')

    try:
        from .mmr_service import parse_excel, generate_report_excel, rows_to_df
        if rows:
            df = rows_to_df(rows)
            if df.empty:
                return jsonify({'error': 'No rows to save. Apply filters or upload data.'}), 400
        else:
            df = parse_excel(path)
        report_bytes = generate_report_excel(df)
        base_name = _report_filename().replace('.xlsx', '')
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'{base_name}_{ts}.xlsx'
        saved_path, err, saved_locally = _save_report_to_drive(report_bytes, filename, save_path=save_path)
        if saved_path:
            return jsonify({
                'success': True, 'path': saved_path, 'filename': filename,
                'saved_locally': saved_locally
            })
        msg = err or 'Failed to save to drive. Check network access to TrueNAS.'
        return jsonify({'error': msg}), 500
    except Exception as e:
        logger.error(f'MMR save to drive error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@mmr_bp.route('/api/report-folder', methods=['GET'])
@jwt_required()
@admin_required
def list_report_folder():
    """List all saved reports in the report folder. Includes filter state for restoring dashboard."""
    folder = _reports_folder()
    files = []
    for name in sorted(os.listdir(folder), reverse=True):
        if name.lower().endswith('.xlsx'):
            path = os.path.join(folder, name)
            try:
                stat = os.stat(path)
                entry = {
                    'name': name,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
                # Load saved filter state if present
                filters_path = path.replace('.xlsx', '_filters.json')
                if os.path.exists(filters_path):
                    try:
                        with open(filters_path) as f:
                            entry['filters'] = json.load(f)
                    except Exception:
                        entry['filters'] = {}
                else:
                    entry['filters'] = {}
                files.append(entry)
            except OSError:
                pass
    return jsonify({'files': files})


@mmr_bp.route('/api/report-folder/download/<path:filename>', methods=['GET'])
@jwt_required()
@admin_required
def download_report_folder_file(filename):
    """Download a saved report from the report folder."""
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    folder = _reports_folder()
    path = os.path.join(folder, filename)
    if not os.path.exists(path) or not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(
        path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@mmr_bp.route('/api/report-folder/open/<path:filename>', methods=['GET'])
@jwt_required()
@admin_required
def open_report_from_folder(filename):
    """Load a saved report's data for display in the dashboard."""
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    folder = _reports_folder()
    path = os.path.join(folder, filename)
    if not os.path.exists(path) or not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404

    try:
        from .mmr_service import parse_saved_report_excel, compute_dashboard, df_to_rows, _resolve_chargeable
        df = parse_saved_report_excel(path)
        if df.empty:
            return jsonify({'error': 'Could not parse report. The file may be in a different format.'}), 400
        dashboard_data = compute_dashboard(df)
        rows = df_to_rows(df)
        for r in rows:
            r['Space'] = _resolve_chargeable(
                r.get('Space', ''), r.get('BaseUnit', ''), r.get('Client', ''),
                r.get('Service Group', ''), r.get('Contract', '')
            )
        return jsonify({
            'success': True,
            'dashboard': dashboard_data,
            'rows': rows,
            'total': len(rows),
        })
    except Exception as e:
        logger.error(f'MMR open report error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Email config
# ──────────────────────────────────────────────────────────────────────────────

@mmr_bp.route('/api/email-config', methods=['GET'])
@jwt_required()
@admin_required
def get_email_config():
    return jsonify(_load_config())


@mmr_bp.route('/api/automation-status', methods=['GET'])
@jwt_required()
@admin_required
def get_automation_status():
    """Return schedule state and last run info for the automation button."""
    config = _load_config()
    schedule_enabled = bool(config.get('schedule_enabled'))
    schedule_hour = int(config.get('schedule_hour', 10))
    schedule_minute = int(config.get('schedule_minute', 0))
    schedule_paused = bool(config.get('schedule_paused'))
    excel_uploaded = os.path.exists(_upload_path())

    last_run = None
    if config.get('last_run_at'):
        try:
            at = datetime.fromisoformat(config['last_run_at'])
            today = datetime.now().date()
            last_run = {
                'at': config['last_run_at'],
                'at_formatted': at.strftime('%Y-%m-%d %H:%M'),
                'date': at.date().isoformat(),
                'is_today': at.date() == today,
                'status': config.get('last_run_status', 'unknown'),
                'to': config.get('last_run_to', ''),
                'cc': config.get('last_run_cc', ''),
                'subject': config.get('last_run_subject', ''),
                'recipient_count': int(config.get('last_run_recipient_count', 0)),
            }
        except (ValueError, TypeError):
            pass

    # automation_status: "completed" | "pending" | "paused" | "disabled"
    automation_status = 'disabled'
    if schedule_enabled:
        if schedule_paused:
            automation_status = 'paused'
        elif last_run and last_run['is_today'] and last_run['status'] == 'success':
            automation_status = 'completed'
        else:
            automation_status = 'pending'

    next_run = None
    next_run_tomorrow = False
    if schedule_enabled:
        now = datetime.now()
        next_today = now.replace(hour=schedule_hour, minute=schedule_minute, second=0, microsecond=0)
        if now >= next_today:
            from datetime import timedelta
            next_today += timedelta(days=1)
            next_run_tomorrow = True
        next_run = next_today.strftime('%H:%M')

    excel_required_for_next_run = (
        schedule_enabled and schedule_paused and
        last_run and last_run['is_today'] and last_run['status'] == 'success'
    )

    return jsonify({
        'schedule_enabled': schedule_enabled,
        'schedule_hour': schedule_hour,
        'schedule_minute': schedule_minute,
        'schedule_paused': schedule_paused,
        'next_run_at': next_run,
        'next_run_tomorrow': next_run_tomorrow,
        'excel_uploaded': excel_uploaded,
        'excel_required_for_next_run': excel_required_for_next_run,
        'last_run': last_run,
        'automation_status': automation_status,
    })


@mmr_bp.route('/api/automation-pause', methods=['POST'])
@jwt_required()
@admin_required
def pause_automation():
    """Pause the automation. Next run will not execute until resumed."""
    config = _load_config()
    config['schedule_paused'] = True
    _save_config(config)
    try:
        from .scheduler import update_schedule
        update_schedule(config, current_app._get_current_object())
    except Exception:
        pass
    return jsonify({'success': True, 'paused': True})


@mmr_bp.route('/api/automation-resume', methods=['POST'])
@jwt_required()
@admin_required
def resume_automation():
    """Resume the automation. Requires Excel file to be uploaded."""
    path = _upload_path()
    if not os.path.exists(path):
        return jsonify({'error': 'Upload an Excel file first to resume automation.'}), 400
    config = _load_config()
    config['schedule_paused'] = False
    _save_config(config)
    try:
        from .scheduler import update_schedule
        update_schedule(config, current_app._get_current_object())
    except Exception:
        pass
    return jsonify({'success': True, 'paused': False})


# ──────────────────────────────────────────────────────────────────────────────
# Cycle endpoints
# ──────────────────────────────────────────────────────────────────────────────

@mmr_bp.route('/api/cycles', methods=['GET'])
@jwt_required()
@admin_required
def get_cycles():
    """Return full cycle log (current cycle + history)."""
    return jsonify(_load_cycle_log())


@mmr_bp.route('/api/approve', methods=['POST'])
@jwt_required()
@admin_required
def approve_cycle():
    """Mark the current cycle as reviewed/approved."""
    user = _get_caller_identity()
    if _approve_current_cycle(user):
        return jsonify({'success': True})
    log = _load_cycle_log()
    current = log.get('current')
    if not current:
        return jsonify({'error': 'No active cycle. Upload an Excel file first.'}), 400
    if current.get('status') == 'approved':
        return jsonify({'error': 'Already approved', 'already_approved': True}), 400
    if current.get('status') == 'sent':
        return jsonify({'error': 'Cycle already completed. Upload a new file to start the next cycle.'}), 400
    return jsonify({'error': 'Cannot approve in the current cycle state'}), 400


@mmr_bp.route('/api/email-config', methods=['POST'])
@jwt_required()
@admin_required
def save_email_config():
    data = request.get_json() or {}

    # Domain validation before persisting
    for field in ('to', 'cc'):
        if field in data and data[field]:
            _, err = _validate_injaaz_emails(data[field])
            if err:
                return jsonify({'error': err}), 400

    config = _load_config()
    allowed = ['to', 'cc', 'subject', 'body',
                'schedule_enabled', 'schedule_hour', 'schedule_minute', 'schedule_paused']
    for k in allowed:
        if k in data:
            config[k] = data[k]
    _save_config(config)

    # Refresh scheduler
    try:
        from .scheduler import update_schedule
        update_schedule(config, current_app._get_current_object())
    except Exception as e:
        logger.warning(f'MMR scheduler update skipped: {e}')

    return jsonify({'success': True})


# ──────────────────────────────────────────────────────────────────────────────
# Send email
# ──────────────────────────────────────────────────────────────────────────────

@mmr_bp.route('/api/send-email', methods=['POST'])
@jwt_required()
@admin_required
def send_email_now():
    data = request.get_json() or {}
    path = _upload_path()

    if not os.path.exists(path):
        return jsonify({'error': 'No MMR file uploaded yet. Please upload an Excel file first.'}), 400

    to_raw = data.get('to', '').strip()
    cc_raw = data.get('cc', '').strip()
    subject = data.get('subject', _DEFAULT_CONFIG['subject'])
    body    = data.get('body', '')
    yesterday = datetime.now() - timedelta(days=1)
    report_date = _format_report_date(yesterday)
    subject = subject.replace(_REPORT_DATE_PLACEHOLDER, report_date)
    body = body.replace(_REPORT_DATE_PLACEHOLDER, report_date)

    if not to_raw:
        return jsonify({'error': 'Recipient (To) email is required'}), 400

    to_list, to_err = _validate_injaaz_emails(to_raw)
    if to_err:
        return jsonify({'error': to_err}), 400

    cc_list, cc_err = _validate_injaaz_emails(cc_raw)
    if cc_err:
        return jsonify({'error': cc_err}), 400
    cc_list = cc_list or None

    # Generate report
    try:
        from .mmr_service import parse_excel, generate_report_excel, format_chargeable_summary_for_email, format_per_tower_chargeable_html_for_email
        df = parse_excel(path)
        report_bytes = generate_report_excel(df)
        filename = _report_filename()

        # Intro for HTML (full body before chargeable summary)
        intro_for_html = body.rstrip()

        # Plain text body (fallback)
        chargeable_summary = format_chargeable_summary_for_email(df)
        if chargeable_summary:
            body = (body.rstrip() + '\n\n' + chargeable_summary).rstrip()
        body = (body.rstrip() + '\n\nFor full information, please refer to the attached Excel file.').rstrip()

        # HTML body with per-tower tables (Askaan, Orient, Garden, C1)
        html_tables = format_per_tower_chargeable_html_for_email(df)
        html_body = None
        if html_tables:
            intro_escaped = intro_for_html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
            html_body = f'''<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;font-size:12px;color:#333">
<p style="margin:0 0 12px 0;line-height:1.5">{intro_escaped}</p>
{html_tables}
<p style="margin:12px 0 8px 0;font-size:10px;color:#666;font-style:italic">* This is computer generated, please cross check at least once.</p>
<p style="margin:0">For full information, please refer to the attached Excel file.</p>
</body></html>'''
    except Exception as e:
        return jsonify({'error': f'Report generation failed: {str(e)}'}), 500

    # Guard: ensure SMTP is configured before even trying
    from flask import current_app as _app
    if not _app.config.get('MAIL_SERVER'):
        return jsonify({
            'error': (
                'SMTP is not configured. '
                'Add MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD '
                'and MAIL_DEFAULT_SENDER to your .env file and restart the server.'
            )
        }), 503

    # Send
    try:
        from common.email_service import send_email
        ok = send_email(
            recipient=to_list,
            subject=subject,
            body=body,
            html_body=html_body if html_body else None,
            cc=cc_list,
            attachments=[{
                'content': report_bytes,
                'filename': filename,
                'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }]
        )
        if ok:
            _save_report_to_folder(report_bytes, filename, 'email')
            try:
                rc = len(to_list) + (len(cc_list) if cc_list else 0)
                _complete_current_cycle(_get_caller_identity(), subject, rc, filename)
            except Exception:
                pass
            return jsonify({
                'success': True,
                'message': "Email sent successfully. If you don't see it, check spam/junk and Promotions (Gmail)."
            })
        return jsonify({'error': 'Email was rejected by the mail server. Check credentials and try again.'}), 502
    except Exception as e:
        logger.error(f'MMR send email error: {e}', exc_info=True)
        return jsonify({'error': f'Email error: {str(e)}'}), 502
