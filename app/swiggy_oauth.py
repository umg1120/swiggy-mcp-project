"""Swiggy MCP OAuth 2.1 + PKCE client.

Swiggy MCP publishes standard OAuth 2.0 Authorization Server Metadata
(RFC 8414) at ``/.well-known/oauth-authorization-server``, and that metadata
advertises a Dynamic Client Registration (RFC 7591) endpoint. That's the
resolution to Step 2's client_id blocker: rather than emailing Swiggy and
waiting for a manually-issued client_id, the app registers its own client
the first time someone starts a login and caches the result (see
``app.models.OAuthClient``). If SWIGGY_CLIENT_ID/SECRET are later set in
settings -- e.g. once Swiggy grants real production credentials -- those are
used instead and self-registration is skipped entirely.

Reference: https://mcp.swiggy.com/builders/docs/start/authenticate/
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import OAuthClient

settings = get_settings()

DISCOVERY_PATH = "/.well-known/oauth-authorization-server"


class SwiggyOAuthError(RuntimeError):
    """Raised when a call to Swiggy's OAuth server fails or is rejected."""


@dataclass(frozen=True)
class ServerMetadata:
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str


@lru_cache
def get_server_metadata() -> ServerMetadata:
    """Fetch and cache Swiggy MCP's OAuth server metadata.

    Cached for the process lifetime: these endpoints are static, so
    re-fetching on every login would just be wasted latency.
    """
    url = f"{settings.swiggy_mcp_base_url}{DISCOVERY_PATH}"
    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise SwiggyOAuthError(f"Could not fetch Swiggy OAuth metadata: {exc}") from exc

    data = resp.json()
    return ServerMetadata(
        authorization_endpoint=data["authorization_endpoint"],
        token_endpoint=data["token_endpoint"],
        registration_endpoint=data["registration_endpoint"],
    )


def get_or_register_client(db: Session) -> OAuthClient:
    """Return the OAuth client to use for Swiggy logins.

    Prefers a static SWIGGY_CLIENT_ID/SECRET from settings if both are set.
    Otherwise reuses a previously self-registered client for this
    redirect_uri, or registers a new one via Dynamic Client Registration.
    """
    if settings.swiggy_client_id and settings.swiggy_client_secret:
        return OAuthClient(
            provider="swiggy",
            client_id=settings.swiggy_client_id,
            client_secret=settings.swiggy_client_secret,
            redirect_uri=settings.swiggy_redirect_uri,
        )

    existing = db.scalars(
        select(OAuthClient).where(
            OAuthClient.provider == "swiggy",
            OAuthClient.redirect_uri == settings.swiggy_redirect_uri,
        )
    ).first()
    if existing is not None:
        return existing

    registered = _register_dynamic_client()
    client = OAuthClient(
        provider="swiggy",
        client_id=registered["client_id"],
        client_secret=registered.get("client_secret"),
        redirect_uri=settings.swiggy_redirect_uri,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def _register_dynamic_client() -> dict:
    metadata = get_server_metadata()
    body = {
        "client_name": "swiggy-mcp-project (local dev)",
        "redirect_uris": [settings.swiggy_redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_post",
    }
    try:
        resp = httpx.post(metadata.registration_endpoint, json=body, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise SwiggyOAuthError(f"Dynamic client registration failed: {exc}") from exc
    return resp.json()


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) per RFC 7636, S256 method."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_authorize_url(client: OAuthClient, state: str, code_challenge: str) -> str:
    metadata = get_server_metadata()
    params = {
        "response_type": "code",
        "client_id": client.client_id,
        "redirect_uri": client.redirect_uri,
        "scope": settings.swiggy_oauth_scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{metadata.authorization_endpoint}?{urlencode(params)}"


def exchange_code_for_token(client: OAuthClient, code: str, code_verifier: str) -> dict:
    metadata = get_server_metadata()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": client.redirect_uri,
        "client_id": client.client_id,
        "code_verifier": code_verifier,
    }
    if client.client_secret:
        data["client_secret"] = client.client_secret

    try:
        resp = httpx.post(metadata.token_endpoint, data=data, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise SwiggyOAuthError(f"Token exchange failed: {exc}") from exc
    return resp.json()
