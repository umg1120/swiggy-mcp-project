from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers import api, auth, chat, dineout, households, instamart, pages, session
from app.session_auth import require_session

app = FastAPI(title="Swiggy MCP Project")

# Auth hardening: every /api/* route (the React frontend's surface) requires
# a valid session -- see app/session_auth.py. Deliberately NOT applied to
# the Jinja routers below (dineout/instamart/chat/households/pages) or to
# auth.router's Swiggy OAuth flow, which must stay reachable for that
# flow's own redirects regardless.
app.include_router(api.router, dependencies=[Depends(require_session)])
app.include_router(auth.router)
app.include_router(session.router)
app.include_router(dineout.router)
app.include_router(instamart.router)
app.include_router(chat.router)
app.include_router(households.router)
app.include_router(pages.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")
