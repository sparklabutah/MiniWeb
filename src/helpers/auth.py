"""Shared session-auth helpers for the per-site routes.

Each site resolves its own user record (its `get_user(uid)` callable) and may
key the session differently (e.g. health-portals prefers `health_user_id`, then
falls back to the global `user_id` auto-login). These two helpers hold the
common logic; a site passes its `get_user` and, if needed, its session keys.

    from helpers.auth import current_user, browsing_user
    def _get_current_user():  return current_user(_get_user)
    def _get_browsing_user(): return browsing_user(_get_user)
"""
from flask import session


def current_user(get_user, *, session_keys=("user_id",)):
    """The logged-in user for this site, or None. `session_keys` are tried in
    order; the first present one resolves the user via `get_user(uid)`."""
    for key in session_keys:
        uid = session.get(key)
        if uid is not None:
            return get_user(uid)
    return None


def browsing_user(get_user, *, session_keys=("user_id",), fallback=1):
    """(user, is_logged_in) — the logged-in user, else the `fallback` user for
    browse-only mode (is_logged_in=False)."""
    user = current_user(get_user, session_keys=session_keys)
    if user:
        return user, True
    return get_user(fallback), False
