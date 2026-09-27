"""Reads the contract envelope (contratos §5) out of the shapes the ADK hands over.

A tool result may arrive as:

- the envelope itself (local tools: ``{dados, fonte, avisos}`` or ``{erro}``);
- an ``McpTool`` result: ``{content: [{type: "text", text: json}],
  structuredContent: envelope, isError: bool}``;
- a wrapper ``{"result": envelope}`` (FastMCP structured output or the ADK
  normalization of non-dict returns).
"""

import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any


def is_envelope(value: object) -> bool:
    return isinstance(value, Mapping) and ("dados" in value or "erro" in value)


def _mcp_error(value: Mapping[str, Any]) -> bool:
    return value.get("isError") is True or value.get("is_error") is True


def extract_envelope(response: object) -> dict[str, Any] | None:
    """Envelope §5 found in ``response``, or ``None`` when outside the contract.

    An MCP protocol error (``isError``) without an envelope yields ``None``.
    """
    if not isinstance(response, Mapping):
        return None
    if is_envelope(response):
        return dict(response)
    for key in ("structuredContent", "structured_content", "result"):
        inner = response.get(key)
        if is_envelope(inner):
            return dict(inner)
        if isinstance(inner, Mapping) and is_envelope(inner.get("result")):
            return dict(inner["result"])
    content = response.get("content")
    for part in content if isinstance(content, list) else ():
        if isinstance(part, Mapping) and part.get("type") == "text":
            try:
                value = json.loads(part.get("text") or "")
            except (TypeError, ValueError):
                continue
            if is_envelope(value):
                return dict(value)
    return None


def succeeded(response: object) -> bool:
    """True for a success envelope (``dados`` without ``erro``) and no MCP ``isError``."""
    if isinstance(response, Mapping) and _mcp_error(response):
        return False
    envelope = extract_envelope(response)
    return envelope is not None and "erro" not in envelope and "dados" in envelope


def success_data(response: object) -> dict[str, Any] | None:
    """``dados`` of a success envelope, else ``None``."""
    if not succeeded(response):
        return None
    envelope = extract_envelope(response) or {}
    data = envelope.get("dados")
    return dict(data) if isinstance(data, Mapping) else None


def error_code(response: object) -> str | None:
    envelope = extract_envelope(response)
    error = envelope.get("erro") if envelope else None
    code = error.get("codigo") if isinstance(error, Mapping) else None
    return code if isinstance(code, str) else None


@dataclass(frozen=True)
class ToolOutcome:
    """One function response found in the session events."""

    name: str
    response: Any
    invocation_id: str | None

    @property
    def ok(self) -> bool:
        return succeeded(self.response)

    @property
    def envelope(self) -> dict[str, Any] | None:
        return extract_envelope(self.response)


def _parts(event: Any) -> list[Any]:
    content = getattr(event, "content", None)
    return list(getattr(content, "parts", None) or [])


def tool_outcomes(events: Iterable[Any], invocation_id: str | None = None) -> Iterator[ToolOutcome]:
    """Function responses in ``events``; only the given invocation when ``invocation_id`` is set."""
    for event in events or ():
        event_invocation = getattr(event, "invocation_id", None)
        if invocation_id is not None and event_invocation != invocation_id:
            continue
        for part in _parts(event):
            response = getattr(part, "function_response", None)
            if response is not None and response.name:
                yield ToolOutcome(response.name, response.response, event_invocation)


def user_texts(events: Iterable[Any]) -> list[str]:
    """Texts written by the client in the session."""
    texts: list[str] = []
    for event in events or ():
        if getattr(event, "author", None) != "user":
            continue
        texts.extend(p.text for p in _parts(event) if getattr(p, "text", None))
    return texts
