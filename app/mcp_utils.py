"""Shared helpers for parsing MCP `CallToolResult` payloads.

Used by every agent client (`dineout_client.py`, `instamart_client.py`, ...).
Extracted after `dineout_client.py` needed several real-call-driven fixes to
get this part right: prefer `content` text blocks over `structured_content`
(which has been observed as an empty `{}`, not `None`, when the server
doesn't populate it), and never assume a tool returns JSON at all -- some
Swiggy MCP tools (see `dineout_client.py::_parse_search_text`) return an
LLM-oriented natural-language summary instead. This module only handles the
JSON case; a tool-specific text fallback belongs in that tool's own client
module, written against a real captured response.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.shared.exceptions import MCPError


def first_text_block(result: Any) -> str | None:
    """Return the first `content` block's text, if any."""
    for block in result.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return None


def extract_json_payload(result: Any) -> dict[str, Any] | None:
    """Return the first JSON object found in a CallToolResult, or None.

    Tries `content`'s first text block (the field the MCP spec guarantees
    is populated) first, then `structured_content` if it's a non-empty
    dict. Returns None -- not an error -- when nothing parses as a JSON
    object, so callers can fall back to a tool-specific text parser.
    """
    text = first_text_block(result)
    if text is not None:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    if isinstance(result.structured_content, dict) and result.structured_content:
        return result.structured_content

    return None


def diagnostics(result: Any) -> str:
    """A compact string dump of a CallToolResult, for error messages."""
    return f"content={result.content!r}; structured_content={result.structured_content!r}"


def unwrap_mcp_exception(exc: BaseException) -> BaseException:
    """Unwrap anyio's `TaskGroup`/`ExceptionGroup` nesting down to the real
    failure underneath.

    `streamable_http_client` (and the session it opens) run their read/write
    loops in anyio task groups, so almost any failure -- including a plain
    `MCPError` from a JSON-RPC error response -- surfaces to callers as an
    opaque, unhelpful "unhandled errors in a TaskGroup (1 sub-exception)",
    often nested two or three `ExceptionGroup`s deep. Confirmed live: an
    expired Swiggy access token produces exactly this, hiding a completely
    diagnosable `MCPError(code=-32603, message='Server returned an error
    response')` underneath. Walk down while there's exactly one exception to
    unwrap; stop (returning the group itself) if a group ever holds more
    than one, since collapsing that would silently drop information."""
    while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        exc = exc.exceptions[0]
    return exc


def describe_mcp_failure(exc: BaseException) -> str:
    """Human-readable message for an exception raised while calling an MCP
    tool, after unwrapping TaskGroup noise (see `unwrap_mcp_exception`).

    Swiggy's MCP gateway collapses transport-level auth failures (e.g. an
    expired access token, confirmed live via a direct HTTP probe returning
    401 `{"error": "invalid_token", "error_description": "JWT has
    expired"}`) into the same generic `MCPError(-32603, "Server returned an
    error response")` it'd give for other server-side failures -- the real
    reason doesn't survive into the MCP protocol layer, so -32603
    specifically gets a hint pointing at the most common real-world cause
    rather than a definitive diagnosis."""
    real = unwrap_mcp_exception(exc)
    if isinstance(real, MCPError):
        hint = (
            " -- this generic code is commonly caused by an expired Swiggy "
            "connection; try reconnecting this household via /auth/login"
            if real.code == -32603
            else ""
        )
        return f"MCP error ({real.code}): {real.message}{hint}"
    return f"MCP call failed: {real}"
