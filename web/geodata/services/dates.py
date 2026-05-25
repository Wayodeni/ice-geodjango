from datetime import date, datetime

from django.utils.dateparse import parse_date


def coerce_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        parsed = parse_date(value)
        if parsed is not None:
            return parsed
    raise ValueError(f"Expected a date value, got {value!r}")
