"""``custom_metadata.bussola.tag`` and ``recomendado`` (FR-016; eventos-agente §5)."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.events import Event
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from bussola_agent.jornada.annotations import annotate, recommended_scenario, turn_tag

RAIZ = Path(__file__).resolve().parents[3]
FIXTURES = RAIZ / "contracts" / "fixtures" / "ferramentas"
COMPARISON = json.loads((FIXTURES / "comparar_cenarios__ate_202506.json").read_text("utf-8"))


def _mcp(envelope: dict) -> dict:
    return {"content": [], "structuredContent": envelope, "isError": False}


def _tool_event(name: str, response: dict, invocation: str = "i2") -> Event:
    part = types.Part(function_response=types.FunctionResponse(name=name, response=response))
    return Event(
        author="bussola", invocation_id=invocation, content=types.Content(role="user", parts=[part])
    )


def _ctx(*events: Event) -> SimpleNamespace:
    return SimpleNamespace(session=SimpleNamespace(events=list(events)), invocation_id="i2")


def _answer(**extra: Any) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text="Resposta")]), **extra
    )


def test_recommended_is_the_viable_scenario_with_lowest_capacity_share() -> None:
    assert recommended_scenario(COMPARISON["dados"]) == "acelerado"
    scenarios = {
        "cenarios": [
            {"nome": "conservador", "pct_capacidade": 0.4, "viavel": True},
            {"nome": "equilibrado", "pct_capacidade": 0.6, "viavel": True},
            {"nome": "acelerado", "pct_capacidade": 0.8, "viavel": False},
        ]
    }
    assert recommended_scenario(scenarios) == "conservador"


@pytest.mark.parametrize(
    "comparison",
    [
        {"cenarios": [{"nome": "acelerado", "pct_capacidade": 0.8, "viavel": False}]},
        {"cenarios": [{"nome": "acelerado", "pct_capacidade": True, "viavel": True}]},
        {"cenarios": []},
        None,
        "x",
    ],
)
def test_no_viable_scenario_means_no_recommendation(comparison: Any) -> None:
    assert recommended_scenario(comparison) is None


@pytest.mark.parametrize(
    ("tools", "tag"),
    [
        ({"perfil_financeiro", "capacidade_poupanca"}, "diagnostico"),
        ({"perfil_financeiro", "simular_objetivo"}, "simulacao"),
        ({"capacidade_poupanca", "comparar_cenarios"}, "recomendacao"),
        ({"buscar_contexto_financeiro"}, "recomendacao"),
        ({"comparar_cenarios", "escolher_cenario"}, "acao"),
        ({"registrar_objetivo"}, None),
        (set(), None),
    ],
)
def test_turn_tag(tools: set[str], tag: str | None) -> None:
    assert turn_tag(tools) == tag


def test_comparison_turn_gets_tag_and_recommendation() -> None:
    response = _answer(custom_metadata={"outro": 1})
    context = _ctx(
        _tool_event("perfil_financeiro", _mcp({"dados": {}, "fonte": {}}), "i1"),
        _tool_event("comparar_cenarios", _mcp(COMPARISON)),
    )
    assert annotate(callback_context=context, llm_response=response) is None
    assert response.custom_metadata == {
        "outro": 1,
        "bussola": {"tag": "recomendacao", "recomendado": "acelerado"},
    }


def test_failed_tools_do_not_tag() -> None:
    response = _answer()
    error = _mcp({"erro": {"codigo": "INDISPONIVEL", "mensagem": "x"}})
    annotate(callback_context=_ctx(_tool_event("comparar_cenarios", error)), llm_response=response)
    assert response.custom_metadata is None


def test_keys_from_other_callbacks_are_kept() -> None:
    own = {"bussola": {"tag": "acao", "guardrail": "outro_cliente"}}
    response = _answer(custom_metadata=own)
    annotate(
        callback_context=_ctx(_tool_event("comparar_cenarios", _mcp(COMPARISON))),
        llm_response=response,
    )
    assert response.custom_metadata["bussola"] == {
        "tag": "acao",
        "guardrail": "outro_cliente",
        "recomendado": "acelerado",
    }


def test_only_the_final_message_is_annotated() -> None:
    response = _answer(partial=True)
    annotate(
        callback_context=_ctx(_tool_event("comparar_cenarios", _mcp(COMPARISON))),
        llm_response=response,
    )
    assert response.custom_metadata is None
