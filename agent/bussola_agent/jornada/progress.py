"""Applies a tool result to the journey kept in ``session.state`` (spec FR-008, FR-013).

Single writer of ``objetivo``, ``cenarios``, ``cenario_escolhido`` and
``estado_jornada``. Called by the ``after_tool`` callback of
:mod:`bussola_agent.escopo` after the ``fonte`` has been recorded, so the
facts of :mod:`bussola_agent.jornada.state_machine` already include it.

Every step of the machine writes ``estado_jornada`` and logs
``evento=estado_alterado`` (contratos §9 fields only).
"""

from collections.abc import Mapping, MutableMapping
from typing import Any

from bussola_agent.estado import (
    CHAVE_CENARIO_ESCOLHIDO,
    CHAVE_CENARIOS,
    CHAVE_OBJETIVO,
    CHAVE_ULTIMAS_FONTES,
    EstadoJornada,
    definir_estado_jornada,
    obter_estado_jornada,
)
from bussola_agent.jornada.state_machine import (
    JourneyFacts,
    advance,
    goal_is_complete,
    succeeded_tools_from_sources,
)
from bussola_agent.jornada.tool_results import success_data
from bussola_agent.jornada.tools import CHOOSE_SCENARIO, REGISTER_GOAL, REQUIRED_GOAL_FIELDS
from bussola_agent.logging_json import obter_logger

COMPARE_SCENARIOS = "comparar_cenarios"
EVENT_STATE_CHANGED = "estado_alterado"

_log = obter_logger(__name__)


def facts_from_state(state: Mapping[str, Any]) -> JourneyFacts:
    """Journey facts read from ``session.state``."""
    chosen = state.get(CHAVE_CENARIO_ESCOLHIDO)
    return JourneyFacts(
        goal_complete=goal_is_complete(state.get(CHAVE_OBJETIVO)),
        succeeded_tools=succeeded_tools_from_sources(state.get(CHAVE_ULTIMAS_FONTES)),
        has_scenarios=bool(state.get(CHAVE_CENARIOS)),
        chosen_scenario=chosen if isinstance(chosen, str) and chosen else None,
    )


def goal_changed(previous: object, new: Mapping[str, Any]) -> bool:
    """True when a required field already set in ``previous`` got a different value (D-02)."""
    if not isinstance(previous, Mapping):
        return False
    return any(
        previous.get(field) is not None and new.get(field) != previous.get(field)
        for field in REQUIRED_GOAL_FIELDS
    )


def _record_data(state: MutableMapping[str, Any], tool_name: str, data: Mapping[str, Any]) -> bool:
    """Writes what the successful tool established. Returns ``True`` on a goal change."""
    if tool_name == REGISTER_GOAL:
        goal = data.get("objetivo")
        if not isinstance(goal, Mapping):
            return False
        changed = goal_changed(state.get(CHAVE_OBJETIVO), goal)
        state[CHAVE_OBJETIVO] = dict(goal)
        if changed:
            state[CHAVE_CENARIOS] = None
            state[CHAVE_CENARIO_ESCOLHIDO] = None
        return changed
    if tool_name == COMPARE_SCENARIOS:
        state[CHAVE_CENARIOS] = dict(data)
    elif tool_name == CHOOSE_SCENARIO and isinstance(data.get("cenario"), str):
        state[CHAVE_CENARIO_ESCOLHIDO] = data["cenario"]
    return False


def apply_tool_outcome(
    state: MutableMapping[str, Any],
    tool_name: str,
    response: object,
    *,
    session_id: str | None = None,
) -> list[EstadoJornada]:
    """Records a tool result and advances the machine. Returns the states visited.

    Failed tools write nothing but still re-check the guards (harmless: the
    facts did not change). An unknown ``estado_jornada`` is left untouched.
    """
    data = success_data(response)
    changed = _record_data(state, tool_name, data) if data is not None else False
    try:
        current = obter_estado_jornada(state)
    except ValueError:
        _log.warning(
            "estado_jornada desconhecido; jornada não avançou.",
            extra={"evento": "estado_invalido", "session_id": session_id, "ferramenta": tool_name},
        )
        return []
    visited = advance(current, facts_from_state(state), goal_changed=changed)
    for step in visited:
        definir_estado_jornada(state, step)
        _log.info(
            "Estado da jornada alterado.",
            extra={
                "evento": EVENT_STATE_CHANGED,
                "estado_jornada": step.value,
                "session_id": session_id,
                "ferramenta": tool_name,
            },
        )
    return visited
