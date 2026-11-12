"""Tests for `app.mcp_utils`'s TaskGroup-unwrapping error helpers.

Regression coverage for a real bug: an expired Swiggy access token made
`instamart_client`/`dineout_client` raise an opaque "unhandled errors in a
TaskGroup (1 sub-exception)" instead of anything actionable -- confirmed
live (see swiggy-mcp-project-progress memory) that the real cause,
`MCPError(code=-32603, message='Server returned an error response')`, was
buried two `ExceptionGroup`s deep.
"""

from mcp.shared.exceptions import MCPError

from app.mcp_utils import describe_mcp_failure, unwrap_mcp_exception


def _mcp_error(code: int, message: str) -> MCPError:
    return MCPError(code=code, message=message)


def test_unwrap_mcp_exception_passes_through_plain_exception():
    exc = ValueError("boom")
    assert unwrap_mcp_exception(exc) is exc


def test_unwrap_mcp_exception_unwraps_nested_single_member_groups():
    inner = _mcp_error(-32603, "Server returned an error response")
    wrapped = ExceptionGroup("unhandled errors in a TaskGroup (1 sub-exception)", [inner])
    double_wrapped = ExceptionGroup("unhandled errors in a TaskGroup (1 sub-exception)", [wrapped])

    assert unwrap_mcp_exception(double_wrapped) is inner


def test_unwrap_mcp_exception_stops_at_a_real_multi_member_group():
    a, b = ValueError("a"), ValueError("b")
    group = ExceptionGroup("two failures", [a, b])
    assert unwrap_mcp_exception(group) is group


def test_describe_mcp_failure_unwraps_and_hints_at_expired_token_for_dash32603():
    inner = _mcp_error(-32603, "Server returned an error response")
    wrapped = ExceptionGroup("unhandled errors in a TaskGroup (1 sub-exception)", [inner])

    message = describe_mcp_failure(wrapped)

    assert "MCP error (-32603)" in message
    assert "Server returned an error response" in message
    assert "expired" in message
    assert "/auth/login" in message


def test_describe_mcp_failure_no_hint_for_other_mcp_error_codes():
    message = describe_mcp_failure(_mcp_error(-32601, "Method not found"))
    assert message == "MCP error (-32601): Method not found"
    assert "expired" not in message


def test_describe_mcp_failure_falls_back_for_non_mcp_exceptions():
    assert describe_mcp_failure(ConnectionError("refused")) == "MCP call failed: refused"
