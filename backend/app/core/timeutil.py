"""Date/time helpers for consistent UTC handling across drivers.

MariaDB returns timezone-aware datetimes while SQLite returns naive ones;
all comparisons must normalize to aware UTC.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ensure_aware(value: datetime | None) -> datetime | None:
    return ensure_utc(value)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)