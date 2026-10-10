from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_FORMATS = ("%Y%m%dT%H%M%SZ", "%a %b %d %H:%M:%S %z %Y")


def parse_dt(value) -> datetime | None:
    """Parse the date formats our sources use (GDELT, X, ISO, RFC 2822, epoch) into aware UTC datetimes."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        dt = _parse_string(str(value).strip())
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_string(s: str) -> datetime | None:
    for fmt in _FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
