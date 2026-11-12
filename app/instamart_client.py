"""Async MCP client for Swiggy's Instamart server -- Step 4's second agent,
following `app/dineout_client.py`'s pattern.

Unlike Dineout (raw lat/long), Instamart's `search_products` requires a
saved delivery `addressId` obtained from `get_addresses` first -- so this
module exposes both calls.

Verified against real live calls with a real access token (see
swiggy-mcp-project-progress memory). Unlike Dineout, both tools DO populate
`structured_content` with parseable JSON, so `extract_json_payload`
(app/mcp_utils.py) handles both with no text-parsing fallback needed --
but the shapes still needed fixes versus the builders-club docs:

- `get_addresses`: `structured_content` matches the docs exactly --
  `{"addresses": [...], "total": ..., "pagination": {...}}`.
- `search_products`: the first `content` text block is an LLM-oriented
  display-instructions blurb, not JSON -- `extract_json_payload` correctly
  falls through to `structured_content` for this one. The payload has no
  `data` wrapper (`{"products": [...], "nextOffset": "1"}` directly), and
  each variation's `price` is an object (`{mrp, offerPrice,
  unitLevelPrice}`), not the scalar the docs implied -- see
  `schemas.InstamartPrice`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings
from app.mcp_utils import describe_mcp_failure, diagnostics, extract_json_payload

settings = get_settings()
logger = logging.getLogger(__name__)

INSTAMART_MCP_URL = f"{settings.swiggy_mcp_base_url}/im"


class InstamartMCPError(RuntimeError):
    """Raised when the Instamart MCP server errors, or is unreachable."""


async def _call_tool(access_token: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    try:
        async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {access_token}"}) as http_client:
            async with streamable_http_client(INSTAMART_MCP_URL, http_client=http_client) as (
                read_stream,
                write_stream,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    return await session.call_tool(tool_name, arguments)
    except Exception as exc:  # noqa: BLE001 -- any transport/protocol failure, surfaced uniformly
        raise InstamartMCPError(describe_mcp_failure(exc)) from exc


async def get_addresses(access_token: str) -> list[dict[str, Any]]:
    """Call Instamart's `get_addresses` tool. Returns the raw list of saved addresses."""
    result = await _call_tool(access_token, "get_addresses", {})
    logger.debug("get_addresses raw result: is_error=%r %s", result.is_error, diagnostics(result))

    if result.is_error:
        raise InstamartMCPError(f"get_addresses failed: {diagnostics(result)}")

    payload = extract_json_payload(result)
    if payload is None:
        raise InstamartMCPError(f"get_addresses returned nothing parsable as JSON: {diagnostics(result)}")

    data = payload.get("data", payload)
    addresses = data.get("addresses") if isinstance(data, dict) else None
    if addresses is None:
        raise InstamartMCPError(
            f"get_addresses returned an unrecognized shape (no 'addresses' key): payload={payload!r}"
        )
    return addresses


async def search_products(access_token: str, address_id: str, query: str, offset: int = 0) -> dict[str, Any]:
    """Call Instamart's `search_products` tool. Returns the tool's `data` payload."""
    arguments = {"addressId": address_id, "query": query, "offset": offset}
    result = await _call_tool(access_token, "search_products", arguments)
    logger.debug("search_products raw result: is_error=%r %s", result.is_error, diagnostics(result))

    if result.is_error:
        raise InstamartMCPError(f"search_products failed: {diagnostics(result)}")

    payload = extract_json_payload(result)
    if payload is None:
        raise InstamartMCPError(
            "search_products returned nothing parsable as JSON -- it may return an agentic "
            f"text response like Dineout's search did, needing a text parser: {diagnostics(result)}"
        )

    data = payload.get("data", payload)
    if not isinstance(data, dict) or "products" not in data:
        raise InstamartMCPError(
            f"search_products returned an unrecognized shape (no 'products' key): payload={payload!r}"
        )
    return data


# -- Cart (get_cart / update_cart / clear_cart) --
#
# Verified against real live calls (see swiggy-mcp-project-progress memory):
# add one item via update_cart, inspect it via get_cart, then clear_cart back
# to empty. Both get_cart's and update_cart's response are the same "cart"
# shape with no `data` wrapper -- unlike search_products, item prices here
# are plain scalars (`mrp`, `discountedFinalPrice`), not `InstamartPrice`.
# An empty cart is `{"cartTotalAmount": "0", "items": [], "billBreakdown":
# {...}, "cartAbsent": true}`.


# What an empty cart looks like on the wire (see the comment above).
EMPTY_CART: dict[str, Any] = {
    "cartTotalAmount": "0",
    "items": [],
    "billBreakdown": {"lineItems": [], "toPay": None},
    "cartAbsent": True,
}

# `get_cart` takes no arguments: Swiggy keeps the cart's delivery address
# server-side, and it's only set by `update_cart(selectedAddressId=...)`.
# Until that has happened, `get_cart` errors with this message even when the
# account has saved addresses (verified live: 9 addresses, still this error)
# -- it really means "no cart yet", so it's treated as an empty cart.
NO_CART_ADDRESS_MESSAGE = "no delivery addresses found"


def _is_no_cart_address_error(result: Any) -> bool:
    structured = result.structured_content
    if isinstance(structured, dict):
        error = structured.get("error")
        message = error.get("message", "") if isinstance(error, dict) else ""
        if NO_CART_ADDRESS_MESSAGE in str(message).lower():
            return True
    return any(
        NO_CART_ADDRESS_MESSAGE in (getattr(block, "text", "") or "").lower() for block in result.content or []
    )


async def get_cart(access_token: str) -> dict[str, Any]:
    """Call Instamart's `get_cart` tool. Returns the raw cart payload, or
    `EMPTY_CART` when Swiggy has no cart address selected yet."""
    result = await _call_tool(access_token, "get_cart", {})
    logger.debug("get_cart raw result: is_error=%r %s", result.is_error, diagnostics(result))

    if _is_no_cart_address_error(result):
        return dict(EMPTY_CART, items=[])
    if result.is_error:
        raise InstamartMCPError(f"get_cart failed: {diagnostics(result)}")

    payload = extract_json_payload(result)
    if payload is None:
        raise InstamartMCPError(f"get_cart returned nothing parsable as JSON: {diagnostics(result)}")
    return payload


async def update_cart(access_token: str, address_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Call Instamart's `update_cart` tool. `items` REPLACES the entire cart --
    callers that want to add one item to an existing cart should merge first
    (see `add_to_cart`). Each item needs `spinId` (+ `quantity`, optional
    `skuId`). Returns the raw cart payload."""
    arguments = {"selectedAddressId": address_id, "items": items}
    result = await _call_tool(access_token, "update_cart", arguments)
    logger.debug("update_cart raw result: is_error=%r %s", result.is_error, diagnostics(result))

    if result.is_error:
        raise InstamartMCPError(f"update_cart failed: {diagnostics(result)}")

    payload = extract_json_payload(result)
    if payload is None:
        raise InstamartMCPError(f"update_cart returned nothing parsable as JSON: {diagnostics(result)}")
    return payload


async def clear_cart(access_token: str) -> dict[str, Any]:
    """Call Instamart's `clear_cart` tool. Returns the raw (small) confirmation payload."""
    result = await _call_tool(access_token, "clear_cart", {})
    logger.debug("clear_cart raw result: is_error=%r %s", result.is_error, diagnostics(result))

    if result.is_error:
        raise InstamartMCPError(f"clear_cart failed: {diagnostics(result)}")

    payload = extract_json_payload(result)
    if payload is None:
        raise InstamartMCPError(f"clear_cart returned nothing parsable as JSON: {diagnostics(result)}")
    return payload


async def add_to_cart(
    access_token: str, address_id: str, spin_id: str, sku_id: str | None = None, quantity: int = 1
) -> dict[str, Any]:
    """Add `quantity` of one item to the existing cart (or bump its quantity if
    already present), without disturbing the rest of the cart. `update_cart`
    itself replaces the whole cart, so this reads the current cart first and
    merges."""
    cart = await get_cart(access_token)
    existing_items = cart.get("items", [])

    items_payload = []
    matched_quantity = quantity
    for item in existing_items:
        if item.get("spinId") == spin_id:
            matched_quantity += item.get("quantity", 0)
            continue
        entry = {"spinId": item["spinId"], "quantity": item.get("quantity", 1)}
        if item.get("skuId"):
            entry["skuId"] = item["skuId"]
        items_payload.append(entry)

    new_entry: dict[str, Any] = {"spinId": spin_id, "quantity": matched_quantity}
    if sku_id:
        new_entry["skuId"] = sku_id
    items_payload.append(new_entry)

    return await update_cart(access_token, address_id, items_payload)
