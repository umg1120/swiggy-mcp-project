from __future__ import annotations

import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    members: Mapped[list["HouseholdMember"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
    plans: Mapped[list["Plan"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
    tokens: Mapped[list["Token"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )


class HouseholdMember(Base):
    __tablename__ = "household_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Free-text notes ("vegetarian", "doesn't like spicy food") fed into the
    # Gemini chat agent's system instructions -- see
    # llm_agent._build_household_context. Optional; purely descriptive.
    preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    household: Mapped["Household"] = relationship(back_populates="members")


class Plan(Base):
    """A result produced by one of the agents (Dineout / Instamart / Food).

    Not used until Step 3+, but the table is created now alongside the rest
    of the schema so migrations don't need to revisit this model later.
    """

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # dineout | instamart | food
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    household: Mapped["Household"] = relationship(back_populates="plans")


class Token(Base):
    """OAuth token for a household's connection to Swiggy. Populated in Step 2."""

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="swiggy")
    access_token: Mapped[str] = mapped_column(String(2048), nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_type: Mapped[str] = mapped_column(String(50), nullable=False, default="bearer")
    expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    household: Mapped["Household"] = relationship(back_populates="tokens")


class OAuthClient(Base):
    """A registered OAuth client for a provider.

    Populated in Step 2 via Dynamic Client Registration (RFC 7591) against
    Swiggy MCP's advertised registration_endpoint, so the app never has to
    wait on a manually-issued client_id -- see app/swiggy_oauth.py. If
    SWIGGY_CLIENT_ID/SECRET are set in settings (e.g. once Swiggy grants
    production credentials), those are used instead and this table is
    bypassed entirely.
    """

    __tablename__ = "oauth_clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="swiggy")
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
