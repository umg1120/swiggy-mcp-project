"""Swiggy OAuth login flow: /auth/login (picker + redirect) and /auth/callback.

State (which household + PKCE verifier a login belongs to) is held in an
in-memory dict keyed by the OAuth `state` param. That's fine for a
single-process dev server and a flow that completes in seconds; it does not
survive a server restart mid-login, which just means starting over at
/auth/login.
"""

from __future__ import annotations

import datetime
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Household, Token
from app.swiggy_oauth import (
    SwiggyOAuthError,
    build_authorize_url,
    exchange_code_for_token,
    generate_pkce_pair,
    get_or_register_client,
)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

_PENDING_TTL_SECONDS = 600
# state -> (household_id, code_verifier, next_target, expires_at)
_pending_logins: dict[str, tuple[int, str, str, float]] = {}


def _store_pending(state: str, household_id: int, code_verifier: str, next_target: str) -> None:
    _pending_logins[state] = (
        household_id,
        code_verifier,
        next_target,
        time.time() + _PENDING_TTL_SECONDS,
    )


def _pop_pending(state: str) -> tuple[int, str, str] | None:
    entry = _pending_logins.pop(state, None)
    if entry is None:
        return None
    household_id, code_verifier, next_target, expires_at = entry
    if time.time() > expires_at:
        return None
    return household_id, code_verifier, next_target


@router.get("/login", response_class=HTMLResponse)
def login_picker(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    households = db.scalars(select(Household).order_by(Household.id)).all()
    return templates.TemplateResponse(request, "auth/login.html", {"households": households})


@router.get("/login/{household_id}")
def login_start(
    household_id: int, next: str = "html", db: Session = Depends(get_db)
) -> RedirectResponse:
    if next not in ("html", "react"):
        raise HTTPException(400, "next must be 'html' or 'react'")

    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(404, "Household not found")

    try:
        client = get_or_register_client(db)
    except SwiggyOAuthError as exc:
        raise HTTPException(502, str(exc)) from exc

    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(24)
    _store_pending(state, household_id, code_verifier, next)

    return RedirectResponse(build_authorize_url(client, state, code_challenge))


@router.get("/callback", response_model=None)
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    if error:
        raise HTTPException(400, error_description or error)
    if not code or not state:
        raise HTTPException(400, "Missing code/state in callback")

    pending = _pop_pending(state)
    if pending is None:
        raise HTTPException(400, "Unknown or expired login -- start again at /auth/login")
    household_id, code_verifier, next_target = pending

    try:
        client = get_or_register_client(db)
        token_response = exchange_code_for_token(client, code, code_verifier)
    except SwiggyOAuthError as exc:
        raise HTTPException(502, str(exc)) from exc

    expires_at = None
    if "expires_in" in token_response:
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=token_response["expires_in"]
        )

    token = db.scalars(
        select(Token).where(Token.household_id == household_id, Token.provider == "swiggy")
    ).first()
    if token is None:
        token = Token(household_id=household_id, provider="swiggy")
        db.add(token)

    token.access_token = token_response["access_token"]
    token.refresh_token = token_response.get("refresh_token")
    token.token_type = token_response.get("token_type", "bearer")
    token.expires_at = expires_at
    db.commit()

    household = db.get(Household, household_id)

    if next_target == "react":
        frontend_url = get_settings().frontend_url.rstrip("/")
        return RedirectResponse(f"{frontend_url}/connect?household_id={household_id}&connected=1")

    return templates.TemplateResponse(request, "auth/success.html", {"household": household})
