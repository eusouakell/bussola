"""Journey state machine (spec FR-007; plan §4): pure transitions, no ADK."""

import pytest

from bussola_agent.estado import EstadoJornada as E
from bussola_agent.jornada.state_machine import (
    JourneyFacts,
    advance,
    goal_is_complete,
    next_state,
    succeeded_tools_from_sources,
)

DATA_TOOLS = frozenset({"perfil_financeiro", "capacidade_poupanca"})
EVERYTHING = JourneyFacts(
    goal_complete=True,
    succeeded_tools=DATA_TOOLS,
    has_scenarios=True,
    chosen_scenario="acelerado",
)


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        ({"valor_alvo": 60000.0, "prazo_meses": 24}, True),
        ({"valor_alvo": 1, "prazo_meses": 1}, True),
        ({"valor_alvo": 0.01, "prazo_meses": 360}, True),
        ({"valor_alvo": None, "prazo_meses": 24}, False),
        ({"valor_alvo": 60000.0, "prazo_meses": None}, False),
        ({"valor_alvo": 0, "prazo_meses": 24}, False),
        ({"valor_alvo": -5, "prazo_meses": 24}, False),
        ({"valor_alvo": 60000.0, "prazo_meses": 0}, False),
        ({"valor_alvo": 60000.0, "prazo_meses": 361}, False),
        ({"valor_alvo": 60000.0, "prazo_meses": 24.5}, False),
        ({"valor_alvo": True, "prazo_meses": 24}, False),
        ({"valor_alvo": "60000", "prazo_meses": 24}, False),
        (None, False),
        ("objetivo", False),
    ],
)
def test_goal_is_complete(goal: object, expected: bool) -> None:
    assert goal_is_complete(goal) is expected


def test_succeeded_tools_from_sources_reads_tool_names() -> None:
    sources = [
        {"ferramenta": "perfil_financeiro", "tabelas": []},
        {"ferramenta": "capacidade_poupanca"},
        {"tabelas": []},
        "lixo",
        {"ferramenta": 3},
    ]
    assert succeeded_tools_from_sources(sources) == DATA_TOOLS
    assert succeeded_tools_from_sources(None) == frozenset()


@pytest.mark.parametrize(
    ("current", "facts", "expected"),
    [
        (E.OBJETIVO, JourneyFacts(), None),
        (E.OBJETIVO, JourneyFacts(goal_complete=True), E.ENTENDER),
        (E.ENTENDER, JourneyFacts(succeeded_tools=frozenset({"perfil_financeiro"})), None),
        (E.ENTENDER, JourneyFacts(succeeded_tools=DATA_TOOLS), E.ANTECIPAR),
        (E.ANTECIPAR, JourneyFacts(), None),
        (E.ANTECIPAR, JourneyFacts(has_scenarios=True), E.ORIENTAR),
        (E.ORIENTAR, JourneyFacts(has_scenarios=True), None),
        (E.ORIENTAR, JourneyFacts(chosen_scenario="outro"), E.AGIR),
        (E.AGIR, EVERYTHING, None),
        (E.ACOMPANHAR, EVERYTHING, None),
    ],
)
def test_next_state_guards(current: E, facts: JourneyFacts, expected: E | None) -> None:
    assert next_state(current, facts) == expected


def test_advance_is_chained_one_step_per_guard() -> None:
    assert advance(E.OBJETIVO, EVERYTHING) == [E.ENTENDER, E.ANTECIPAR, E.ORIENTAR, E.AGIR]
    facts = JourneyFacts(goal_complete=True, succeeded_tools=DATA_TOOLS)
    assert advance(E.OBJETIVO, facts) == [E.ENTENDER, E.ANTECIPAR]


def test_advance_without_facts_does_not_move() -> None:
    assert advance(E.OBJETIVO, JourneyFacts()) == []
    assert advance(E.ANTECIPAR, JourneyFacts(goal_complete=True)) == []


def test_data_tools_alone_do_not_skip_the_goal() -> None:
    """Consultar dados antes do objetivo não tira a jornada de OBJETIVO."""
    facts = JourneyFacts(succeeded_tools=DATA_TOOLS, has_scenarios=True)
    assert advance(E.OBJETIVO, facts) == []


@pytest.mark.parametrize("owned", [E.AGIR, E.ACOMPANHAR])
def test_states_owned_by_005_006_never_advance(owned: E) -> None:
    assert advance(owned, EVERYTHING) == []


def test_goal_change_restarts_at_understand_and_chains() -> None:
    facts = JourneyFacts(goal_complete=True, succeeded_tools=DATA_TOOLS)
    assert advance(E.ORIENTAR, facts, goal_changed=True) == [E.ENTENDER, E.ANTECIPAR]
    assert advance(E.AGIR, JourneyFacts(goal_complete=True), goal_changed=True) == [E.ENTENDER]


def test_goal_change_is_ignored_in_follow_up_and_early_states() -> None:
    facts = JourneyFacts(goal_complete=True)
    assert advance(E.ACOMPANHAR, facts, goal_changed=True) == []
    assert advance(E.ENTENDER, facts, goal_changed=True) == []
    assert advance(E.OBJETIVO, facts, goal_changed=True) == [E.ENTENDER]


def test_goal_change_needs_a_complete_goal() -> None:
    assert advance(E.ORIENTAR, JourneyFacts(), goal_changed=True) == []
