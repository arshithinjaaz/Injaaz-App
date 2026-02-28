"""
APScheduler wrapper for the MMR daily email.
Runs a single cron job at the configured time (default 10:00 AM).
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_JOB_ID = 'mmr_daily_report'


# ──────────────────────────────────────────────────────────────────────────────
# Job function (runs outside request context – needs its own app context)
# ──────────────────────────────────────────────────────────────────────────────

def _run_scheduled_report(app):
    with app.app_context():
        try:
            import os
            from datetime import datetime, timedelta
            from .routes import _upload_path, _load_config, _format_report_date, _REPORT_DATE_PLACEHOLDER, _report_filename
            from .mmr_service import parse_excel, generate_report_excel, format_chargeable_summary_for_email
            from common.email_service import send_email

            config = _load_config()
            if not config.get('schedule_enabled'):
                return

            path = _upload_path()
            if not os.path.exists(path):
                logger.info('MMR scheduler: no Excel file found, skipping')
                return

            to_raw = config.get('to', '').strip()
            if not to_raw:
                logger.warning('MMR scheduler: no recipient configured, skipping')
                return

            to_list = [e.strip() for e in to_raw.split(',') if e.strip()]
            cc_raw  = config.get('cc', '').strip()
            cc_list = [e.strip() for e in cc_raw.split(',') if e.strip()] if cc_raw else None

            df = parse_excel(path)
            report_bytes = generate_report_excel(df)
            filename = _report_filename()

            body = config.get('body', '')
            yesterday = datetime.now() - timedelta(days=1)
            report_date = _format_report_date(yesterday)
            subject = config.get('subject', 'Daily Report on Resolved and Pending Complaints for {{REPORT_DATE}}').replace(_REPORT_DATE_PLACEHOLDER, report_date)
            body = body.replace(_REPORT_DATE_PLACEHOLDER, report_date)
            chargeable_summary = format_chargeable_summary_for_email(df)
            if chargeable_summary:
                body = (body.rstrip() + '\n\n' + chargeable_summary).rstrip()
            body = (body.rstrip() + '\n\nFor full information, please refer to the attached Excel file.').rstrip()

            send_email(
                recipient=to_list,
                subject=subject,
                body=body,
                cc=cc_list,
                attachments=[{
                    'content': report_bytes,
                    'filename': filename,
                    'mime_type': ('application/vnd.openxmlformats-'
                                  'officedocument.spreadsheetml.sheet'),
                }]
            )
            logger.info('MMR scheduled report sent successfully')
        except Exception:
            logger.exception('MMR scheduled report failed')


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def init_scheduler(app):
    """Start the background scheduler and register a job if scheduling is enabled."""
    global _scheduler

    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(daemon=True)

    try:
        from .routes import _load_config
        with app.app_context():
            config = _load_config()
        if config.get('schedule_enabled'):
            _add_job(config, app)
    except Exception:
        logger.exception('MMR scheduler: error reading config during init')

    _scheduler.start()
    logger.info('MMR APScheduler started')


def update_schedule(config: dict, app):
    """Called after the admin saves email config – refreshes the cron job."""
    global _scheduler

    if not _scheduler:
        init_scheduler(app)
        return

    # Remove existing job
    if _scheduler.get_job(_JOB_ID):
        _scheduler.remove_job(_JOB_ID)

    if config.get('schedule_enabled'):
        _add_job(config, app)
        logger.info(
            f"MMR scheduler: job set for "
            f"{config.get('schedule_hour', 10):02d}:{config.get('schedule_minute', 0):02d}"
        )
    else:
        logger.info('MMR scheduler: job disabled')


def _add_job(config: dict, app):
    global _scheduler
    _scheduler.add_job(
        _run_scheduled_report,
        CronTrigger(
            hour=int(config.get('schedule_hour', 10)),
            minute=int(config.get('schedule_minute', 0))
        ),
        args=[app],
        id=_JOB_ID,
        replace_existing=True,
    )
