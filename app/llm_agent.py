"""Step 5: chat-driven intent router, using Gemini function calling to pick
between Dineout (restaurant search) and Instamart (grocery search + cart)
instead of a person picking a form by hand.

Uses google-genai's *automatic function calling* (AFC): the tools below are
plain async closures (household access token, and Instamart's selected
address, bound in via `_build_tools` -- the model never sees or chooses
those), and `Chat.send_message` inspects/calls them itself, looping until it
has a final text answer. Confirmed against the installed `google-genai`
2.20.0 source (`chats.py`/`_extra_utils.py`): AFC only activates for plain
callables in `tools` (not `Tool`/`FunctionDeclaration` objects), supports
async functions when called via `client.aio.chats`, wraps a tool's return
value as `{"result": ...}` and an exception as `{"error": str(exc)}` fed
back to the model -- so tool wrappers don't need their own try/except --
and `Chat.get_history()` returns the full transcript (including the
function-call/response turns) as plain `Content` objects.

This app is server-rendered with no server-side session store, so the chat
history round-trips through a hidden form field between requests --
`run_chat_turn` takes/returns it as plain JSON (`list[dict]`), matching
`ContentOrDict`/`Content.model_dump(mode="json")`.
"""

import logging
from typing import Any

# Deliberately no `from __future__ import annotations` here (unlike every
# other module in this app) -- google-genai's automatic function calling
# reads each tool's `inspect.signature(...).annotation` directly (see
# `_extra_utils.convert_argument_from_function`), not via
# `typing.get_type_hints()`. With postponed evaluation on, every annotation
# is a plain string at runtime ('str', 'int', ...) and its arg-conversion
# blows up with "isinstance() arg 2 must be a type, a tuple of types, or a
# union" -- confirmed live, see swiggy-mcp-project-progress memory. Real
# type objects are required, and Python 3.12 (this project's floor) supports
# `dict[str, Any]` / `str | None` natively without the future import.

from google import genai
from google.genai import types

from app.config import get_settings
from app.dineout_client import DineoutMCPError, search_restaurants
from app.instamart_client import (
    InstamartMCPError,
    add_to_cart,
    clear_cart,
    get_cart,
    search_products,
)

settings = get_settings()
logger = logging.getLogger(__name__)

# Matches dineout/search.html's form default -- Bangalore -- used only when
# the model doesn't have (or the user didn't give) a location for Dineout.
DEFAULT_LATITUDE = 12.9716
DEFAULT_LONGITUDE = 77.5946

SYSTEM_INSTRUCTION = """\
You are a household assistant for Swiggy Dineout (restaurant search) and \
Swiggy Instamart (grocery search + cart), acting through the tools \
provided -- never answer from your own knowledge.

Rules:
- Only report restaurant names, product names, prices, or cart contents that \
came back from a tool call. Never invent or guess one.
- To add something to the Instamart cart, first call \
search_instamart_products to find the exact item and its spin_id, then call \
add_instamart_item_to_cart with that spin_id -- never invent a spin_id.
- If a search returns several plausible matches for what the user asked for, \
ask which one they mean instead of guessing.
- Before clearing the cart, confirm with the user first.
- If a tool call fails (e.g. no delivery address selected), explain the \
problem in plain language and say what the user should do (e.g. "pick a \
delivery address above first").
"""


class ChatError(RuntimeError):
    """Raised when the chat turn itself fails to reach Gemini -- distinct
    from a Swiggy tool-call error, which google-genai's AFC already catches
    and feeds back to the model as a `{"error": ...}` function response."""


def _build_system_instruction(
    household_name: str | None, member_notes: list[tuple[str, str]]
) -> str:
    """Append household member preferences (free-text notes set on
    /households, e.g. "vegetarian", "doesn't like spicy food") to the base
    system instruction, so the agent actually reasons about them when
    searching/recommending. Kept as a separate, per-call instruction
    (instead of a fixed module-level constant) because it depends on which
    household is chatting."""
    if not member_notes:
        return SYSTEM_INSTRUCTION
    notes = "\n".join(f"- {name}: {note}" for name, note in member_notes)
    household_label = f'"{household_name}"' if household_name else "This household"
    return (
        f"{SYSTEM_INSTRUCTION}\n"
        f"Household context -- {household_label} has these member preferences. Weigh them "
        "when searching or recommending, but don't recite this list back verbatim unless asked:\n"
        f"{notes}\n"
    )


def _build_tools(access_token: str, address_id: str | None) -> list[Any]:
    """Bind one household's access token (+ selected Instamart address) into
    plain async functions Gemini can call directly. Kept separate from
    `dineout_client`/`instamart_client` (which take those as explicit
    arguments) because the model must never see or choose them itself."""

    async def search_restaurants_dineout(
        query: str, latitude: float = DEFAULT_LATITUDE, longitude: float = DEFAULT_LONGITUDE
    ) -> dict[str, Any]:
        """Search Swiggy Dineout for restaurants to eat at or order dine-in from.

        Args:
          query: Free-text search, e.g. "biryani" or "rooftop cafe".
          latitude: Search location latitude. Only override this if the user
            names a specific place; otherwise leave it at its default.
          longitude: Search location longitude. Only override this if the
            user names a specific place; otherwise leave it at its default.
        """
        try:
            return await search_restaurants(access_token, query=query, latitude=latitude, longitude=longitude)
        except DineoutMCPError as exc:
            raise RuntimeError(str(exc)) from exc

    async def search_instamart_products(query: str) -> dict[str, Any]:
        """Search Swiggy Instamart for grocery/household products.

        Args:
          query: Free-text search, e.g. "milk" or "atta".
        """
        if address_id is None:
            raise RuntimeError(
                "No Instamart delivery address is selected yet -- ask the user to pick one first."
            )
        try:
            return await search_products(access_token, address_id, query)
        except InstamartMCPError as exc:
            raise RuntimeError(str(exc)) from exc

    async def add_instamart_item_to_cart(
        spin_id: str, quantity: int = 1, sku_id: str | None = None
    ) -> dict[str, Any]:
        """Add one Instamart product variation to the household's cart.

        Args:
          spin_id: The variation's `spinId`, taken from a prior
            search_instamart_products result -- never invented.
          quantity: How many units to add.
          sku_id: The variation's `skuId` from that same search result, if it
            had one.
        """
        if address_id is None:
            raise RuntimeError(
                "No Instamart delivery address is selected yet -- ask the user to pick one first."
            )
        try:
            return await add_to_cart(access_token, address_id, spin_id, sku_id, quantity)
        except InstamartMCPError as exc:
            raise RuntimeError(str(exc)) from exc

    async def view_instamart_cart() -> dict[str, Any]:
        """Return the household's current Instamart cart contents and bill total."""
        try:
            return await get_cart(access_token)
        except InstamartMCPError as exc:
            raise RuntimeError(str(exc)) from exc

    async def clear_instamart_cart() -> dict[str, Any]:
        """Empty the household's Instamart cart. Only call this after the user
        has confirmed they want to clear it."""
        try:
            await clear_cart(access_token)
            return await get_cart(access_token)
        except InstamartMCPError as exc:
            raise RuntimeError(str(exc)) from exc

    return [
        search_restaurants_dineout,
        search_instamart_products,
        add_instamart_item_to_cart,
        view_instamart_cart,
        clear_instamart_cart,
    ]


async def run_chat_turn(
    history: list[dict[str, Any]],
    user_message: str,
    *,
    access_token: str,
    address_id: str | None,
    household_name: str | None = None,
    member_notes: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Run one chat turn: send `user_message` (with prior `history`) to
    Gemini, letting it call Dineout/Instamart tools as needed, and return the
    new full history (JSON-plain dicts, for storing in a hidden form field --
    see the module docstring). The assistant's reply is the last entry's
    text; callers that also want it directly can pull it from there.

    `household_name`/`member_notes` (a household's members' free-text
    preferences, e.g. [("Bob", "vegetarian")]) are folded into the system
    instruction when given -- see `_build_system_instruction`."""
    if not settings.gemini_api_key:
        raise ChatError("GEMINI_API_KEY isn't set -- add it to .env to enable the chat agent.")

    client = genai.Client(api_key=settings.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=_build_system_instruction(household_name, member_notes or []),
        tools=_build_tools(access_token, address_id),
    )
    chat = client.aio.chats.create(model=settings.gemini_model, config=config, history=history)

    try:
        await chat.send_message(user_message)
    except Exception as exc:  # noqa: BLE001 -- any Gemini-side failure, surfaced uniformly
        raise ChatError(f"Gemini call failed: {exc}") from exc

    return [content.model_dump(mode="json", exclude_none=True) for content in chat.get_history()]
