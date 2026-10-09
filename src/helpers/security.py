"""Web security helpers."""


def safe_next(value):
    """Return `value` only if it's a same-site relative path (open-redirect
    guard); otherwise None. Rejects absolute URLs and protocol-relative `//`."""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return None
