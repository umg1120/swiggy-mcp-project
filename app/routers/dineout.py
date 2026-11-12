"""Step 3: one agent, fully wired, hardcoded to Dineout's restaurant search.

No intent router yet -- this endpoint always calls search_restaurants_dineout.
That's deliberate: prove household -> agent -> MCP -> response -> template
works end to end for one path before generalizing to Food/Instamart or a
real /chat router (Steps 4-5).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dineout_client import DineoutMCPError, search_restaurants
from app.models import Household, Token
from app.schemas import DineoutSearchResult

router = APIRouter(prefix="/dineout", tags=["dineout"])
templates = Jinja2Templates(directory="app/templates")


def _connected_household_ids(db: Session) -> set[int]:
    return set(db.scalars(select(Token.household_id).where(Token.provider == "swiggy")).all())


@router.get("/search", response_class=HTMLResponse)
def search_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    households = db.scalars(select(Household).order_by(Household.id)).all()
    return templates.TemplateResponse(
        request,
        "dineout/search.html",
        {"households": households, "connected_ids": _connected_household_ids(db), "results": None},
    )


@router.post("/search", response_class=HTMLResponse)
async def run_search(
    request: Request,
    household_id: int = Form(...),
    query: str = Form(..., min_length=1),
    latitude: float = Form(...),
    longitude: float = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    households = db.scalars(select(Household).order_by(Household.id)).all()
    connected_ids = _connected_household_ids(db)

    token = db.scalars(
        select(Token).where(Token.household_id == household_id, Token.provider == "swiggy")
    ).first()
    if token is None:
        raise HTTPException(400, "That household isn't connected to Swiggy yet -- visit /auth/login first")

    try:
        payload = await search_restaurants(
            token.access_token, query=query, latitude=latitude, longitude=longitude
        )
    except DineoutMCPError as exc:
        raise HTTPException(502, str(exc)) from exc

    try:
        results = DineoutSearchResult.model_validate(payload)
    except ValidationError as exc:
        # The MCP call itself succeeded -- this means the real payload shape
        # doesn't match schemas.DineoutSearchResult. Surface the raw payload
        # alongside the validation error so the mismatch can be fixed exactly,
        # instead of a bare 500 with no detail.
        raise HTTPException(
            502, f"Dineout response didn't match the expected schema: {exc}\nraw payload: {payload!r}"
        ) from exc

    return templates.TemplateResponse(
        request,
        "dineout/search.html",
        {
            "households": households,
            "connected_ids": connected_ids,
            "results": results,
            "query": query,
            "latitude": latitude,
            "longitude": longitude,
            "selected_household_id": household_id,
        },
    )
