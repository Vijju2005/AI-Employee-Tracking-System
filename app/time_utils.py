"""
EBT System — Timezone and Date/Time Utilities
Handles consistent UTC storage with Asia/Kolkata (IST) display,
and active duration calculations.
"""

from datetime import datetime, timezone, date, timedelta, time
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


def parse_iso_date(value: str | None) -> date | None:
    """Parse an ISO date string into a date object, ignoring invalid values."""
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def parse_iso_datetime_start(value: str | None) -> datetime | None:
    """Convert ISO date input to the start of that day as a naive datetime."""
    parsed = parse_iso_date(value)
    if parsed is None:
        return None
    return datetime.combine(parsed, time.min)


def parse_iso_datetime_end(value: str | None) -> datetime | None:
    """Convert ISO date input to the end of that day as a naive datetime."""
    parsed = parse_iso_date(value)
    if parsed is None:
        return None
    return datetime.combine(parsed, time.max)


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


def get_current_session_cycle_id() -> str:
    """
    Return the session cycle identifier for the current time in IST.
    A new cycle begins every day at 18:00 (6:00 PM) IST.
    Sessions created before 18:00 belong to the previous day's 18:00 cycle.
    Sessions created at or after 18:00 belong to today's 18:00 cycle.
    """
    now = local_now()
    cutoff_time = time(18, 0, 0)
    if now.time() < cutoff_time:
        cycle_date = (now - timedelta(days=1)).date()
    else:
        cycle_date = now.date()
    return f"{cycle_date.isoformat()}_18:00_IST"


def get_ms_until_next_6pm_ist() -> int:
    """
    Calculate milliseconds remaining until the upcoming 6:00 PM (18:00) IST.
    """
    now = local_now()
    target_today = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now >= target_today:
        target_next = target_today + timedelta(days=1)
    else:
        target_next = target_today
    delta = target_next - now
    return max(1000, int(delta.total_seconds() * 1000))

