"""Async MCP client for Swiggy's Dineout server -- Step 3's one fully-wired agent.

Deliberately narrow: one function, one tool (``search_restaurants_dineout``).
The point of Step 3 is proving the whole loop -- household -> agent -> MCP ->
response -> template -- works end to end for exactly one call before
generalizing to more tools or more agents (Food, Instamart).

Verified against the real server while building this: a session using a
fake bearer token reaches https://mcp.swiggy.com/dineout, completes the
streamable-HTTP handshake, and gets back a distinct protocol-level error
(MCPError -32603) rather than a transport failure -- confirming the wiring
is correct. With a real access token, the call succeeds -- but the live
tool does NOT return the JSON envelope the builders-club docs describe. It
returns an LLM-oriented natural-language summary (a numbered restaurant
list) plus an instruction to call an undocumented `render_restaurants_dineout`
tool next (not even listed among the 12 public Dineout tools -- 404 on its
own doc page). Rather than chase an undocumented tool's schema through more
guesswork, this parses the numbered list directly: it has a stable,
regular structure, confirmed against a real response. If Swiggy's docs
turn out to be right for some other query shape, JSON is still tried first.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings
from app.mcp_utils import describe_mcp_failure, diagnostics, extract_json_payload, first_text_block

settings = get_settings()
logger = logging.getLogger(__name__)

# Matches a line like:
#   1. Zarqash at The Ritz- Carlton Bangalore — Modern Indian, Awadhi | 4.5★ | ₹4000 for two | Ashok Nagar (ID: 1222182)
_LINE_RE = re.compile(
    r"^\d+\.\s+(?P<name>.+?)\s+—\s+(?P<cuisine>.+?)\s+\|\s+(?P<rating>[\d.]+)★\s+\|\s+"
    r"₹(?P<cost>[\d,]+)\s+for two\s+\|\s+(?P<area>.+?)\s+\(ID:\s*(?P<id>\d+)\)\s*$",
    re.MULTILINE,
)
_TOTAL_RE = re.compile(r"Found (\d+) restaurant\(s\) matching")
_NEXT_OFFSET_RE = re.compile(r"call again with offset=(\d+)")


class DineoutMCPError(RuntimeError):
    """Raised when the Dineout MCP server errors, or is unreachable."""


async def search_restaurants(
    access_token: str,
    query: str,
    latitude: float,
    longitude: float,
    limit: int = 10,
) -> dict[str, Any]:
    """Call Dineout's `search_restaurants_dineout` tool.

    Returns a dict shaped like `{"restaurants": [...], "total": int,
    "offset": int, "nextOffset": int | None}` -- callers validate it into
    `schemas.DineoutSearchResult`.
    """
    url = f"{settings.swiggy_mcp_base_url}/dineout"
    arguments = {
        "query": query,
        "latitude": latitude,
        "longitude": longitude,
        "limit": limit,
    }

    try:
        async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {access_token}"}) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool("search_restaurants_dineout", arguments)
    except Exception as exc:  # noqa: BLE001 -- any transport/protocol failure, surfaced uniformly
        raise DineoutMCPError(describe_mcp_failure(exc)) from exc

    logger.debug(
        "search_restaurants_dineout raw result: is_error=%r content=%r structured_content=%r",
        result.is_error,
        result.content,
        result.structured_content,
    )

    if result.is_error:
        raise DineoutMCPError(f"Dineout search failed: {first_text_block(result) or result.content!r}")

    return _extract_payload(result)


def _extract_payload(result: Any) -> dict[str, Any]:
    """Pull a `{"restaurants": [...]}`-shaped dict out of a CallToolResult.

    Tries, in order: the shared JSON extractor (a `content` text block or
    non-empty `structured_content` -- what the docs describe); and finally
    the natural-language numbered-list format the live tool actually
    returns. Raises with full diagnostics if none of those work.
    """
    payload = extract_json_payload(result)
    if payload is not None:
        data = payload.get("data", payload)
        if isinstance(data, dict) and "restaurants" in data:
            return data

    text = first_text_block(result)
    if text is not None:
        parsed_text = _parse_search_text(text)
        if parsed_text["restaurants"] or _TOTAL_RE.search(text):
            return parsed_text

    raise DineoutMCPError(f"Dineout MCP returned nothing parsable as restaurant data: {diagnostics(result)}")


def _parse_search_text(text: str) -> dict[str, Any]:
    """Parse search_restaurants_dineout's natural-language numbered list.

    See module docstring: the live tool returns a summary meant for an LLM
    to read, not JSON. This regex-parses the same fields our schema needs
    straight out of that summary.
    """
    restaurants = [
        {
            "id": m.group("id"),
            "name": m.group("name").strip(),
            "cuisine": [c.strip() for c in m.group("cuisine").split(",")],
            "area": m.group("area").strip(),
            "rating": {"value": m.group("rating")},
            "costForTwo": f"₹{m.group('cost')}",
        }
        for m in _LINE_RE.finditer(text)
    ]

    total_match = _TOTAL_RE.search(text)
    next_offset_match = _NEXT_OFFSET_RE.search(text)

    return {
        "restaurants": restaurants,
        "total": int(total_match.group(1)) if total_match else len(restaurants),
        "offset": 0,
        "nextOffset": int(next_offset_match.group(1)) if next_offset_match else None,
    }
