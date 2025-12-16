"""
Generator module for HVAC MEP submissions.

- Uses module_site_visit.utils.pdf_generator.generate_visit_pdf
  and module_site_visit.utils.excel_writer.create_report_workbook
  to produce PDF and Excel reports.
- Updates job progress using common.utils helpers.
- Optionally sends an email with attachments or links using Flask app config.

Call:
    process_submission(job_id, submission_path, app)

Runs inside a background thread/process. The caller (routes) should pass
the Flask `app` object so this function can push an app_context().
"""
import os
import json
import time
import traceback
import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime

from flask import url_for

# import our existing report generators (site_visit utilities)
from module_site_visit.utils.pdf_generator import generate_visit_pdf
from module_site_visit.utils.excel_writer import create_report_workbook

# job helpers
from common.utils import mark_job_done, update_job_progress

# Defaults (if not provided in app.config)
BLUEPRINT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BLUEPRINT_DIR)
DEFAULT_GENERATED_DIR = os.path.join(BASE_DIR, "generated")
DEFAULT_UPLOADS_DIR = os.path.join(DEFAULT_GENERATED_DIR, "uploads")
DEFAULT_JOBS_DIR = os.path.join(DEFAULT_GENERATED_DIR, "jobs")


def _paths_from_app(app):
    gen = app.config.get("GENERATED_DIR", DEFAULT_GENERATED_DIR)
    uploads = app.config.get("UPLOADS_DIR", DEFAULT_UPLOADS_DIR)
    jobs = app.config.get("JOBS_DIR", DEFAULT_JOBS_DIR)
    return gen, uploads, jobs


def _send_email(app, subject, body, recipients, attachments=None):
    """
    Simple SMTP mailer using app.config. Returns True on success.
    Config keys:
      MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD,
      MAIL_USE_TLS, MAIL_USE_SSL, MAIL_DEFAULT_SENDER
    """
    if not recipients:
        app.logger.warning("No recipients provided for email")
        return False

    mail_server = app.config.get("MAIL_SERVER")
    mail_port = int(app.config.get("MAIL_PORT", 0) or 0)
    mail_user = app.config.get("MAIL_USERNAME")
    mail_pass = app.config.get("MAIL_PASSWORD")
    mail_use_tls = bool(app.config.get("MAIL_USE_TLS", False))
    mail_use_ssl = bool(app.config.get("MAIL_USE_SSL", False))
    mail_sender = app.config.get("MAIL_DEFAULT_SENDER") or mail_user

    if not mail_server or not mail_port:
        app.logger.warning("Mail server/port not configured; skipping email")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_sender
    if isinstance(recipients, (list, tuple)):
        msg["To"] = ", ".join(recipients)
    else:
        msg["To"] = recipients
    msg.set_content(body)

    attachments = attachments or []
    for path in attachments:
        try:
            if not os.path.exists(path):
                app.logger.warning("Attachment not found: %s", path)
                continue
            ctype, encoding = mimetypes.guess_type(path)
            if ctype is None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            with open(path, "rb") as fh:
                data = fh.read()
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(path))
        except Exception:
            app.logger.exception("Failed to attach file %s", path)

    try:
        if mail_use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(mail_server, mail_port, context=context) as server:
                if mail_user and mail_pass:
                    server.login(mail_user, mail_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(mail_server, mail_port) as server:
                if mail_use_tls:
                    server.starttls()
                if mail_user and mail_pass:
                    server.login(mail_user, mail_pass)
                server.send_message(msg)
        app.logger.info("Email sent to %s", recipients)
        return True
    except Exception:
        app.logger.exception("Failed to send email")
        return False


def process_submission(job_id, submission_path, app):
    """
    Main background worker. Expects `app` (Flask app instance) so the function
    can push an app_context for url_for and config lookups.
    """
    gen_dir, uploads_dir, jobs_dir = _paths_from_app(app)

    try:
        update_job_progress(jobs_dir, job_id, 5)

        # load submission json
        submission = {}
        try:
            if submission_path and os.path.exists(submission_path):
                with open(submission_path, "r", encoding="utf-8") as sf:
                    submission = json.load(sf)
        except Exception:
            app.logger.exception("Failed to load submission JSON")
            submission = {}

        # Build visit_info and processed_items expected by site_visit utils
        visit_info = {}
        visit_info["building_name"] = submission.get("site_name") or submission.get("id", "Unknown")
        visit_info["building_address"] = submission.get("site_address", "")  # optional
        visit_info["visit_date"] = submission.get("visit_date", "")
        # signatures: our routes saved dicts like {"saved": "<fname>", "url": "<external url>"}
        tech_sig = submission.get("tech_signature") or {}
        opman_sig = submission.get("opman_signature") or {}
        if isinstance(tech_sig, dict):
            if tech_sig.get("url"):
                visit_info["tech_signature_url"] = tech_sig.get("url")
            # compute local path if saved filename present
            if tech_sig.get("saved"):
                visit_info["tech_signature_path"] = os.path.join(uploads_dir, tech_sig.get("saved"))
        if isinstance(opman_sig, dict):
            if opman_sig.get("url"):
                visit_info["opMan_signature_url"] = opman_sig.get("url")
            if opman_sig.get("saved"):
                visit_info["opMan_signature_path"] = os.path.join(uploads_dir, opman_sig.get("saved"))

        # additional metadata (optional)
        visit_info["technician_name"] = submission.get("technician_name") or submission.get("tech_name") or ""
        visit_info["opMan_name"] = submission.get("opMan_name") or ""
        visit_info["contact_person"] = submission.get("contact_person") or ""
        visit_info["contact_number"] = submission.get("contact_number") or ""
        visit_info["email"] = submission.get("email") or ""
        visit_info["general_notes"] = submission.get("general_notes") or ""

        processed_items = []
        for it in submission.get("items", []) or []:
            # each item may include photos saved earlier with 'path' and 'url'
            image_paths = []
            image_urls = []
            for p in (it.get("photos") or []):
                if isinstance(p, dict):
                    # routes.py saved 'path' and 'url'
                    if p.get("path"):
                        image_paths.append(p.get("path"))
                    if p.get("url"):
                        image_urls.append(p.get("url"))
                else:
                    # fallback if photos are saved as strings (filenames)
                    try:
                        # treat as saved filename
                        fp = os.path.join(uploads_dir, p)
                        if os.path.exists(fp):
                            image_paths.append(fp)
                    except Exception:
                        pass
            processed_items.append({
                "asset": it.get("asset", ""),
                "system": it.get("system", ""),
                "description": it.get("description", ""),
                "quantity": it.get("quantity", ""),
                "brand": it.get("brand", ""),
                "comments": it.get("comments", ""),
                "image_paths": image_paths,
                "image_urls": image_urls,
            })

        # Generate Excel and PDF inside app_context so url_for builds correct external URLs
        with app.app_context():
            update_job_progress(jobs_dir, job_id, 15)
            # Excel: create_report_workbook(output_dir, visit_info, processed_items) -> (path, filename)
            try:
                excel_path, excel_filename = create_report_workbook(gen_dir, visit_info, processed_items)
            except Exception:
                app.logger.exception("Excel generation failed")
                excel_path, excel_filename = None, None

            update_job_progress(jobs_dir, job_id, 50)

            # PDF: generate_visit_pdf(visit_info, processed_items, output_dir)
            try:
                pdf_path, pdf_filename = generate_visit_pdf(visit_info, processed_items, gen_dir)
            except TypeError:
                # older signature order (some callers pass output_dir first)
                try:
                    pdf_path, pdf_filename = generate_visit_pdf(visit_info, processed_items, gen_dir)
                except Exception:
                    app.logger.exception("PDF generation failed")
                    pdf_path, pdf_filename = None, None
            except Exception:
                app.logger.exception("PDF generation failed")
                pdf_path, pdf_filename = None, None

            update_job_progress(jobs_dir, job_id, 85)

            results = []
            attachments = []
            # Prefer base_url stored with the submission to build absolute links
            base = submission.get("base_url") if isinstance(submission, dict) else None

            if excel_filename:
                rel = url_for("hvac_mep_bp.download_generated", filename=excel_filename, _external=False)
                url = f"{base}{rel}" if base else rel
                results.append({"filename": excel_filename, "url": url})
                if excel_path and os.path.exists(excel_path):
                    attachments.append(excel_path)
            if pdf_filename:
                rel = url_for("hvac_mep_bp.download_generated", filename=pdf_filename, _external=False)
                url = f"{base}{rel}" if base else rel
                results.append({"filename": pdf_filename, "url": url})
                if pdf_path and os.path.exists(pdf_path):
                    attachments.append(pdf_path)

            # Try to send email if configured
            recipients_conf = app.config.get("MAIL_RECIPIENTS") or app.config.get("NOTIFY_RECIPIENTS")
            recipients = []
            if recipients_conf:
                if isinstance(recipients_conf, str):
                    recipients = [r.strip() for r in recipients_conf.split(",") if r.strip()]
                elif isinstance(recipients_conf, (list, tuple)):
                    recipients = list(recipients_conf)

            email_sent = False
            if recipients:
                subject = f"Injaaz - HVAC/MEP Submission {submission.get('id') or job_id}"
                links = "\n".join([f"{r['filename']}: {r['url']}" for r in results])
                body = f"Submission {submission.get('id') or job_id} processed.\n\nFiles:\n{links}\n\nRegards,\nInjaaz"
                try:
                    email_sent = _send_email(app, subject, body, recipients, attachments=attachments)
                except Exception:
                    app.logger.exception("Error while sending email")
                    email_sent = False

            # Mark job done
            meta = {"generated": results, "email_sent": bool(email_sent)}
            mark_job_done(jobs_dir, job_id, meta)
            update_job_progress(jobs_dir, job_id, 100)

    except Exception:
        traceback.print_exc()
        try:
            update_job_progress(jobs_dir, job_id, 0, state="failed", results=[{"error": "internal error"}])
        except Exception:
            pass