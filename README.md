# Swiggy MCP Project

A small web app for ordering on behalf of a household. Each household
connects its own Swiggy account, and you can:

- search restaurants on **Dineout**
- search groceries and manage the cart on **Instamart**
- chat with a **Gemini** agent that does both, using each member's food preferences

Backend: FastAPI (Python). Frontend: React + Vite.

## Setup

You need [uv](https://docs.astral.sh/uv/) and Node.js.

```bash
uv sync
cp .env.example .env        # then fill in the values (see the comments in the file)
uv run alembic upgrade head

cd frontend && npm install
```

Set an app password: generate a hash, then put it in `.env` as
`APP_PASSWORD_HASH='...'` (keep the single quotes).

```bash
uv run python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"
```

## Run

In two terminals:

```bash
uv run uvicorn app.main:app --reload --port 8000   # backend
cd frontend && npm run dev                          # frontend
```

Open http://localhost:5173 and log in with your password. Then:

1. **Households**: create a household and add its members.
2. **Connect Swiggy**: sign in to Swiggy for that household.
3. Use **Dineout**, **Instamart** or **Chat**.

## Test

```bash
uv run pytest
```

## Share it with peers (optional)

With both servers running:

```bash
cloudflared tunnel --url http://localhost:5173
```

Send the `https://...trycloudflare.com` link it prints. Press Ctrl+C to stop
sharing. Use a strong password first: anyone with the link reaches the login page.
