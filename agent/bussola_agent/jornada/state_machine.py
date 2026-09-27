"""Deterministic journey state machine (004 §3.3; plan §4).

Pure core: no ADK, no I/O. Transitions depend only on facts produced by tools
(registered goal, successful tools, compared scenarios, chosen scenario),
never on the model's free text.

| From      | To        | Guard                                                  |
|-----------|-----------|--------------------------------------------------------|
| OBJETIVO  | ENTENDER  | goal with valid ``valor_alvo`` and ``prazo_meses``     |
| ENTENDER  | ANTECIPAR | ``perfil_financeiro`` and ``capacidade_poupanca`` ok   |
| ANTECIPAR | ORIENTAR  | ``cenarios`` saved by ``comparar_cenarios``            |
| ORIENTAR  | AGIR      | ``cenario_escolhido`` saved by ``escolher_cenario``    |

Guards are chained, so a single tool result may advance more than one step.
AGIR and ACOMPANHAR belong to cycles 005 and 006: this machine never leaves
them on its own. A changed goal restarts the journey at ENTENDER (spec D-02).
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from bussola_agent.estado import EstadoJornada

DATA_TOOLS_FOR_ANTICIPATE: frozenset[str] = frozenset({"perfil_financeiro", "capacidade_poupanca"})
"""Tools that must have succeeded before ENTENDER → ANTECIPAR."""

SCENARIO_NAMES: tuple[str, ...] = ("conservador", "equilibrado", "acelerado")
OTHER_SCENARIO = "outro"
MAX_TARGET_MONTHS = 360

_OWNED_ELSEWHERE = frozenset({EstadoJornada.AGIR, EstadoJornada.ACOMPANHAR})


@dataclass(frozen=True)
class JourneyFacts:
    """What the tools have established so far in the session."""

    goal_complete: bool = False
    succeeded_tools: frozenset[str] = frozenset()
    has_scenarios: bool = False
    chosen_scenario: str | None = None


def goal_is_complete(goal: object) -> bool:
    """True when ``goal`` has ``valor_alvo > 0`` and an integer ``prazo_meses`` in 1–360."""
    if not isinstance(goal, Mapping):
        return False
    value = goal.get("valor_alvo")
    months = goal.get("prazo_meses")
    value_ok = isinstance(value, int | float) and not isinstance(value, bool) and value > 0
    months_ok = (
        isinstance(months, int)
        and not isinstance(months, bool)
        and 1 <= months <= MAX_TARGET_MONTHS
    )
    return value_ok and months_ok


def succeeded_tools_from_sources(sources: Iterable[Any] | None) -> frozenset[str]:
    """Tool names found in ``ultimas_fontes`` (only successful envelopes carry a ``fonte``)."""
    names = set()
    for source in sources or ():
        if isinstance(source, Mapping) and isinstance(source.get("ferramenta"), str):
            names.add(source["ferramenta"])
    return frozenset(names)


_GUARDS: dict[EstadoJornada, tuple[EstadoJornada, Callable[[JourneyFacts], bool]]] = {
    EstadoJornada.OBJETIVO: (EstadoJornada.ENTENDER, lambda f: f.goal_complete),
    EstadoJornada.ENTENDER: (
        EstadoJornada.ANTECIPAR,
        lambda f: DATA_TOOLS_FOR_ANTICIPATE <= f.succeeded_tools,
    ),
    EstadoJornada.ANTECIPAR: (EstadoJornada.ORIENTAR, lambda f: f.has_scenarios),
    EstadoJornada.ORIENTAR: (EstadoJornada.AGIR, lambda f: f.chosen_scenario is not None),
}


def next_state(current: EstadoJornada, facts: JourneyFacts) -> EstadoJornada | None:
    """The single next state allowed by the facts, or ``None`` to stay."""
    step = _GUARDS.get(current)
    if step is None:
        return None
    target, guard = step
    return target if guard(facts) else None


def advance(
    current: EstadoJornada, facts: JourneyFacts, *, goal_changed: bool = False
) -> list[EstadoJornada]:
    """States visited from ``current`` (excluded), in order. Empty list: no change.

    ``goal_changed`` restarts the journey at ENTENDER when the goal is complete
    and the current state is past it (except ACOMPANHAR, owned by 006).
    """
    visited: list[EstadoJornada] = []
    state = current
    if (
        goal_changed
        and facts.goal_complete
        and state
        not in (
            EstadoJornada.OBJETIVO,
            EstadoJornada.ENTENDER,
            EstadoJornada.ACOMPANHAR,
        )
    ):
        state = EstadoJornada.ENTENDER
        visited.append(state)
    if state in _OWNED_ELSEWHERE:
        return visited
    while (target := next_state(state, facts)) is not None:
        visited.append(target)
        state = target
        if state in _OWNED_ELSEWHERE:
            break
    return visited
