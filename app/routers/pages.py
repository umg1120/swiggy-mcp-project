from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Household, HouseholdMember

router = APIRouter(prefix="/ui", tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/households", response_class=HTMLResponse)
def households_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    stmt = select(Household).options(selectinload(Household.members)).order_by(Household.id)
    households = db.scalars(stmt).all()
    return templates.TemplateResponse(
        request, "households/list.html", {"households": households}
    )


@router.post("/households")
def create_household_from_form(
    name: str = Form(..., min_length=1, max_length=255),
    member_names: str = Form(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    members = [
        HouseholdMember(name=n.strip())
        for n in member_names.split(",")
        if n.strip()
    ]
    household = Household(name=name.strip(), members=members)
    db.add(household)
    db.commit()
    return RedirectResponse(url="/ui/households", status_code=303)
