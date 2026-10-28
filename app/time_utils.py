"""
EBT System — Timezone and Date/Time Utilities
Handles consistent UTC storage with Asia/Kolkata (IST) display,
and active duration calculations.
"""

from datetime import datetime, timezone, date, timedelta
import zoneinfo
from flask import current_app

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def get_app_timezone():
    """Return configured application timezone object (defaults to Asia/Kolkata)."""
    try:
        tz_name = current_app.config.get("TIMEZONE", "Asia/Kolkata")
        return zoneinfo.ZoneInfo(tz_name)
    except Exception:
        return IST


def utc_now() -> datetime:
    """Return current naive UTC datetime for database storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now() -> datetime:
    """Return current datetime in the local configured timezone (Asia/Kolkata)."""
    tz = get_app_timezone()
    return datetime.now(timezone.utc).astimezone(tz)


def local_today() -> date:
    """Return today's date in local configured timezone (Asia/Kolkata)."""
    return local_now().date()


def to_local(dt: datetime | None) -> datetime | None:
    """
    Convert a UTC naive datetime from the database to configured local timezone.
    If dt is None, returns None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    tz = get_app_timezone()
    return dt.astimezone(tz)


def format_local_time(dt: datetime | None, fmt: str = "%I:%M %p") -> str:
    """Format UTC datetime as a string in local timezone."""
    if not dt:
        return "—"
    local_dt = to_local(dt)
    return local_dt.strftime(fmt)


def format_local_date(dt: datetime | date | None, fmt: str = "%Y-%m-%d") -> str:
    """Format UTC datetime or date in local timezone."""
    if not dt:
        return "—"
    if isinstance(dt, datetime):
        return to_local(dt).strftime(fmt)
    return dt.strftime(fmt)


def format_hours_mins(minutes: float | None) -> str:
    """Format minutes into '#h #m' string."""
    if minutes is None or minutes < 0:
        minutes = 0.0
    h = int(minutes // 60)
    m = int(round(minutes % 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h}h {m}m"


def format_mins(minutes: float | None) -> str:
    """Format minutes into '#m' string."""
    if minutes is None or minutes < 0:
        minutes = 0.0
    return f"{int(round(minutes))}m"
