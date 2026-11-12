"""Step 5: chat UI. One free-text box in front of `app/llm_agent.py`'s
Gemini-driven tool calling, following `instamart.py`'s pattern (household ->
address -> live MCP call).

Stateless like every other page here -- there's no server-side session
store, so the running Gemini history round-trips through a hidden
`history_json` form field between requests (see `llm_agent.run_chat_turn`).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.instamart_client import InstamartMCPError, get_addresses
from app.llm_agent import ChatError, run_chat_turn
from app.models import Household, Token
from app.schemas import InstamartAddress

router = APIRouter(prefix="/chat", tags=["chat"])
templates = Jinja2Templates(directory="app/templates")


def _connected_household_ids(db: Session) -> set[int]:
    return set(db.scalars(select(Token.household_id).where(Token.provider == "swiggy")).all())


def _token_for(db: Session, household_id: int) -> Token | None:
    return db.scalars(
        select(Token).where(Token.household_id == household_id, Token.provider == "swiggy")
    ).first()


def _display_transcript(history: list[dict]) -> list[dict]:
    """Collapse Gemini's raw turn history -- which also holds tool-call and
    tool-response turns, see `llm_agent`'s module docstring -- down to the
    (user, assistant) text turns a person should actually see."""
    turns = []
    for content in history:
        text = "".join(part.get("text", "") for part in content.get("parts") or [] if part.get("text"))
        if not text:
            continue
        turns.append({"role": "user" if content.get("role") == "user" else "assistant", "text": text})
    return turns


async def _load_addresses(token: Token) -> list[InstamartAddress]:
    try:
        raw_addresses = await get_addresses(token.access_token)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc
    return [InstamartAddress.model_validate(a) for a in raw_addresses]


@router.get("", response_class=HTMLResponse)
async def chat_form(
    request: Request, household_id: int | None = None, db: Session = Depends(get_db)
) -> HTMLResponse:
    households = db.scalars(select(Household).order_by(Household.id)).all()
    context = {
        "households": households,
        "connected_ids": _connected_household_ids(db),
        "selected_household_id": household_id,
        "addresses": None,
        "transcript": [],
        "history_json": "[]",
    }

    if household_id is not None:
        token = _token_for(db, household_id)
        if token is None:
            raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")
        context["addresses"] = await _load_addresses(token)

    return templates.TemplateResponse(request, "chat/index.html", context)


@router.post("", response_class=HTMLResponse)
async def chat_send(
    request: Request,
    household_id: int = Form(...),
    address_id: str | None = Form(None),
    message: str = Form(..., min_length=1),
    history_json: str = Form("[]"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    households = db.scalars(select(Household).order_by(Household.id)).all()
    connected_ids = _connected_household_ids(db)

    token = _token_for(db, household_id)
    if token is None:
        raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")

    addresses = await _load_addresses(token)

    try:
        history = json.loads(history_json)
    except json.JSONDecodeError:
        history = []

    household = db.scalars(
        select(Household).options(selectinload(Household.members)).where(Household.id == household_id)
    ).first()
    member_notes = [(m.name, m.preferences) for m in (household.members if household else []) if m.preferences]

    try:
        new_history = await run_chat_turn(
            history,
            message,
            access_token=token.access_token,
            address_id=address_id,
            household_name=household.name if household else None,
            member_notes=member_notes,
        )
    except ChatError as exc:
        raise HTTPException(502, str(exc)) from exc

    return templates.TemplateResponse(
        request,
        "chat/index.html",
        {
            "households": households,
            "connected_ids": connected_ids,
            "selected_household_id": household_id,
            "selected_address_id": address_id,
            "addresses": addresses,
            "transcript": _display_transcript(new_history),
            "history_json": json.dumps(new_history),
        },
    )
