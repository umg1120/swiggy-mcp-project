"""Tests for auth hardening on /api/* -- see app/session_auth.py and
swiggy-mcp-project-progress memory's "Auth-hardening plan for Phase 0"."""

import pytest

from app.config import get_settings
from app.session_auth import hash_password


@pytest.fixture()
def configured_password(monkeypatch):
    """Configure a real APP_PASSWORD_HASH for "correctpassword", clearing
    the cached Settings() so the new value actually takes effect (get_db,
    session_auth, and routers/session all hold their own `settings =
    get_settings()` module-level references, resolved once)."""
    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("correctpassword"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_api_route_401s_with_no_session(client):
    resp = client.get("/api/households")
    assert resp.status_code == 401


def test_login_with_wrong_password_401s(client, configured_password):
    resp = client.post("/auth/session/login", json={"password": "wrong"})
    assert resp.status_code == 401
    assert client.get("/api/households").status_code == 401


def test_login_when_unconfigured_always_401s(client):
    """No APP_PASSWORD_HASH set at all -- must fail closed, not accept any
    password (e.g. an empty one) as a de-facto open door."""
    resp = client.post("/auth/session/login", json={"password": ""})
    assert resp.status_code == 401


def test_login_with_correct_password_grants_api_access(client, configured_password):
    login_resp = client.post("/auth/session/login", json={"password": "correctpassword"})
    assert login_resp.status_code == 200
    assert login_resp.json() == {"authenticated": True}
    assert "swiggy_mcp_session" in login_resp.cookies

    # The TestClient carries cookies across requests on the same instance.
    assert client.get("/api/households").status_code == 200
    assert client.get("/auth/session/me").status_code == 200


def test_logout_revokes_access(client, configured_password):
    client.post("/auth/session/login", json={"password": "correctpassword"})
    assert client.get("/api/households").status_code == 200

    logout_resp = client.post("/auth/session/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"authenticated": False}

    assert client.get("/api/households").status_code == 401


def test_tampered_cookie_is_rejected(client, configured_password):
    client.post("/auth/session/login", json={"password": "correctpassword"})
    client.cookies.set("swiggy_mcp_session", "not-a-real-signed-token")
    assert client.get("/api/households").status_code == 401


def test_jinja_and_swiggy_oauth_routes_stay_unauthenticated(client):
    """Auth hardening is scoped to /api/* only -- decided with the user:
    the legacy Jinja UI is left open, and the Swiggy OAuth flow can't be
    gated by definition (its /auth/login and /auth/callback redirects
    aren't driven by our own session)."""
    assert client.get("/ui/households").status_code == 200
    assert client.get("/households").status_code == 200
