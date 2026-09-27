"""Envelope extraction from the shapes the ADK and ``McpTool`` hand over."""

import json

import pytest
from google.adk.events import Event
from google.genai import types

from bussola_agent.jornada.tool_results import (
    error_code,
    extract_envelope,
    succeeded,
    success_data,
    tool_outcomes,
    user_texts,
)

OK = {"dados": {"x": 1}, "fonte": {"ferramenta": "perfil_financeiro"}, "avisos": []}
ERR = {"erro": {"codigo": "DADOS_INSUFICIENTES", "mensagem": "poucos meses"}}


def _mcp(envelope: dict, *, is_error: bool = False, structured: bool = True) -> dict:
    result: dict = {
        "content": [{"type": "text", "text": json.dumps(envelope)}],
        "isError": is_error,
    }
    if structured:
        result["structuredContent"] = envelope
    return result


@pytest.mark.parametrize(
    "response",
    [
        OK,
        _mcp(OK),
        _mcp(OK, structured=False),
        {"result": OK},
        {"structuredContent": {"result": OK}},
    ],
)
def test_success_shapes(response: dict) -> None:
    assert extract_envelope(response) == OK
    assert succeeded(response)
    assert success_data(response) == {"x": 1}
    assert error_code(response) is None


@pytest.mark.parametrize("response", [ERR, _mcp(ERR), {"result": ERR}])
def test_error_shapes(response: dict) -> None:
    assert not succeeded(response)
    assert success_data(response) is None
    assert error_code(response) == "DADOS_INSUFICIENTES"


@pytest.mark.parametrize(
    "response",
    [
        _mcp(OK, is_error=True),
        {"content": [{"type": "text", "text": "Traceback: boom"}], "isError": True},
        {"content": [{"type": "text", "text": "não é json"}]},
        {"qualquer": "coisa"},
        None,
        "texto",
        [OK],
    ],
)
def test_outside_contract_is_failure(response: object) -> None:
    assert not succeeded(response)
    assert success_data(response) is None


def _response_event(name: str, response: dict, invocation: str) -> Event:
    part = types.Part(function_response=types.FunctionResponse(name=name, response=response))
    return Event(
        author="bussola",
        invocation_id=invocation,
        content=types.Content(role="user", parts=[part]),
    )


def test_tool_outcomes_filters_by_invocation() -> None:
    events = [
        Event(
            author="user",
            invocation_id="i1",
            content=types.Content(role="user", parts=[types.Part(text="Oi")]),
        ),
        _response_event("perfil_financeiro", _mcp(OK), "i1"),
        _response_event("capacidade_poupanca", _mcp(ERR), "i2"),
    ]
    assert [(o.name, o.ok) for o in tool_outcomes(events)] == [
        ("perfil_financeiro", True),
        ("capacidade_poupanca", False),
    ]
    [only] = tool_outcomes(events, invocation_id="i2")
    assert only.name == "capacidade_poupanca"
    assert only.envelope == ERR
    assert user_texts(events) == ["Oi"]
