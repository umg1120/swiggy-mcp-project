"""Step 6: JSON API for the React frontend (`frontend/`).

Deliberately a thin, separate layer rather than a rewrite of
`households.py`/`dineout.py`/`instamart.py`/`chat.py` -- those keep serving
the original Jinja2 pages untouched. This router calls the exact same
`app.*_client` functions and `app.schemas` models, just returns JSON instead
of a `TemplateResponse`, following the household -> token -> live MCP call
pattern already established there.
"""

from __future__ import annotations

import datetime
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dineout_client import DineoutMCPError, search_restaurants
from app.instamart_client import (
    InstamartMCPError,
    add_to_cart,
    clear_cart,
    get_addresses,
    get_cart,
    search_products,
)
from app.llm_agent import ChatError, run_chat_turn
from app.models import Household, HouseholdMember, Token
from app.schemas import (
    DineoutSearchResult,
    HouseholdCreate,
    InstamartAddress,
    InstamartCart,
    InstamartSearchResult,
)

router = APIRouter(prefix="/api", tags=["api"])

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _is_expired(expires_at: datetime.datetime | None) -> bool:
    """True only if we can *prove* the token has expired -- no `expires_at`
    stored means we can't tell, so treat it as not expired rather than
    false-flag a working connection as needing reconnect."""
    if expires_at is None:
        return False
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_at.tzinfo is None:
        # SQLite doesn't reliably round-trip tzinfo through SQLAlchemy's
        # DateTime(timezone=True) -- normalize to naive-UTC so this can't
        # crash on an aware/naive mismatch either way.
        now = now.replace(tzinfo=None)
    return expires_at < now


def _swiggy_tokens(db: Session) -> dict[int, Token]:
    tokens = db.scalars(select(Token).where(Token.provider == "swiggy")).all()
    return {t.household_id: t for t in tokens}


def _token_for(db: Session, household_id: int) -> Token:
    token = db.scalars(
        select(Token).where(Token.household_id == household_id, Token.provider == "swiggy")
    ).first()
    if token is None:
        raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")
    if _is_expired(token.expires_at):
        raise HTTPException(
            400, "That household's Swiggy connection has expired -- reconnect via /connect"
        )
    return token


def _validate(model: type[_ModelT], payload: dict, label: str) -> _ModelT:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            502, f"{label} response didn't match the expected schema: {exc}\nraw payload: {payload!r}"
        ) from exc


# -- Households --------------------------------------------------------


class MemberOut(BaseModel):
    name: str
    preferences: str | None


class HouseholdOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    members: list[MemberOut]
    # True only when a token exists AND isn't expired -- so every existing
    # consumer that already gates on `connected` (HouseholdPicker disabling
    # a chip, Home's "connect" nudge, etc.) correctly treats an expired
    # connection the same as never-connected, with no changes needed there.
    connected: bool
    # True only when a token exists but is expired -- lets the UI show
    # "reconnect" instead of "connect" without changing `connected`'s
    # gating semantics above.
    token_expired: bool = Field(alias="tokenExpired")


def _household_out(h: Household, tokens: dict[int, Token]) -> HouseholdOut:
    token = tokens.get(h.id)
    expired = _is_expired(token.expires_at) if token else False
    return HouseholdOut(
        id=h.id,
        name=h.name,
        members=[MemberOut(name=m.name, preferences=m.preferences) for m in h.members],
        connected=token is not None and not expired,
        token_expired=expired,
    )


@router.get("/households", response_model=list[HouseholdOut])
def list_households(db: Session = Depends(get_db)) -> list[HouseholdOut]:
    stmt = select(Household).options(selectinload(Household.members)).order_by(Household.id)
    households = db.scalars(stmt).all()
    tokens = _swiggy_tokens(db)
    return [_household_out(h, tokens) for h in households]


@router.post("/households", response_model=HouseholdOut, status_code=201)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)) -> HouseholdOut:
    household = Household(
        name=payload.name,
        members=[HouseholdMember(name=m.name, preferences=m.preferences) for m in payload.members],
    )
    db.add(household)
    db.commit()
    db.refresh(household)
    return _household_out(household, tokens={})


@router.put("/households/{household_id}", response_model=HouseholdOut)
def update_household(
    household_id: int, payload: HouseholdCreate, db: Session = Depends(get_db)
) -> HouseholdOut:
    """Full replace: `payload.members` becomes the household's entire member
    list (existing rows not present in it are deleted, via the model's
    `cascade="all, delete-orphan"`) -- simpler than diffing against member
    ids, and matches how `create_household` already accepts a flat list."""
    household = db.scalars(
        select(Household).options(selectinload(Household.members)).where(Household.id == household_id)
    ).first()
    if household is None:
        raise HTTPException(404, "Household not found")
    household.name = payload.name
    household.members = [HouseholdMember(name=m.name, preferences=m.preferences) for m in payload.members]
    db.commit()
    db.refresh(household)
    return _household_out(household, _swiggy_tokens(db))


@router.delete("/households/{household_id}/connection", response_model=HouseholdOut)
def disconnect_household(household_id: int, db: Session = Depends(get_db)) -> HouseholdOut:
    """Remove a household's Swiggy connection (deletes its `tokens` row).
    Idempotent -- disconnecting an already-disconnected household just
    returns its (unchanged) status rather than erroring."""
    household = db.scalars(
        select(Household).options(selectinload(Household.members)).where(Household.id == household_id)
    ).first()
    if household is None:
        raise HTTPException(404, "Household not found")
    db.execute(delete(Token).where(Token.household_id == household_id, Token.provider == "swiggy"))
    db.commit()
    return _household_out(household, tokens={})


# -- Dineout ------------------------------------------------------------


@router.get("/dineout/search", response_model=DineoutSearchResult)
async def dineout_search(
    household_id: int, query: str, latitude: float, longitude: float, db: Session = Depends(get_db)
) -> DineoutSearchResult:
    token = _token_for(db, household_id)
    try:
        payload = await search_restaurants(
            token.access_token, query=query, latitude=latitude, longitude=longitude
        )
    except DineoutMCPError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _validate(DineoutSearchResult, payload, "Dineout")


# -- Instamart ------------------------------------------------------------


@router.get("/instamart/addresses", response_model=list[InstamartAddress])
async def instamart_addresses(household_id: int, db: Session = Depends(get_db)) -> list[InstamartAddress]:
    token = _token_for(db, household_id)
    try:
        raw_addresses = await get_addresses(token.access_token)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc
    return [InstamartAddress.model_validate(a) for a in raw_addresses]


@router.get("/instamart/search", response_model=InstamartSearchResult)
async def instamart_search(
    household_id: int, address_id: str, query: str, db: Session = Depends(get_db)
) -> InstamartSearchResult:
    token = _token_for(db, household_id)
    try:
        payload = await search_products(token.access_token, address_id, query)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _validate(InstamartSearchResult, payload, "Instamart")


@router.get("/instamart/cart", response_model=InstamartCart)
async def instamart_cart(household_id: int, db: Session = Depends(get_db)) -> InstamartCart:
    token = _token_for(db, household_id)
    try:
        payload = await get_cart(token.access_token)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _validate(InstamartCart, payload, "Cart")


class CartAddIn(BaseModel):
    household_id: int
    address_id: str
    spin_id: str
    sku_id: str | None = None
    quantity: int = 1


@router.post("/instamart/cart/add", response_model=InstamartCart)
async def instamart_cart_add(payload: CartAddIn, db: Session = Depends(get_db)) -> InstamartCart:
    token = _token_for(db, payload.household_id)
    try:
        cart_payload = await add_to_cart(
            token.access_token, payload.address_id, payload.spin_id, payload.sku_id, payload.quantity
        )
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _validate(InstamartCart, cart_payload, "Cart")


class HouseholdIdIn(BaseModel):
    household_id: int


@router.post("/instamart/cart/clear", response_model=InstamartCart)
async def instamart_cart_clear(payload: HouseholdIdIn, db: Session = Depends(get_db)) -> InstamartCart:
    token = _token_for(db, payload.household_id)
    try:
        await clear_cart(token.access_token)
        cart_payload = await get_cart(token.access_token)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _validate(InstamartCart, cart_payload, "Cart")


# -- Chat (Step 5's Gemini agent) ------------------------------------------


class ChatTurnIn(BaseModel):
    household_id: int
    address_id: str | None = None
    message: str
    history: list[dict] = []


class ChatTurnOut(BaseModel):
    transcript: list[dict]
    history: list[dict]


def _display_transcript(history: list[dict]) -> list[dict]:
    turns = []
    for content in history:
        text = "".join(part.get("text", "") for part in content.get("parts") or [] if part.get("text"))
        if not text:
            continue
        turns.append({"role": "user" if content.get("role") == "user" else "assistant", "text": text})
    return turns


@router.post("/chat", response_model=ChatTurnOut)
async def chat_turn(payload: ChatTurnIn, db: Session = Depends(get_db)) -> ChatTurnOut:
    token = _token_for(db, payload.household_id)
    household = db.scalars(
        select(Household)
        .options(selectinload(Household.members))
        .where(Household.id == payload.household_id)
    ).first()
    member_notes = [(m.name, m.preferences) for m in (household.members if household else []) if m.preferences]
    try:
        new_history = await run_chat_turn(
            payload.history,
            payload.message,
            access_token=token.access_token,
            address_id=payload.address_id,
            household_name=household.name if household else None,
            member_notes=member_notes,
        )
    except ChatError as exc:
        raise HTTPException(502, str(exc)) from exc
    return ChatTurnOut(transcript=_display_transcript(new_history), history=new_history)
