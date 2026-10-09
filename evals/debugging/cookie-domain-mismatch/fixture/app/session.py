# Synthetic fixture. Not a real service.
import time
from . import config

_store = {}  # sid -> {"user": str, "expires": float}


def create_session(response, user):
    sid = _new_sid()
    _store[sid] = {"user": user, "expires": time.time() + config.SESSION_TTL_SECONDS}
    response.set_cookie(
        config.SESSION_COOKIE_NAME,
        sid,
        domain=config.SESSION_COOKIE_DOMAIN,
        max_age=config.SESSION_TTL_SECONDS,
        secure=config.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=config.SESSION_COOKIE_SAMESITE,
        path="/",
    )
    return sid


def current_user(request):
    sid = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not sid:
        return None
    entry = _store.get(sid)
    if not entry or entry["expires"] < time.time():
        return None
    return entry["user"]


def _new_sid():
    import secrets
    return secrets.token_urlsafe(32)
