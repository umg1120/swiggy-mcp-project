"""Tests for the React frontend's household endpoints (`/api/households*`
in `app/routers/api.py`) -- previously untested despite `/households`
(the plain pydantic router) and `/ui/households` (Jinja) both having
coverage. Focuses on the connect/reconnect/disconnect lifecycle, since
that's the part with actual logic (expiry-awareness, the delete)."""

import datetime

import pytest

from app.config import get_settings
from app.models import Token
from app.session_auth import hash_password


@pytest.fixture()
def client(client, monkeypatch):
    """Overrides conftest's `client` for this module only: every /api/*
    route now requires a session (see app/session_auth.py), so log in
    first rather than touching every test body. Pytest resolves this
    fixture's `client` parameter to conftest's version, not itself --
    a documented, supported override pattern."""
    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("test-password"))
    get_settings.cache_clear()
    resp = client.post("/auth/session/login", json={"password": "test-password"})
    assert resp.status_code == 200
    return client


def _add_token(db_session, household_id: int, *, expires_at=None) -> None:
    db_session.add(
        Token(
            household_id=household_id,
            provider="swiggy",
            access_token="fake-token",
            expires_at=expires_at,
        )
    )
    db_session.commit()


def test_create_household_via_api_is_not_connected(client):
    resp = client.post("/api/households", json={"name": "New House", "members": []})
    assert resp.status_code == 201
    data = resp.json()
    assert data["connected"] is False
    assert data["tokenExpired"] is False


def test_household_with_valid_token_is_connected(client, db_session):
    household_id = client.post("/api/households", json={"name": "Flamingo"}).json()["id"]
    _add_token(
        db_session, household_id, expires_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )

    data = client.get("/api/households").json()[0]
    assert data["connected"] is True
    assert data["tokenExpired"] is False


def test_household_with_expired_token_is_not_connected_but_flagged(client, db_session):
    household_id = client.post("/api/households", json={"name": "Flamingo"}).json()["id"]
    _add_token(
        db_session, household_id, expires_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=1),
    )

    data = client.get("/api/households").json()[0]
    assert data["connected"] is False
    assert data["tokenExpired"] is True


def test_household_with_no_expiry_stored_is_treated_as_connected(client, db_session):
    """No `expires_at` means we can't prove it's expired -- shouldn't
    false-flag a working connection as needing reconnect."""
    household_id = client.post("/api/households", json={"name": "Flamingo"}).json()["id"]
    _add_token(db_session, household_id, expires_at=None)

    data = client.get("/api/households").json()[0]
    assert data["connected"] is True
    assert data["tokenExpired"] is False


def test_disconnect_household_removes_token(client, db_session):
    household_id = client.post("/api/households", json={"name": "Flamingo"}).json()["id"]
    _add_token(
        db_session, household_id, expires_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )
    assert client.get("/api/households").json()[0]["connected"] is True

    resp = client.delete(f"/api/households/{household_id}/connection")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["tokenExpired"] is False  # no token at all -- not "expired"

    # Reflected in a fresh list call too, not just the response of the
    # disconnect call itself.
    assert client.get("/api/households").json()[0]["connected"] is False


def test_disconnect_household_is_idempotent(client):
    household_id = client.post("/api/households", json={"name": "Never Connected"}).json()["id"]

    resp = client.delete(f"/api/households/{household_id}/connection")
    assert resp.status_code == 200
    assert resp.json()["connected"] is False


def test_disconnect_unknown_household_404s(client):
    resp = client.delete("/api/households/999999/connection")
    assert resp.status_code == 404


def test_disconnect_preserves_members(client, db_session):
    household_id = client.post(
        "/api/households", json={"name": "Flamingo", "members": [{"name": "Alice", "preferences": "vegetarian"}]}
    ).json()["id"]
    _add_token(db_session, household_id)

    resp = client.delete(f"/api/households/{household_id}/connection")
    assert resp.json()["members"] == [{"name": "Alice", "preferences": "vegetarian"}]


def test_expired_household_calls_get_a_clear_400_not_a_live_mcp_call(client, db_session):
    """`_token_for` should reject an expired token up front rather than
    letting the request reach the (slow, real) MCP call first."""
    household_id = client.post("/api/households", json={"name": "Flamingo"}).json()["id"]
    _add_token(
        db_session, household_id, expires_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=1),
    )

    resp = client.get(f"/api/instamart/cart?household_id={household_id}")
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"]
