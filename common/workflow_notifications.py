"""
Workflow email notifications.
"""
from flask import current_app
from app.models import User
from common.email_service import send_email


WORKFLOW_TEAM_DESIGNATIONS = [
    'supervisor',
    'operations_manager',
    'business_development',
    'procurement'
]


def _module_display(module_type):
    return {
        'hvac_mep': 'HVAC & MEP',
        'civil': 'Civil Works',
        'cleaning': 'Cleaning Services'
    }.get(module_type, module_type or 'Form')


def _get_team_recipients():
    users = User.query.filter(
        User.is_active == True,
        User.designation.in_(WORKFLOW_TEAM_DESIGNATIONS)
    ).all()
    return [u.email for u in users if u and u.email]


def send_team_notification(submission, action_user, action_label):
    """
    Notify workflow team members after a signature action.
    """
    try:
        recipients = _get_team_recipients()
        if not recipients:
            return False

        module_name = _module_display(getattr(submission, 'module_type', None))
        site_name = getattr(submission, 'site_name', '') or 'N/A'
        visit_date = getattr(submission, 'visit_date', None)
        visit_display = visit_date.strftime('%Y-%m-%d') if visit_date else 'N/A'
        submission_id = getattr(submission, 'submission_id', '')

        actor_name = getattr(action_user, 'full_name', None) or getattr(action_user, 'username', None) or 'User'
        actor_role = getattr(action_user, 'designation', None) or getattr(action_user, 'role', None) or 'User'

        base_url = (current_app.config.get('APP_BASE_URL') or '').rstrip('/')
        pending_link = f"{base_url}/workflow/pending-reviews" if base_url else "/workflow/pending-reviews"

        subject = f"[Injaaz] {module_name} - {action_label}"
        body = (
            f"{action_label}.\n\n"
            f"Module: {module_name}\n"
            f"Submission ID: {submission_id}\n"
            f"Site/Project: {site_name}\n"
            f"Visit Date: {visit_display}\n"
            f"Signed By: {actor_name} ({actor_role})\n\n"
            f"Review here: {pending_link}\n\n"
            "Injaaz Team"
        )

        html_body = f"""
        <html>
          <body>
            <h2>{action_label}</h2>
            <p><strong>Module:</strong> {module_name}</p>
            <p><strong>Submission ID:</strong> {submission_id}</p>
            <p><strong>Site/Project:</strong> {site_name}</p>
            <p><strong>Visit Date:</strong> {visit_display}</p>
            <p><strong>Signed By:</strong> {actor_name} ({actor_role})</p>
            <p><a href="{pending_link}">Open Pending Reviews</a></p>
            <p>Injaaz Team</p>
          </body>
        </html>
        """

        return send_email(recipients, subject, body, html_body)
    except Exception as e:
        current_app.logger.error(f"Workflow notification error: {str(e)}", exc_info=True)
        return False
