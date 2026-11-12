import secrets
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App-wide configuration, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    database_url: str = "sqlite:///./swiggy_mcp.db"

    # Swiggy MCP OAuth (Step 2). Swiggy MCP supports Dynamic Client
    # Registration (RFC 7591), so swiggy_client_id/secret are only needed as
    # an override once Swiggy grants static production credentials -- until
    # then the app self-registers a client on first login and caches it in
    # the oauth_clients table. See app/swiggy_oauth.py.
    swiggy_mcp_base_url: str = "https://mcp.swiggy.com"
    swiggy_oauth_scopes: str = "mcp:tools mcp:resources mcp:prompts"
    swiggy_client_id: str | None = None
    swiggy_client_secret: str | None = None
    swiggy_redirect_uri: str = "http://localhost:8000/auth/callback"

    # Step 5 (chat agent). Gemini picks which Swiggy tool to call from free
    # text -- see app/llm_agent.py. Get a key at https://aistudio.google.com/apikey.
    gemini_api_key: str | None = None
    # gemini-2.5-flash was retired for new API keys after this app was built
    # (confirmed via a real 404 from the live API, recommending this model) --
    # see swiggy-mcp-project-progress memory.
    gemini_model: str = "gemini-3.6-flash"

    # Step 6 (React frontend). Where the SPA lives in dev -- only used to
    # send /auth/callback's full-page redirect back into the app once a
    # Swiggy login completes, since that hop can't be an XHR the SPA
    # intercepts. Not used anywhere else; the SPA talks to this backend's
    # JSON /api/* routes through Vite's dev proxy, same-origin.
    frontend_url: str = "http://localhost:5173"

    # Auth hardening on /api/* (see app/session_auth.py). Single shared
    # operator password -- this app has exactly one operator, not a users
    # table -- distinct from the per-household Swiggy OAuth above, which
    # authenticates the *app* to Swiggy, not a person to this app.
    #
    # Fails closed, not open, when unconfigured: with app_password_hash
    # unset, /auth/session/login always rejects (see routers/session.py),
    # so every /api/* route stays 401 rather than falling back to "open".
    # Generate a hash with:
    #   python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
    app_password_hash: str | None = None

    # Signs the session cookie (itsdangerous) -- NOT given a fixed default
    # on purpose: a hardcoded secret baked into checked-in source would let
    # anyone who reads this file forge a valid session cookie themselves,
    # bypassing the password entirely. If SESSION_SECRET_KEY isn't set, a
    # fresh random one is generated per process start instead -- safe, the
    # only downside is every session is invalidated on a server restart.
    # Set one explicitly for a real deployment. Generate with:
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    session_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))


@lru_cache
def get_settings() -> Settings:
    return Settings()
