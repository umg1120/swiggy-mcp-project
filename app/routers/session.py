"""App-level login for a person to use this app at all -- distinct from
`app/routers/auth.py`'s Swiggy OAuth, which links a *household* to its own
Swiggy account. See `app/session_auth.py` for the design."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.config import get_settings
from app.session_auth import COOKIE_NAME, SESSION_MAX_AGE_SECONDS, create_session_token, require_session, verify_password

router = APIRouter(prefix="/auth/session", tags=["session"])


class LoginIn(BaseModel):
    password: str


@router.post("/login")
def login(payload: LoginIn, response: Response) -> dict:
    # Calls get_settings() fresh (cheap -- it's lru_cache'd) rather than
    # holding a module-level `settings` reference, so tests can
    # monkeypatch APP_PASSWORD_HASH + Settings.cache_clear() and have it
    # actually take effect -- a stale module-level reference wouldn't see
    # the change.
    settings = get_settings()
    if settings.app_password_hash is None or not verify_password(
        payload.password, settings.app_password_hash
    ):
        raise HTTPException(401, "Incorrect password")
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(),
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE_SECONDS,
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME)
    return {"authenticated": False}


@router.get("/me", dependencies=[Depends(require_session)])
def me() -> dict:
    """A valid session cookie is all this needs to check -- `require_session`
    already 401s otherwise, so reaching this line means yes."""
    return {"authenticated": True}
