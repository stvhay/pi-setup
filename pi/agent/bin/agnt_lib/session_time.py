"""Stable session start times shared by discovery and idempotent score updates."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def session_start(session_id: str) -> datetime | None:
    try:
        return datetime.strptime(session_id.split("_", 1)[0], "%Y-%m-%dT%H-%M-%S-%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            session_uuid = uuid.UUID(session_id)
            if session_uuid.version != 7:
                return None
            milliseconds = session_uuid.int >> 80
            return datetime.fromtimestamp(milliseconds // 1000, tz=timezone.utc).replace(
                microsecond=(milliseconds % 1000) * 1000
            )
        except (ValueError, OverflowError, OSError):
            return None
