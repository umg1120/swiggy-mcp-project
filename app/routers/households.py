from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Household, HouseholdMember
from app.schemas import HouseholdCreate, HouseholdRead

router = APIRouter(prefix="/households", tags=["households"])


@router.post("", response_model=HouseholdRead, status_code=201)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)) -> Household:
    household = Household(
        name=payload.name,
        members=[HouseholdMember(name=m.name, preferences=m.preferences) for m in payload.members],
    )
    db.add(household)
    db.commit()
    db.refresh(household)
    return household


@router.get("", response_model=list[HouseholdRead])
def list_households(db: Session = Depends(get_db)) -> list[Household]:
    stmt = select(Household).options(selectinload(Household.members)).order_by(Household.id)
    return list(db.scalars(stmt).all())
