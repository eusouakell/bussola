"""Local journey tools: ``registrar_objetivo`` and ``escolher_cenario`` (FR-009, FR-010)."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.events import Event
from google.genai import types

from bussola_agent.jornada.tools import (
    MSG_INVALID_TERM,
    MSG_INVALID_VALUE,
    escolher_cenario,
    normalize_scenario_name,
    parse_target_value,
    parse_term_months,
    registrar_objetivo,
)

RAIZ = Path(__file__).resolve().parents[3]
FIXTURES = RAIZ / "contracts" / "fixtures" / "ferramentas"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}__ate_202506.json").read_text(encoding="utf-8"))


def _ctx(state: dict | None = None, events: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        state=state if state is not None else {},
        session=SimpleNamespace(id="s1", events=events or []),
    )


# ---------------------------------------------------------------------------
# registrar_objetivo
# ---------------------------------------------------------------------------


def test_register_partial_goal_lists_what_is_missing() -> None:
    result = registrar_objetivo(
        "imovel", "Primeiro apartamento", prioridade="Alta", tool_context=_ctx()
    )
    assert result == {
        "dados": {
            "objetivo": {
                "tipo": "imovel",
                "descricao": "Primeiro apartamento",
                "valor_alvo": None,
                "prazo_meses": None,
                "prioridade": "alta",
            },
            "faltando": ["valor_alvo", "prazo_meses"],
        },
        "fonte": {"ferramenta": "registrar_objetivo", "tabelas": [], "periodo": None},
        "avisos": [],
    }


def test_register_complete_goal() -> None:
    result = registrar_objetivo("imovel", "Entrada", 60000, 24, tool_context=_ctx())
    goal = result["dados"]["objetivo"]
    assert goal["valor_alvo"] == 60000.0
    assert isinstance(goal["valor_alvo"], float)
    assert goal["prazo_meses"] == 24
    assert result["dados"]["faltando"] == []


def test_partial_input_is_merged_with_the_current_goal() -> None:
    state = {
        "objetivo": {
            "tipo": "imovel",
            "descricao": "Primeiro apartamento",
            "valor_alvo": None,
            "prazo_meses": None,
            "prioridade": "alta",
        }
    }
    result = registrar_objetivo("", "", valor_alvo=30000, prazo_meses=24, tool_context=_ctx(state))
    goal = result["dados"]["objetivo"]
    assert goal == {
        "tipo": "imovel",
        "descricao": "Primeiro apartamento",
        "valor_alvo": 30000.0,
        "prazo_meses": 24,
        "prioridade": "alta",
    }
    assert state["objetivo"]["valor_alvo"] is None  # a ferramenta não grava o state


@pytest.mark.parametrize("value", [0, -1, -0.01, float("nan"), float("inf"), True, "abc"])
def test_invalid_target_value(value: object) -> None:
    result = registrar_objetivo("imovel", "x", valor_alvo=value, prazo_meses=24)  # type: ignore[arg-type]
    assert result == {"erro": {"codigo": "ENTRADA_INVALIDA", "mensagem": MSG_INVALID_VALUE}}


@pytest.mark.parametrize("term", [0, -3, 361, 24.5, True, "dois anos"])
def test_implausible_term(term: object) -> None:
    result = registrar_objetivo("imovel", "x", valor_alvo=1000, prazo_meses=term)  # type: ignore[arg-type]
    assert result == {"erro": {"codigo": "PRAZO_IMPLAUSIVEL", "mensagem": MSG_INVALID_TERM}}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (60000, 60000.0),
        (1234.567, 1234.57),
        ("60000", 60000.0),
        ("60.000", 60000.0),
        ("60.000,50", 60000.5),
        ("R$ 1.250,00", 1250.0),
        ("12.5", 12.5),
    ],
)
def test_parse_target_value(raw: object, expected: float) -> None:
    assert parse_target_value(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [(24, 24), (24.0, 24), ("36", 36), (360, 360)])
def test_parse_term_months(raw: object, expected: int) -> None:
    assert parse_term_months(raw) == expected


def test_texts_are_sanitized_and_capped() -> None:
    result = registrar_objetivo(
        "imovel {id_usuario}",
        "Casa\n{ate_anomes} <b>nova</b> " + "x" * 200,
        tool_context=_ctx(),
    )
    goal = result["dados"]["objetivo"]
    assert "{" not in goal["tipo"] and "{" not in goal["descricao"]
    assert "\n" not in goal["descricao"] and "<" not in goal["descricao"]
    assert len(goal["descricao"]) <= 80


def test_unknown_priority_is_warned_not_stored() -> None:
    result = registrar_objetivo("imovel", "x", prioridade="urgentíssima", tool_context=_ctx())
    assert result["dados"]["objetivo"]["prioridade"] is None
    assert result["avisos"]


def test_goal_change_with_active_plan_is_refused() -> None:
    state = {
        "plano_id": "p1",
        "objetivo": {"tipo": "imovel", "descricao": "x", "valor_alvo": 30000.0, "prazo_meses": 24},
    }
    result = registrar_objetivo("imovel", "x", valor_alvo=50000, tool_context=_ctx(state))
    assert result["erro"]["codigo"] == "ENTRADA_INVALIDA"
    same = registrar_objetivo("imovel", "x", valor_alvo=30000, tool_context=_ctx(state))
    assert "dados" in same


# ---------------------------------------------------------------------------
# escolher_cenario
# ---------------------------------------------------------------------------


def _orient_state(**extra: Any) -> dict[str, Any]:
    return {
        "estado_jornada": "ORIENTAR",
        "cenarios": _fixture("comparar_cenarios")["dados"],
        **extra,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("acelerado", "acelerado"),
        ("Caminho Acelerado", "acelerado"),
        ("o caminho equilibrado", "equilibrado"),
        ("CONSERVADOR!", "conservador"),
        ("Outro caminho", "outro"),
        ("outro", "outro"),
        ("turbo", None),
        (3, None),
    ],
)
def test_normalize_scenario_name(raw: object, expected: str | None) -> None:
    assert normalize_scenario_name(raw) == expected


def test_choose_named_scenario_returns_details_from_the_comparison() -> None:
    result = escolher_cenario("Caminho acelerado", tool_context=_ctx(_orient_state()))
    assert result["dados"] == {
        "cenario": "acelerado",
        "detalhes": {
            "aporte_mensal": 1660.85,
            "prazo_meses": 19,
            "viavel": True,
            "pct_capacidade": 0.8,
        },
    }
    assert result["fonte"]["ferramenta"] == "escolher_cenario"


def test_choose_requires_compared_scenarios() -> None:
    result = escolher_cenario("acelerado", tool_context=_ctx({"estado_jornada": "ORIENTAR"}))
    assert result["erro"]["codigo"] == "ENTRADA_INVALIDA"


@pytest.mark.parametrize("stage", ["OBJETIVO", "ENTENDER", "ANTECIPAR", "ACOMPANHAR", "???"])
def test_choose_only_in_orient_or_act(stage: str) -> None:
    result = escolher_cenario("acelerado", tool_context=_ctx(_orient_state(estado_jornada=stage)))
    assert result["erro"]["codigo"] == "ENTRADA_INVALIDA"


def test_choose_unknown_name() -> None:
    result = escolher_cenario("turbo", tool_context=_ctx(_orient_state()))
    assert result["erro"]["codigo"] == "ENTRADA_INVALIDA"


def test_choose_refused_with_active_plan() -> None:
    result = escolher_cenario("acelerado", tool_context=_ctx(_orient_state(plano_id="p1")))
    assert result["erro"]["codigo"] == "ENTRADA_INVALIDA"


def _simulation_event(response: dict) -> Event:
    part = types.Part(
        function_response=types.FunctionResponse(name="simular_objetivo", response=response)
    )
    return Event(author="bussola", content=types.Content(role="user", parts=[part]))


def test_choose_other_requires_a_successful_simulation() -> None:
    failed = _simulation_event({"erro": {"codigo": "PRAZO_IMPLAUSIVEL", "mensagem": "x"}})
    result = escolher_cenario("outro", tool_context=_ctx(_orient_state(), [failed]))
    assert result["erro"]["codigo"] == "ENTRADA_INVALIDA"

    simulation = _fixture("simular_objetivo")
    mcp = {"content": [], "structuredContent": simulation, "isError": False}
    result = escolher_cenario(
        "outro caminho", tool_context=_ctx(_orient_state(), [failed, _simulation_event(mcp)])
    )
    assert result["dados"] == {
        "cenario": "outro",
        "detalhes": {
            "valor_alvo": 30000.0,
            "aporte_mensal": 1250.0,
            "prazo_meses": 24,
            "viavel": True,
            "modo": "prazo",
        },
    }


def test_choose_without_context() -> None:
    assert escolher_cenario("acelerado")["erro"]["codigo"] == "ENTRADA_INVALIDA"
