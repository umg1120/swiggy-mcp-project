from unittest.mock import AsyncMock

import pytest

from app.llm_agent import _build_tools
from app.routers.chat import _display_transcript

# -- _display_transcript --
#
# Gemini's raw history (app/llm_agent.py's module docstring) interleaves
# plain (user, assistant) text turns with tool-call/tool-response turns that
# have no `text` part -- only `function_call`/`function_response`. The chat
# UI should show only the former.

RAW_HISTORY = [
    {"role": "user", "parts": [{"text": "add milk to my cart"}]},
    {"role": "model", "parts": [{"function_call": {"name": "search_instamart_products", "args": {"query": "milk"}}}]},
    {"role": "user", "parts": [{"function_response": {"name": "search_instamart_products", "response": {"result": {}}}}]},
    {"role": "model", "parts": [{"text": "Found Amul Taaza Milk -- added it to your cart."}]},
]


def test_display_transcript_keeps_only_text_turns():
    transcript = _display_transcript(RAW_HISTORY)
    assert transcript == [
        {"role": "user", "text": "add milk to my cart"},
        {"role": "assistant", "text": "Found Amul Taaza Milk -- added it to your cart."},
    ]


def test_display_transcript_empty_for_no_history():
    assert _display_transcript([]) == []


# -- app.llm_agent._build_tools --
#
# The tools Gemini calls are plain closures binding one household's access
# token / selected Instamart address -- the model never supplies those
# itself. Exercise them directly, independent of any real Gemini call.


def _tool(tools: list, name: str):
    return next(t for t in tools if t.__name__ == name)


@pytest.mark.asyncio
async def test_search_instamart_products_requires_an_address():
    tools = _build_tools("token", address_id=None)
    search = _tool(tools, "search_instamart_products")

    with pytest.raises(RuntimeError, match="No Instamart delivery address"):
        await search(query="milk")


@pytest.mark.asyncio
async def test_search_instamart_products_calls_the_real_client(monkeypatch):
    mock_search = AsyncMock(return_value={"products": []})
    monkeypatch.setattr("app.llm_agent.search_products", mock_search)

    tools = _build_tools("a-token", address_id="addr-1")
    search = _tool(tools, "search_instamart_products")

    result = await search(query="milk")

    mock_search.assert_awaited_once_with("a-token", "addr-1", "milk")
    assert result == {"products": []}


@pytest.mark.asyncio
async def test_add_instamart_item_to_cart_requires_an_address():
    tools = _build_tools("token", address_id=None)
    add = _tool(tools, "add_instamart_item_to_cart")

    with pytest.raises(RuntimeError, match="No Instamart delivery address"):
        await add(spin_id="SPIN1")


@pytest.mark.asyncio
async def test_clear_instamart_cart_clears_then_returns_the_cart(monkeypatch):
    mock_clear = AsyncMock(return_value={})
    mock_get_cart = AsyncMock(return_value={"items": [], "cartAbsent": True})
    monkeypatch.setattr("app.llm_agent.clear_cart", mock_clear)
    monkeypatch.setattr("app.llm_agent.get_cart", mock_get_cart)

    tools = _build_tools("a-token", address_id="addr-1")
    clear = _tool(tools, "clear_instamart_cart")

    result = await clear()

    mock_clear.assert_awaited_once_with("a-token")
    mock_get_cart.assert_awaited_once_with("a-token")
    assert result == {"items": [], "cartAbsent": True}


# -- /chat routes --


def test_chat_form_renders(client):
    resp = client.get("/chat")
    assert resp.status_code == 200
    assert "Ask about restaurants or groceries" in resp.text


def test_chat_form_shows_no_households_message(client):
    resp = client.get("/chat")
    assert "create one first" in resp.text


def test_chat_send_disallowed_for_unconnected_household(client):
    create_resp = client.post("/households", json={"name": "Not Connected House"})
    household_id = create_resp.json()["id"]

    resp = client.post("/chat", data={"household_id": household_id, "message": "hi"})
    assert resp.status_code == 400
    assert "isn't connected" in resp.text.lower()
