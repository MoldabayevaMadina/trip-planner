"""
Helpers that read query parameters (?city=...&visa_free=true) and check them.
A wrong value stops the request with 400 and a clear message, instead of returning an empty list.
"""
from datetime import date

from rest_framework.exceptions import ValidationError

TRUE_VALUES = {"true", "1", "yes"}
FALSE_VALUES = {"false", "0", "no"}


def get_bool(params, name):
    """?visited=true -> True, ?visited=false -> False, missing -> None."""
    value = params.get(name)
    if value in (None, ""):
        return None
    if value.lower() in TRUE_VALUES:
        return True
    if value.lower() in FALSE_VALUES:
        return False
    raise ValidationError({name: "Use true or false."})


def get_int(params, name):
    """?trip=3 -> 3, missing -> None."""
    value = params.get(name)
    if value in (None, ""):
        return None
    if not value.isdigit():
        raise ValidationError({name: "Must be a positive whole number."})
    return int(value)


def parse_date(value, name="date"):
    """"2026-11-10" -> date(2026, 11, 10)."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({name: "Use the format YYYY-MM-DD, e.g. 2026-11-10."})


def get_date(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    return parse_date(value, name)


def get_choice(params, name, choices):
    """?category=food -> "food" if it is one of the choices."""
    value = params.get(name)
    if value in (None, ""):
        return None
    if value not in choices:
        raise ValidationError({name: f"Use one of: {', '.join(choices)}."})
    return value