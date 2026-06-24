"""Typed value normalizers for MiniWeb evaluation.

Inspired by WebArena-Verified (ServiceNow, 2025).
Each normalizer converts messy real-world values into a canonical form for comparison.
"""

import re
from datetime import datetime


def normalize(value, value_type="string"):
    """Normalize a value based on its declared type."""
    fn = NORMALIZERS.get(value_type, normalize_string)
    try:
        return fn(value)
    except (ValueError, TypeError):
        return normalize_string(value)


def normalize_string(value):
    """Normalize string: lowercase, strip whitespace, remove articles."""
    if value is None:
        return ""
    s = str(value).strip().lower()
    # Remove leading articles
    s = re.sub(r"^(the|a|an)\s+", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_number(value):
    """Normalize number: remove currency symbols, commas, units. Return float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    # Remove currency symbols and common prefixes
    s = re.sub(r"[$€£¥₹]", "", s)
    # Remove commas
    s = s.replace(",", "")
    # Remove trailing units (%, items, etc)
    s = re.sub(r"\s*(items?|products?|results?|pages?|%)\s*$", "", s, flags=re.IGNORECASE)
    # Extract first number from string
    match = re.search(r"-?\d+\.?\d*", s)
    if match:
        return float(match.group())
    return None


def normalize_boolean(value):
    """Normalize boolean: yes/no/true/false/1/0 → True/False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("yes", "true", "1", "y", "on", "enabled", "active"):
        return True
    if s in ("no", "false", "0", "n", "off", "disabled", "inactive", "none", ""):
        return False
    return None


def normalize_date(value):
    """Normalize date: various formats → YYYY-MM-DD string."""
    if value is None:
        return None
    s = str(value).strip()
    # Try common formats
    for fmt in [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d %B %Y", "%d %b %Y",
    ]:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def normalize_currency(value):
    """Normalize currency: $1,234.56 → 1234.56 as float."""
    return normalize_number(value)


def normalize_string_list(value):
    """Normalize string list: split by comma/newline, normalize each."""
    if isinstance(value, (list, tuple)):
        return sorted(normalize_string(v) for v in value)
    s = str(value)
    # Split by comma or newline
    items = re.split(r"[,\n;]", s)
    return sorted(normalize_string(v) for v in items if v.strip())


def normalize_url(value):
    """Normalize URL: remove protocol, trailing slash, www prefix."""
    if value is None:
        return ""
    s = str(value).strip()
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\.", "", s)
    s = s.rstrip("/")
    return s.lower()


NORMALIZERS = {
    "string": normalize_string,
    "number": normalize_number,
    "boolean": normalize_boolean,
    "date": normalize_date,
    "currency": normalize_currency,
    "string_list": normalize_string_list,
    "url": normalize_url,
}
