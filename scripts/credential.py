"""Shared credential schema and deterministic extraction rules."""

import re
from datetime import date


FIELDS = (
    "is_credential", "holder_name", "credential_type", "license_number",
    "issuing_authority", "issue_date", "expiration_date", "expiration_status",
)
STATUSES = {"expired", "expiring_soon", "valid", "no_expiration"}


def valid_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def schema_errors(value: object) -> dict[str, str]:
    """Check shape and field domains; do not repair or normalize predictions."""
    if not isinstance(value, dict):
        return {"$": "expected a JSON object"}
    errors = {}
    extra = sorted(set(value) - set(FIELDS))
    if extra:
        errors["$"] = f"unexpected keys: {', '.join(extra)}"
    for field in FIELDS:
        if field not in value:
            errors[field] = "missing field"
            continue
        item = value[field]
        if field == "is_credential":
            if type(item) is not bool:
                errors[field] = "expected a boolean"
        elif item is not None:
            if not isinstance(item, str):
                errors[field] = "expected a string or null"
            elif field in {"issue_date", "expiration_date"} and not valid_date(item):
                errors[field] = "expected a valid YYYY-MM-DD date or null"
            elif field == "expiration_status" and item not in STATUSES:
                errors[field] = "unsupported expiration status"
    return errors


def normalize_date(value: object) -> str | None:
    """Accept ISO or unambiguous slash dates with four-digit years; never guess."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("date must be a string or null")
    text = value.strip()
    if valid_date(text):
        return text
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        first, second, year = map(int, match.groups())
        candidates = set()
        for month, day in ((first, second), (second, first)):
            try:
                candidates.add(date(year, month, day).isoformat())
            except ValueError:
                pass
        if len(candidates) == 1:
            return candidates.pop()
        if len(candidates) > 1:
            raise ValueError("ambiguous numeric date order")
    raise ValueError("invalid or unsupported date; an explicit four-digit year is required")


def finalize_credential(value: object, reference_date: str,
                        expiring_soon_window_days: int) -> dict:
    """Apply local rules, preserving all names and identifier punctuation."""
    if not isinstance(reference_date, str) or not valid_date(reference_date):
        raise ValueError("reference_date must be a valid YYYY-MM-DD date")
    if type(expiring_soon_window_days) is not int or expiring_soon_window_days < 0:
        raise ValueError("expiring_soon_window_days must be a nonnegative integer")
    if not isinstance(value, dict):
        raise ValueError("expected a credential JSON object")
    if set(value) - set(FIELDS):
        raise ValueError("unexpected credential fields")
    if type(value.get("is_credential")) is not bool:
        raise ValueError("is_credential must be a boolean")
    if value["is_credential"] is False:
        return {field: False if field == "is_credential" else None for field in FIELDS}
    # Status is derived. Missing extracted fields must not become invented nulls.
    if any(field not in value for field in FIELDS if field != "expiration_status"):
        raise ValueError("missing required extracted fields")
    result = dict(value)
    for field in ("issue_date", "expiration_date"):
        try:
            result[field] = normalize_date(result[field])
        except ValueError as exc:
            raise ValueError(f"{field}: {exc}") from None
    if result["expiration_date"] is None:
        result["expiration_status"] = "no_expiration"
    else:
        days = (date.fromisoformat(result["expiration_date"]) - date.fromisoformat(reference_date)).days
        result["expiration_status"] = (
            "expired" if days < 0 else
            "expiring_soon" if days <= expiring_soon_window_days else "valid"
        )
    errors = schema_errors(result)
    if errors:
        raise ValueError("invalid credential fields: " + ", ".join(errors))
    return result
