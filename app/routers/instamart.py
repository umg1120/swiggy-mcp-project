"""Step 4: Instamart agent, following app/routers/dineout.py's pattern.

No intent router yet -- this endpoint always calls search_products. One
extra step versus Dineout: Instamart's search needs a saved delivery
address, so picking a household first fetches that household's addresses
live (`get_addresses`) before a search can run.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.instamart_client import (
    InstamartMCPError,
    add_to_cart,
    clear_cart,
    get_addresses,
    get_cart,
    search_products,
)
from app.models import Household, Token
from app.schemas import InstamartAddress, InstamartCart, InstamartSearchResult

router = APIRouter(prefix="/instamart", tags=["instamart"])
templates = Jinja2Templates(directory="app/templates")


def _connected_household_ids(db: Session) -> set[int]:
    return set(db.scalars(select(Token.household_id).where(Token.provider == "swiggy")).all())


def _token_for(db: Session, household_id: int) -> Token | None:
    return db.scalars(
        select(Token).where(Token.household_id == household_id, Token.provider == "swiggy")
    ).first()


@router.get("/search", response_class=HTMLResponse)
async def search_form(
    request: Request, household_id: int | None = None, db: Session = Depends(get_db)
) -> HTMLResponse:
    households = db.scalars(select(Household).order_by(Household.id)).all()
    context = {
        "households": households,
        "connected_ids": _connected_household_ids(db),
        "selected_household_id": household_id,
        "addresses": None,
        "results": None,
    }

    if household_id is not None:
        token = _token_for(db, household_id)
        if token is None:
            raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")
        try:
            raw_addresses = await get_addresses(token.access_token)
        except InstamartMCPError as exc:
            raise HTTPException(502, str(exc)) from exc
        context["addresses"] = [InstamartAddress.model_validate(a) for a in raw_addresses]

    return templates.TemplateResponse(request, "instamart/search.html", context)


@router.post("/search", response_class=HTMLResponse)
async def run_search(
    request: Request,
    household_id: int = Form(...),
    address_id: str = Form(...),
    query: str = Form(..., min_length=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    households = db.scalars(select(Household).order_by(Household.id)).all()
    connected_ids = _connected_household_ids(db)

    token = _token_for(db, household_id)
    if token is None:
        raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")

    try:
        raw_addresses = await get_addresses(token.access_token)
        payload = await search_products(token.access_token, address_id, query)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc

    addresses = [InstamartAddress.model_validate(a) for a in raw_addresses]

    try:
        results = InstamartSearchResult.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            502, f"Instamart response didn't match the expected schema: {exc}\nraw payload: {payload!r}"
        ) from exc

    return templates.TemplateResponse(
        request,
        "instamart/search.html",
        {
            "households": households,
            "connected_ids": connected_ids,
            "selected_household_id": household_id,
            "addresses": addresses,
            "selected_address_id": address_id,
            "query": query,
            "results": results,
        },
    )


def _validate_cart(payload: dict) -> InstamartCart:
    try:
        return InstamartCart.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            502, f"Cart response didn't match the expected schema: {exc}\nraw payload: {payload!r}"
        ) from exc


@router.get("/cart", response_class=HTMLResponse)
async def view_cart(request: Request, household_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    token = _token_for(db, household_id)
    if token is None:
        raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")

    try:
        payload = await get_cart(token.access_token)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc

    return templates.TemplateResponse(
        request, "instamart/cart.html", {"household_id": household_id, "cart": _validate_cart(payload)}
    )


@router.post("/cart/add", response_class=HTMLResponse)
async def cart_add(
    request: Request,
    household_id: int = Form(...),
    address_id: str = Form(...),
    spin_id: str = Form(...),
    sku_id: str | None = Form(None),
    quantity: int = Form(1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    token = _token_for(db, household_id)
    if token is None:
        raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")

    try:
        payload = await add_to_cart(token.access_token, address_id, spin_id, sku_id, quantity)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc

    return templates.TemplateResponse(
        request, "instamart/cart.html", {"household_id": household_id, "cart": _validate_cart(payload)}
    )


@router.post("/cart/clear", response_class=HTMLResponse)
async def cart_clear(
    request: Request, household_id: int = Form(...), db: Session = Depends(get_db)
) -> HTMLResponse:
    token = _token_for(db, household_id)
    if token is None:
        raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")

    try:
        await clear_cart(token.access_token)
        payload = await get_cart(token.access_token)
    except InstamartMCPError as exc:
        raise HTTPException(502, str(exc)) from exc

    return templates.TemplateResponse(
        request, "instamart/cart.html", {"household_id": household_id, "cart": _validate_cart(payload)}
    )
