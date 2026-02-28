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

_CONFIG_FILE = 'mmr_email_config.json'
_UPLOAD_FILE  = 'mmr_latest.xlsx'

_DEFAULT_CONFIG = {
    'to': '',
    'cc': '',
    'subject': 'MMR Daily Work Order Report',
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
}

_REPORT_DATE_PLACEHOLDER = '{{REPORT_DATE}}'


def _format_report_date(dt: datetime) -> str:
    """Format as '28th of February 2026' (previous day's date for report)."""
    d = dt.day
    suffix = 'th' if 11 <= d <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')
    return f"{d}{suffix} of {dt.strftime('%B %Y')}"


# ──────────────────────────────────────────────────────────────────────────────
# Config helpers (stored in GENERATED_DIR as a JSON file)
# ──────────────────────────────────────────────────────────────────────────────

def _config_path():
    return os.path.join(current_app.config['GENERATED_DIR'], _CONFIG_FILE)

def _upload_path():
    return os.path.join(current_app.config['GENERATED_DIR'], _UPLOAD_FILE)

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
        from .mmr_service import parse_excel, compute_dashboard, df_to_rows
        df = parse_excel(dest)
        dashboard_data = compute_dashboard(df)
        rows = df_to_rows(df)
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
        filename = f"MMR_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
# Email config
# ──────────────────────────────────────────────────────────────────────────────

@mmr_bp.route('/api/email-config', methods=['GET'])
@jwt_required()
@admin_required
def get_email_config():
    return jsonify(_load_config())


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
                'schedule_enabled', 'schedule_hour', 'schedule_minute']
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
    body = body.replace(_REPORT_DATE_PLACEHOLDER, _format_report_date(yesterday))

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
        from .mmr_service import parse_excel, generate_report_excel, format_chargeable_summary_for_email
        df = parse_excel(path)
        report_bytes = generate_report_excel(df)
        filename = f"MMR_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        # Append chargeable summary and attachment note to body
        chargeable_summary = format_chargeable_summary_for_email(df)
        if chargeable_summary:
            body = (body.rstrip() + '\n\n' + chargeable_summary).rstrip()
        body = (body.rstrip() + '\n\nFor full information, please refer to the attached Excel file.').rstrip()
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
            cc=cc_list,
            attachments=[{
                'content': report_bytes,
                'filename': filename,
                'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }]
        )
        if ok:
            return jsonify({
                'success': True,
                'message': 'Email sent successfully. If you don’t see it, check spam/junk and “Promotions” (Gmail).'
            })
        return jsonify({'error': 'Email was rejected by the mail server. Check credentials and try again.'}), 502
    except Exception as e:
        logger.error(f'MMR send email error: {e}', exc_info=True)
        return jsonify({'error': f'Email error: {str(e)}'}), 502
