"""APScheduler: write a database snapshot every 30 minutes.

Files land in ./backups (or DB_BACKUPS_DIR / GENERATED_DIR/db_backups).
Disable with DB_BACKUP_SCHEDULER=0. Interval: DB_BACKUP_INTERVAL_MINUTES (default 30).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_JOB_ID = "db_snapshot_interval"


def _is_testing(app) -> bool:
    if app is not None and app.config.get("TESTING"):
        return True
    env = (os.environ.get("TESTING") or "").strip().lower()
    if env in ("1", "true", "yes"):
        return True
    return (os.environ.get("FLASK_ENV") or "").strip().lower() == "testing"


def _disabled(app) -> bool:
    flag = (os.environ.get("DB_BACKUP_SCHEDULER") or "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return True
    return _is_testing(app)


def _interval_minutes() -> int:
    raw = (os.environ.get("DB_BACKUP_INTERVAL_MINUTES") or "30").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def _run_backup(app) -> None:
    with app.app_context():
        try:
            from scripts.db_snapshot import create_backup, prune_backups

            dest = create_backup()
            keep_raw = (os.environ.get("DB_BACKUP_KEEP") or "48").strip()
            try:
                keep = max(1, int(keep_raw))
            except ValueError:
                keep = 48
            prune_backups(keep)
            logger.info("DB snapshot wrote %s", dest)
        except Exception:
            logger.exception("DB snapshot scheduler failed")


def init_scheduler(app) -> None:
    global _scheduler
    if _disabled(app):
        return
    if _scheduler and _scheduler.running:
        return
    minutes = _interval_minutes()
    tz_name = (os.environ.get("AUTOMATION_SCHEDULE_TIMEZONE") or "Asia/Dubai").strip() or "Asia/Dubai"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Asia/Dubai")
    _scheduler = BackgroundScheduler(daemon=True, timezone=tz)
    _scheduler.add_job(
        _run_backup,
        IntervalTrigger(minutes=minutes, timezone=tz),
        args=[app],
        id=_JOB_ID,
        replace_existing=True,
        next_run_time=datetime.now(tz) + timedelta(seconds=45),
        coalesce=True,
        max_instances=1,
        misfire_grace_time=minutes * 60,
    )
    _scheduler.start()
    logger.info("DB snapshot APScheduler started (every %s minutes)", minutes)
