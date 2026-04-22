"""
APScheduler wrapper for the MMR daily email.
Runs a cron job at the configured time (default 10:00 AM) and a reminder one hour earlier.

Schedule hour/minute are interpreted in Dubai time (Asia/Dubai), not server UTC.
Override with env MMR_SCHEDULE_TIMEZONE (e.g. UTC for debugging).
"""
import logging
import os
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def _cron_timezone():
    """IANA zone for cron triggers; default Asia/Dubai (UAE)."""
    name = (os.environ.get('MMR_SCHEDULE_TIMEZONE') or 'Asia/Dubai').strip() or 'Asia/Dubai'
    try:
        return ZoneInfo(name)
    except Exception:
        logger.warning(
            'MMR scheduler: invalid MMR_SCHEDULE_TIMEZONE=%r, using Asia/Dubai',
            name,
        )
        return ZoneInfo('Asia/Dubai')

_scheduler: BackgroundScheduler | None = None
_JOB_ID = 'mmr_daily_report'
_REMINDER_JOB_ID = 'mmr_upload_reminder'
_REMINDER_RECIPIENTS = ['arshith@injaaz.ae', 'arshithinjaaz@gmail.com']


# ──────────────────────────────────────────────────────────────────────────────
# Job function (runs outside request context – needs its own app context)
# ──────────────────────────────────────────────────────────────────────────────

def _run_scheduled_report(app):
    with app.app_context():
        try:
            from datetime import datetime, timedelta
            from .routes import (_upload_path, _load_config, _save_config, _save_last_run,
                                  append_automation_activity,
                                  _save_report_to_folder, _save_email_report_to_network,
                                  _format_report_date, _format_report_date_range_str,
                                  _REPORT_DATE_PLACEHOLDER, _report_filename, _complete_current_cycle)
            from .mmr_service import parse_excel, generate_report_excel, get_report_date_range_from_df, get_report_date_from_excel, format_chargeable_summary_for_email, format_per_tower_chargeable_html_for_email
            from common.email_service import send_email

            config = _load_config()
            if not config.get('schedule_enabled'):
                return
            if config.get('schedule_paused'):
                logger.info('MMR scheduler: paused (upload new Excel to resume)')
                return

            path = _upload_path()
            if not os.path.exists(path):
                logger.info('MMR scheduler: no Excel file found, skipping')
                append_automation_activity(
                    'run_skipped',
                    'Scheduled run skipped: no Excel file on the server',
                    None,
                    meta={'reason': 'no_file'},
                )
                return

            last_mt = config.get('last_sent_source_mtime')
            if last_mt is not None:
                try:
                    if os.path.getmtime(path) <= float(last_mt) + 0.001:
                        logger.warning(
                            'MMR scheduler: Excel unchanged since last send; skipping (upload required)'
                        )
                        cfg2 = _load_config()
                        cfg2['schedule_paused'] = True
                        _save_config(cfg2)
                        append_automation_activity(
                            'run_skipped',
                            'Scheduled run skipped: Excel file unchanged since last send',
                            'Upload a fresh CAFM export before the next run.',
                            meta={'reason': 'stale_file'},
                        )
                        return
                except (TypeError, ValueError):
                    pass

            to_raw = config.get('to', '').strip()
            if not to_raw:
                logger.warning('MMR scheduler: no recipient configured, skipping')
                append_automation_activity(
                    'run_skipped',
                    'Scheduled run skipped: no recipients configured',
                    None,
                    meta={'reason': 'no_recipients'},
                )
                return

            to_list = [e.strip() for e in to_raw.split(',') if e.strip()]
            cc_raw  = config.get('cc', '').strip()
            cc_list = [e.strip() for e in cc_raw.split(',') if e.strip()] if cc_raw else None

            df = parse_excel(path)
            report_bytes = generate_report_excel(df)
            date_range = get_report_date_range_from_df(df)
            rf = config.get('report_format', 'daily')
            rf = str(rf).strip().lower() if rf is not None else 'daily'
            if rf not in ('daily', 'monthly'):
                rf = 'daily'
            filename = _report_filename(report_date_range=date_range, upload_path=path, report_format=rf)

            body = config.get('body', '')
            report_date = _format_report_date_range_str(date_range)
            if report_date is None:
                report_dt = get_report_date_from_excel(path) or (datetime.now() - timedelta(days=1))
                report_date = _format_report_date(report_dt)
            subject = config.get('subject', 'Daily Report on Resolved and Pending Complaints for {{REPORT_DATE}}').replace(_REPORT_DATE_PLACEHOLDER, report_date)
            body = body.replace(_REPORT_DATE_PLACEHOLDER, report_date)
            intro_for_html = body.rstrip()
            chargeable_summary = format_chargeable_summary_for_email(df)
            if chargeable_summary:
                body = (body.rstrip() + '\n\n' + chargeable_summary).rstrip()
            body = (body.rstrip() + '\n\nFor full information, please refer to the attached Excel file.').rstrip()

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

            send_email(
                recipient=to_list,
                subject=subject,
                body=body,
                html_body=html_body,
                cc=cc_list,
                attachments=[{
                    'content': report_bytes,
                    'filename': filename,
                    'mime_type': ('application/vnd.openxmlformats-'
                                  'officedocument.spreadsheetml.sheet'),
                }]
            )
            recipient_count = len(to_list) + (len(cc_list) if cc_list else 0)
            cid = _complete_current_cycle('scheduler', subject, recipient_count, filename)
            _save_last_run(
                'success', to_list, cc_list, subject, recipient_count,
                activity_source='scheduler', cycle_id=cid,
            )
            _save_report_to_folder(report_bytes, filename, 'email')
            _save_email_report_to_network(report_bytes, filename)
            logger.info('MMR scheduled report sent successfully')
        except Exception:
            logger.exception('MMR scheduled report failed')
            try:
                from .routes import _load_config, _save_last_run
                config = _load_config()
                to_raw = config.get('to', '').strip()
                to_list = [e.strip() for e in to_raw.split(',') if e.strip()] if to_raw else []
                cc_raw = config.get('cc', '').strip()
                cc_list = [e.strip() for e in cc_raw.split(',') if e.strip()] if cc_raw else None
                _save_last_run(
                    'failed', to_list or [], cc_list or [], '', 0,
                    activity_source='scheduler',
                )
            except Exception:
                pass


def _reminder_hour_minute(schedule_hour: int, schedule_minute: int) -> tuple[int, int]:
    """One hour before the main job, same minute (e.g. 10:00 → 09:00)."""
    h = (int(schedule_hour) - 1) % 24
    return h, int(schedule_minute)


def _run_upload_reminder(app):
    """Email ops ~1h before the scheduled send when a fresh Excel is still required."""
    with app.app_context():
        try:
            from datetime import datetime

            from flask import current_app

            from .routes import _load_config, _save_config, append_automation_activity
            from common.email_service import is_email_configured, send_email

            config = _load_config()
            if not config.get('schedule_enabled'):
                return
            if not config.get('automation_waiting_for_fresh_upload'):
                return
            if not config.get('schedule_paused'):
                return

            tz = _cron_timezone()
            now = datetime.now(tz)
            today = now.date().isoformat()
            if config.get('last_upload_reminder_sent_date') == today:
                return

            if not is_email_configured(current_app):
                logger.warning('MMR upload reminder: email not configured, skipping')
                return

            # Reminder recipients are intentionally fixed (independent from MMR To/CC config).
            # This allows explicit reminder routing without affecting main daily report emails.
            to_list = list(_REMINDER_RECIPIENTS)
            cc_list = None

            sh = int(config.get('schedule_hour', 10))
            sm = int(config.get('schedule_minute', 0))
            tz_label = getattr(tz, 'key', str(tz))
            body = (
                f'This is a reminder: MMR email automation is scheduled for '
                f'{sh:02d}:{sm:02d} ({tz_label}).\n\n'
                f'Please upload a fresh CAFM Excel file on the MMR dashboard before that time. '
                f'If no new file is uploaded, the automation will not run.\n\n'
                f'After each successful send, a new upload is required for the next scheduled run.'
            )
            subject = f"[MMR Reminder] Upload today's Excel before {sh:02d}:{sm:02d}"
            ok = send_email(
                recipient=to_list,
                subject=subject,
                body=body,
                cc=cc_list,
            )
            if ok:
                config = _load_config()
                config['last_upload_reminder_sent_date'] = today
                _save_config(config)
                append_automation_activity(
                    'reminder_sent',
                    'Reminder email sent (upload Excel before the scheduled send)',
                    f'Scheduled send: {sh:02d}:{sm:02d} {tz_label}.',
                    meta={'schedule_hour': sh, 'schedule_minute': sm},
                )
                logger.info('MMR upload reminder sent')
        except Exception:
            logger.exception('MMR upload reminder failed')


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
            tz = _cron_timezone()
            sh = int(config.get('schedule_hour', 10))
            sm = int(config.get('schedule_minute', 0))
            rh, rm = _reminder_hour_minute(sh, sm)
            logger.info(
                'MMR scheduler: report %02d:%02d, reminder %02d:%02d %s (startup)',
                sh, sm, rh, rm, getattr(tz, 'key', str(tz)),
            )
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

    for jid in (_JOB_ID, _REMINDER_JOB_ID):
        if _scheduler.get_job(jid):
            _scheduler.remove_job(jid)

    if config.get('schedule_enabled'):
        _add_job(config, app)
        tz = _cron_timezone()
        rh, rm = _reminder_hour_minute(
            int(config.get('schedule_hour', 10)),
            int(config.get('schedule_minute', 0)),
        )
        logger.info(
            'MMR scheduler: report %02d:%02d, reminder %02d:%02d %s',
            int(config.get('schedule_hour', 10)),
            int(config.get('schedule_minute', 0)),
            rh,
            rm,
            getattr(tz, 'key', str(tz)),
        )
    else:
        logger.info('MMR scheduler: jobs disabled')


def _add_job(config: dict, app):
    global _scheduler
    tz = _cron_timezone()
    sh = int(config.get('schedule_hour', 10))
    sm = int(config.get('schedule_minute', 0))
    _scheduler.add_job(
        _run_scheduled_report,
        CronTrigger(hour=sh, minute=sm, timezone=tz),
        args=[app],
        id=_JOB_ID,
        replace_existing=True,
    )
    rh, rm = _reminder_hour_minute(sh, sm)
    _scheduler.add_job(
        _run_upload_reminder,
        CronTrigger(hour=rh, minute=rm, timezone=tz),
        args=[app],
        id=_REMINDER_JOB_ID,
        replace_existing=True,
    )
