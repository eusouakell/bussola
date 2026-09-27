"""Tool result → ``session.state`` journey (FR-008, FR-013; spec D-02, D-03)."""

import json

import pytest
from google.adk.sessions.state import State

from bussola_agent.estado import EstadoJornada as E
from bussola_agent.estado import estado_inicial
from bussola_agent.jornada.progress import apply_tool_outcome, facts_from_state, goal_changed

ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"
PERFIL = {"ferramenta": "perfil_financeiro", "tabelas": [], "periodo": {"inicio": 1, "fim": 2}}
CAPACIDADE = {"ferramenta": "capacidade_poupanca", "tabelas": []}
CENARIOS = {"cenarios": [{"nome": "acelerado", "viavel": True}], "regras": {}}


def _goal(value: float | None = 60000.0, months: int | None = 24) -> dict:
    return {
        "dados": {
            "objetivo": {
                "tipo": "imovel",
                "descricao": "Entrada",
                "valor_alvo": value,
                "prazo_meses": months,
                "prioridade": None,
            },
            "faltando": [],
        },
        "fonte": {"ferramenta": "registrar_objetivo", "tabelas": []},
        "avisos": [],
    }


def _state(**extra: object) -> dict:
    return {**estado_inicial(ANCORA, 202506), **extra}


def _events(capsys: pytest.CaptureFixture[str]) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]


def test_complete_goal_moves_to_understand_and_logs(capsys: pytest.CaptureFixture[str]) -> None:
    state = _state()
    capsys.readouterr()
    visited = apply_tool_outcome(state, "registrar_objetivo", _goal(), session_id="s1")
    assert visited == [E.ENTENDER]
    assert state["estado_jornada"] == "ENTENDER"
    assert state["objetivo"]["valor_alvo"] == 60000.0
    [log] = _events(capsys)
    assert log["evento"] == "estado_alterado"
    assert log["estado_jornada"] == "ENTENDER"
    assert log["ferramenta"] == "registrar_objetivo"
    assert log["session_id"] == "s1"
    assert "60000" not in json.dumps(log)


def test_partial_goal_stays_in_objective() -> None:
    state = _state()
    assert apply_tool_outcome(state, "registrar_objetivo", _goal(value=None)) == []
    assert state["estado_jornada"] == "OBJETIVO"
    assert state["objetivo"]["valor_alvo"] is None


def test_failed_goal_writes_nothing() -> None:
    state = _state()
    error = {"erro": {"codigo": "PRAZO_IMPLAUSIVEL", "mensagem": "x"}}
    assert apply_tool_outcome(state, "registrar_objetivo", error) == []
    assert state["objetivo"] is None


def test_data_tools_move_to_anticipate_only_with_both_sources() -> None:
    state = _state(estado_jornada="ENTENDER", ultimas_fontes=[PERFIL])
    assert apply_tool_outcome(state, "perfil_financeiro", {"dados": {}, "fonte": PERFIL}) == []
    state["ultimas_fontes"] = [PERFIL, CAPACIDADE]
    assert apply_tool_outcome(state, "capacidade_poupanca", {"dados": {}}) == [E.ANTECIPAR]


def test_comparison_saves_scenarios_and_moves_to_orient() -> None:
    state = _state(estado_jornada="ANTECIPAR")
    mcp = {"content": [], "structuredContent": {"dados": CENARIOS, "fonte": {}}, "isError": False}
    assert apply_tool_outcome(state, "comparar_cenarios", mcp) == [E.ORIENTAR]
    assert state["cenarios"] == CENARIOS


def test_failed_comparison_keeps_anticipate() -> None:
    state = _state(estado_jornada="ANTECIPAR")
    error = {"erro": {"codigo": "INDISPONIVEL", "mensagem": "x"}}
    assert apply_tool_outcome(state, "comparar_cenarios", error) == []
    assert state["cenarios"] is None


def test_choice_moves_to_act() -> None:
    state = _state(estado_jornada="ORIENTAR", cenarios=CENARIOS)
    choice = {"dados": {"cenario": "acelerado", "detalhes": {}}}
    assert apply_tool_outcome(state, "escolher_cenario", choice) == [E.AGIR]
    assert state["cenario_escolhido"] == "acelerado"


def test_goal_change_clears_scenarios_and_restarts(capsys: pytest.CaptureFixture[str]) -> None:
    state = _state(
        estado_jornada="AGIR",
        objetivo=_goal()["dados"]["objetivo"],
        cenarios=CENARIOS,
        cenario_escolhido="acelerado",
        ultimas_fontes=[PERFIL, CAPACIDADE],
    )
    capsys.readouterr()
    visited = apply_tool_outcome(state, "registrar_objetivo", _goal(value=80000.0))
    assert visited == [E.ENTENDER, E.ANTECIPAR]
    assert state["cenarios"] is None
    assert state["cenario_escolhido"] is None
    assert [e["estado_jornada"] for e in _events(capsys)] == ["ENTENDER", "ANTECIPAR"]


def test_same_goal_again_keeps_the_journey() -> None:
    state = _state(
        estado_jornada="ORIENTAR", objetivo=_goal()["dados"]["objetivo"], cenarios=CENARIOS
    )
    assert apply_tool_outcome(state, "registrar_objetivo", _goal()) == []
    assert state["cenarios"] == CENARIOS


def test_goal_changed_rules() -> None:
    new = {"valor_alvo": 60000.0, "prazo_meses": 24}
    assert not goal_changed(None, new)
    assert not goal_changed({"valor_alvo": None, "prazo_meses": None}, new)
    assert goal_changed({"valor_alvo": 30000.0, "prazo_meses": 24}, new)
    assert goal_changed({"valor_alvo": 60000.0, "prazo_meses": 12}, new)


def test_unknown_state_is_left_untouched() -> None:
    state = _state(estado_jornada="???")
    assert apply_tool_outcome(state, "registrar_objetivo", _goal()) == []
    assert state["estado_jornada"] == "???"


def test_adk_state_records_the_delta() -> None:
    delta: dict = {}
    state = State(value=_state(), delta=delta)
    apply_tool_outcome(state, "registrar_objetivo", _goal())
    assert delta["estado_jornada"] == "ENTENDER"
    assert delta["objetivo"]["prazo_meses"] == 24


def test_facts_from_state() -> None:
    facts = facts_from_state(
        _state(objetivo=_goal()["dados"]["objetivo"], ultimas_fontes=[PERFIL], cenarios=CENARIOS)
    )
    assert facts.goal_complete and facts.has_scenarios
    assert facts.succeeded_tools == frozenset({"perfil_financeiro"})
    assert facts.chosen_scenario is None
