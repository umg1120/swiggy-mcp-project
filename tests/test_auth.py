import base64
import hashlib
from urllib.parse import parse_qs, urlparse

from app.models import OAuthClient
from app.swiggy_oauth import generate_pkce_pair


def test_pkce_pair_challenge_matches_verifier():
    verifier, challenge = generate_pkce_pair()

    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected_challenge
    # Both must be unpadded base64url, per RFC 7636.
    assert "=" not in verifier
    assert "=" not in challenge


def test_pkce_pairs_are_unique():
    pair_a = generate_pkce_pair()
    pair_b = generate_pkce_pair()
    assert pair_a != pair_b


def test_login_picker_lists_households(client):
    client.post("/households", json={"name": "Test House"})

    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert 'Connect "Test House"' in resp.text


def test_login_picker_empty_state(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert "create one first" in resp.text


def test_login_start_unknown_household_404s(client):
    resp = client.get("/auth/login/999", follow_redirects=False)
    assert resp.status_code == 404


def test_callback_without_code_or_state_is_400(client):
    resp = client.get("/auth/callback")
    assert resp.status_code == 400


def test_callback_unknown_state_is_400(client):
    resp = client.get("/auth/callback", params={"code": "abc", "state": "not-a-real-state"})
    assert resp.status_code == 400


def test_callback_surfaces_provider_error(client):
    resp = client.get(
        "/auth/callback",
        params={"error": "access_denied", "error_description": "user declined"},
    )
    assert resp.status_code == 400
    assert "user declined" in resp.text


def test_login_start_rejects_unknown_next(client):
    create = client.post("/households", json={"name": "Next Test House"})
    household_id = create.json()["id"]

    resp = client.get(
        f"/auth/login/{household_id}", params={"next": "xml"}, follow_redirects=False
    )
    assert resp.status_code == 400


def test_login_start_react_redirects_callback_to_frontend(client, monkeypatch):
    """`next=react` (the React SPA's connect flow) should send a completed
    login back to FRONTEND_URL instead of rendering auth/success.html --
    the default `next=html` behavior used by the old Jinja2 pages must be
    unaffected (see test_callback_* above, all still `next`-less)."""
    create = client.post("/households", json={"name": "React Connect House"})
    household_id = create.json()["id"]

    fake_client = OAuthClient(
        provider="swiggy",
        client_id="fake-client-id",
        client_secret="fake-secret",
        redirect_uri="http://localhost:8000/auth/callback",
    )
    monkeypatch.setattr("app.routers.auth.get_or_register_client", lambda db: fake_client)

    login_resp = client.get(
        f"/auth/login/{household_id}", params={"next": "react"}, follow_redirects=False
    )
    assert login_resp.status_code in (302, 307)
    state = parse_qs(urlparse(login_resp.headers["location"]).query)["state"][0]

    monkeypatch.setattr(
        "app.routers.auth.exchange_code_for_token",
        lambda client, code, code_verifier: {"access_token": "fake-token", "token_type": "bearer"},
    )

    callback_resp = client.get(
        "/auth/callback", params={"code": "fake-code", "state": state}, follow_redirects=False
    )
    assert callback_resp.status_code in (302, 307)
    assert callback_resp.headers["location"] == (
        f"http://localhost:5173/connect?household_id={household_id}&connected=1"
    )
