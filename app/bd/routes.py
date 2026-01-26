from flask import Blueprint, jsonify, render_template, request, redirect, url_for, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User
from common.email_service import send_email

bd_bp = Blueprint('bd_bp', __name__, url_prefix='/bd')


def _is_bd_user(user):
    return user and (user.designation == 'business_development')


def _parse_emails(value):
    if not value:
        return []
    if isinstance(value, list):
        return [v.strip() for v in value if v and str(v).strip()]
    raw = str(value)
    parts = [p.strip() for p in raw.replace(';', ',').split(',')]
    return [p for p in parts if p]


def _get_gm_emails():
    gms = User.query.filter(
        User.is_active == True,
        User.designation == 'general_manager'
    ).all()
    return [u.email for u in gms if u and u.email]


@bd_bp.route('/email-module', methods=['GET'])
@jwt_required()
def email_module():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not _is_bd_user(user):
        return redirect('/dashboard')

    gm_emails = _get_gm_emails()
    return render_template('bd_email_module.html', gm_emails=gm_emails)


@bd_bp.route('/email-module/send', methods=['POST'])
@jwt_required()
def send_email_to_gm():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not _is_bd_user(user):
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    payload = request.get_json(silent=True) or request.form.to_dict()
    to_value = payload.get('to') or ''
    cc_value = payload.get('cc') or ''
    subject = (payload.get('subject') or '').strip()
    message = (payload.get('message') or '').strip()

    if not subject:
        return jsonify({'success': False, 'error': 'Subject is required'}), 400
    if not message:
        return jsonify({'success': False, 'error': 'Message is required'}), 400

    recipients = _parse_emails(to_value)
    if not recipients:
        recipients = _get_gm_emails()

    if not recipients:
        return jsonify({'success': False, 'error': 'No General Manager email found'}), 400

    cc_list = _parse_emails(cc_value)

    signature = f"\n\nSent by: {user.full_name or user.username}\nInjaaz Team"
    body = f"{message}{signature}"
    html_body = (
        "<html><body>"
        f"<p>{message.replace(chr(10), '<br>')}</p>"
        f"<p><strong>Sent by:</strong> {user.full_name or user.username}<br>Injaaz Team</p>"
        "</body></html>"
    )

    sent = send_email(recipients, subject, body, html_body=html_body, cc=cc_list or None)

    if sent:
        current_app.logger.info(f"BD email sent by user {user_id} to {recipients}")
        return jsonify({'success': True, 'message': 'Email sent to General Manager'}), 200
    return jsonify({'success': False, 'error': 'Failed to send email'}), 500
