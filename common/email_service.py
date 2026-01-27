"""
Email service for sending emails (password resets, notifications)
"""
import smtplib
import ssl
import logging
import os
import mimetypes
from email.message import EmailMessage
from flask import current_app

logger = logging.getLogger(__name__)


def send_email(recipient, subject, body, html_body=None, cc=None, attachments=None):
    """
    Send email using SMTP configuration from app config
    
    Args:
        recipient: Email address or list of addresses
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
        cc: Optional CC email(s)
        attachments: Optional list of file paths or dicts with bytes
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        app = current_app._get_current_object()
        
        mail_server = app.config.get('MAIL_SERVER')
        mail_port = app.config.get('MAIL_PORT', 587)
        mail_user = app.config.get('MAIL_USERNAME')
        mail_pass = app.config.get('MAIL_PASSWORD')
        mail_use_tls = app.config.get('MAIL_USE_TLS', True)
        mail_sender = app.config.get('MAIL_DEFAULT_SENDER', mail_user or 'noreply@injaaz.com')
        
        if not mail_server or not mail_port:
            logger.warning("Mail server/port not configured; cannot send email")
            return False
        
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = mail_sender
        if isinstance(recipient, (list, tuple)):
            msg['To'] = ', '.join(recipient)
        else:
            msg['To'] = recipient
        
        if cc:
            if isinstance(cc, (list, tuple)):
                msg['Cc'] = ', '.join(cc)
            else:
                msg['Cc'] = cc

        if html_body:
            msg.set_content(body)
            msg.add_alternative(html_body, subtype='html')
        else:
            msg.set_content(body)

        attachments = attachments or []
        for item in attachments:
            try:
                if isinstance(item, str):
                    path = item
                    if not os.path.exists(path):
                        logger.warning("Attachment not found: %s", path)
                        continue
                    ctype, encoding = mimetypes.guess_type(path)
                    if ctype is None:
                        ctype = "application/octet-stream"
                    maintype, subtype = ctype.split("/", 1)
                    with open(path, "rb") as fh:
                        data = fh.read()
                    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(path))
                elif isinstance(item, dict):
                    data = item.get("content")
                    filename = item.get("filename")
                    mime_type = item.get("mime_type") or "application/octet-stream"
                    if not data or not filename:
                        continue
                    maintype, subtype = mime_type.split("/", 1)
                    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
            except Exception:
                logger.error("Failed to attach file", exc_info=True)
        
        # Send email
        if mail_use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(mail_server, mail_port) as server:
                server.starttls(context=context)
                if mail_user and mail_pass:
                    server.login(mail_user, mail_pass)
                server.send_message(msg)
        else:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(mail_server, mail_port, context=context) as server:
                if mail_user and mail_pass:
                    server.login(mail_user, mail_pass)
                server.send_message(msg)
        
        logger.info(f"Email sent successfully to {recipient}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}", exc_info=True)
        return False


def send_password_reset_email(user_email, username, temp_password):
    """
    Send password reset email with temporary password
    
    Args:
        user_email: User's email address
        username: Username
        temp_password: Temporary password to send
    
    Returns:
        bool: True if sent successfully
    """
    subject = "Your Injaaz Account Password Has Been Reset"
    
    body = f"""
Hello {username},

Your password has been reset by an administrator.

Your temporary password is: {temp_password}

Please log in and change your password immediately for security.

If you did not request this password reset, please contact support immediately.

Best regards,
Injaaz Team
"""
    
    html_body = f"""
<html>
<body>
<h2>Password Reset</h2>
<p>Hello {username},</p>
<p>Your password has been reset by an administrator.</p>
<p><strong>Your temporary password is: <code>{temp_password}</code></strong></p>
<p>Please log in and change your password immediately for security.</p>
<p>If you did not request this password reset, please contact support immediately.</p>
<p>Best regards,<br>Injaaz Team</p>
</body>
</html>
"""
    
    return send_email(user_email, subject, body, html_body)

