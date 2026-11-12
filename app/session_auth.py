"""Single-operator session auth, gating `/api/*` (see `app/main.py`).

This is a separate concern from `app/swiggy_oauth.py`/`app/routers/auth.py`,
which authenticate the *app* to Swiggy on a household's behalf -- this
authenticates a *person* to this app at all. One shared password (this app
has exactly one operator, not a users table), checked with `bcrypt`.

The session itself is a signed, expiring cookie (`itsdangerous`) rather than
a server-side session store, so no new DB table is needed -- verifying a
cookie is just checking its signature and age, no lookup required.

Cookie, not a header/API key: `/auth/login/{household_id}`
(`frontend/src/pages/Connect.tsx`) is a full-page `window.location.href`
redirect, and `/auth/callback` is Swiggy's server redirecting the browser
back -- neither can carry a custom header. A cookie rides along
automatically on both (with `SameSite=Lax`), so this needs no exceptions
carved into the OAuth flow.
"""

from __future__ import annotations

import bcrypt
from fastapi import Cookie, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

settings = get_settings()

COOKIE_NAME = "swiggy_mcp_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30 days
# itsdangerous "salt": namespaces this signature so it can't be replayed
# against some other signed value in this app -- not a password salt.
_SIGNING_SALT = "swiggy-mcp-session"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # Malformed hash -- e.g. APP_PASSWORD_HASH set to something that
        # isn't actually a bcrypt hash. Fail closed, not with a 500.
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret_key, salt=_SIGNING_SALT)


def create_session_token() -> str:
    return _serializer().dumps({"authenticated": True})


def _is_valid_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return False
    return True


def require_session(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    """FastAPI dependency -- 401s unless the session cookie is present,
    correctly signed, and not expired. Applied at the router level to
    `api.router` (see `app/main.py`), so it covers every `/api/*` route --
    current and future -- with no per-route wiring needed."""
    if not _is_valid_session(session):
        raise HTTPException(401, "Not authenticated -- log in first")
