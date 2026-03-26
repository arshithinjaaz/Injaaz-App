"""
Email service for sending emails (password resets, notifications)

SMTP works locally and on hosts that allow outbound 587. Render *free* web services block
outbound SMTP (see Render changelog); set BREVO_API_KEY and use the Brevo HTTP API instead.
"""
import base64
import smtplib
import ssl
import socket
import logging
import os
import mimetypes
from email.message import EmailMessage
from flask import current_app

import requests

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def _brevo_api_key(app):
    return (
        app.config.get("BREVO_API_KEY")
        or os.environ.get("BREVO_API_KEY")
        or os.environ.get("SENDINBLUE_API_KEY")
    )


def is_email_configured(app=None):
    """True if the app can send mail (SMTP or Brevo HTTP)."""
    a = app if app is not None else current_app._get_current_object()
    if _brevo_api_key(a):
        return bool(a.config.get("MAIL_DEFAULT_SENDER") or a.config.get("MAIL_USERNAME"))
    return bool(a.config.get("MAIL_SERVER"))


def _normalize_socket_timeout(timeout):
    """smtplib passes socket._GLOBAL_DEFAULT_TIMEOUT (sentinel), not None — settimeout needs float or None."""
    if timeout is None:
        return None
    if timeout is socket._GLOBAL_DEFAULT_TIMEOUT:
        return None
    return timeout


def _smtp_socket_ipv4(host, port, timeout):
    """Connect over IPv4 only. Many PaaS hosts (e.g. Render) have no usable IPv6 route to Gmail SMTP."""
    t = _normalize_socket_timeout(timeout)
    port = int(port)
    err = None
    for res in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            sock.settimeout(t)
            sock.connect(sa)
            return sock
        except OSError as e:
            err = e
            if sock is not None:
                sock.close()
    if err is not None:
        raise err
    raise OSError(f"No IPv4 address found for {host!r}")


class SMTPIPv4(smtplib.SMTP):
    """SMTP client that connects via IPv4 (avoids errno 101 on broken IPv6 in cloud)."""

    def _get_socket(self, host, port, timeout):
        return _smtp_socket_ipv4(host, port, timeout)


class SMTP_SSL_IPv4(SMTPIPv4, smtplib.SMTP_SSL):
    """SMTP_SSL over IPv4 only."""

    pass


def _send_email_brevo_http(app, recipient, subject, body, html_body, cc, attachments, api_key):
    """Send via Brevo REST API (HTTPS). Required on Render free tier where SMTP ports are blocked."""
    mail_sender = app.config.get("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME")
    if not mail_sender:
        logger.error("Brevo: set MAIL_DEFAULT_SENDER to a sender verified in Brevo")
        return False
    to_list = recipient if isinstance(recipient, (list, tuple)) else [recipient]
    payload = {
        "sender": {"email": mail_sender.strip(), "name": "Injaaz"},
        "to": [{"email": e.strip()} for e in to_list if e and str(e).strip()],
        "subject": subject,
        "textContent": (body or "").rstrip(),
    }
    if html_body:
        payload["htmlContent"] = html_body
    if cc:
        cc_list = cc if isinstance(cc, (list, tuple)) else [cc]
        payload["cc"] = [{"email": e.strip()} for e in cc_list if e and str(e).strip()]
    att_out = []
    for item in attachments or []:
        try:
            if isinstance(item, str):
                path = item
                if not os.path.exists(path):
                    logger.warning("Brevo: attachment not found: %s", path)
                    continue
                with open(path, "rb") as fh:
                    data = fh.read()
                filename = os.path.basename(path)
            elif isinstance(item, dict):
                data = item.get("content")
                filename = item.get("filename")
                if not data or not filename:
                    continue
            else:
                continue
            att_out.append(
                {"name": filename, "content": base64.b64encode(data).decode("ascii")}
            )
        except Exception:
            logger.error("Brevo: failed to read attachment", exc_info=True)
    if att_out:
        payload["attachment"] = att_out
    try:
        r = requests.post(
            BREVO_SEND_URL,
            json=payload,
            headers={"api-key": api_key, "Accept": "application/json"},
            timeout=120,
        )
        if r.status_code in (200, 201):
            logger.info("Email sent via Brevo API to %s", recipient)
            return True
        logger.error("Brevo API HTTP %s: %s", r.status_code, r.text[:4000])
        return False
    except Exception as e:
        logger.error("Brevo API request failed: %s", e, exc_info=True)
        return False


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

        brevo_key = _brevo_api_key(app)
        if brevo_key:
            return _send_email_brevo_http(
                app, recipient, subject, body, html_body, cc, attachments, brevo_key
            )

        mail_server = app.config.get('MAIL_SERVER')
        mail_port = app.config.get('MAIL_PORT', 587)
        mail_user = app.config.get('MAIL_USERNAME')
        mail_pass = app.config.get('MAIL_PASSWORD')
        mail_use_tls = app.config.get('MAIL_USE_TLS', True)
        mail_sender = app.config.get('MAIL_DEFAULT_SENDER', mail_user or 'noreply@injaaz.com')

        if not mail_server or not mail_port:
            logger.warning("Mail server/port not configured; cannot send email (or set BREVO_API_KEY)")
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
        
        # Send email (IPv4 SMTP — see SMTPIPv4 docstring)
        if mail_use_tls:
            context = ssl.create_default_context()
            with SMTPIPv4(mail_server, mail_port) as server:
                server.starttls(context=context)
                if mail_user and mail_pass:
                    server.login(mail_user, mail_pass)
                server.send_message(msg)
        else:
            context = ssl.create_default_context()
            with SMTP_SSL_IPv4(mail_server, mail_port, context=context) as server:
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

