"""Message annotations for the front (spec FR-016; eventos-agente §2, §5).

``after_model`` order 90 (registered before the quick replies): the final
message of the turn gets ``custom_metadata.bussola``:

- ``tag``: ``acao``, ``recomendacao``, ``simulacao`` or ``diagnostico``, from
  the tools that answered without error in the turn (the furthest step wins);
- ``recomendado``: the viable scenario with the lowest ``pct_capacidade``
  (rule R9 of the front, a selection and not a calculation), only when
  ``comparar_cenarios`` answered in the turn and some scenario is viable.

Keys already set by another callback are kept. The response is changed in
place and the callback returns ``None``.
"""

from collections.abc import Mapping
from typing import Any

from bussola_agent.jornada.number_check import is_final_text
from bussola_agent.jornada.tool_results import tool_outcomes

ORDER = 90
TAG_ACTION = "acao"
TAG_RECOMMENDATION = "recomendacao"
TAG_SIMULATION = "simulacao"
TAG_DIAGNOSIS = "diagnostico"

TAG_BY_TOOL: Mapping[str, str] = {
    "escolher_cenario": TAG_ACTION,
    "comparar_cenarios": TAG_RECOMMENDATION,
    "buscar_contexto_financeiro": TAG_RECOMMENDATION,
    "simular_objetivo": TAG_SIMULATION,
    "perfil_financeiro": TAG_DIAGNOSIS,
    "capacidade_poupanca": TAG_DIAGNOSIS,
    "dividas_e_parcelas": TAG_DIAGNOSIS,
    "oportunidades_corte": TAG_DIAGNOSIS,
    "resumo_mes": TAG_DIAGNOSIS,
}
TAG_PRIORITY: tuple[str, ...] = (TAG_ACTION, TAG_RECOMMENDATION, TAG_SIMULATION, TAG_DIAGNOSIS)


def recommended_scenario(comparison: Any) -> str | None:
    """Name of the viable scenario with the lowest ``pct_capacidade`` (R9), or ``None``.

    ``comparison`` is the ``dados`` of ``comparar_cenarios`` (``{cenarios, regras}``).
    """
    scenarios = comparison.get("cenarios") if isinstance(comparison, Mapping) else None
    viable = [
        s
        for s in scenarios or ()
        if isinstance(s, Mapping)
        and s.get("viavel") is True
        and isinstance(s.get("nome"), str)
        and isinstance(s.get("pct_capacidade"), int | float)
        and not isinstance(s.get("pct_capacidade"), bool)
    ]
    if not viable:
        return None
    return min(viable, key=lambda s: s["pct_capacidade"])["nome"]


def turn_tag(tool_names: set[str]) -> str | None:
    """The furthest step among the tools that answered in the turn."""
    tags = {TAG_BY_TOOL[name] for name in tool_names if name in TAG_BY_TOOL}
    return next((tag for tag in TAG_PRIORITY if tag in tags), None)


def annotate(callback_context: Any, llm_response: Any) -> None:
    """``after_model`` order 90: sets ``tag`` and ``recomendado`` on the final message."""
    if not is_final_text(llm_response):
        return None
    session = getattr(callback_context, "session", None)
    events = list(getattr(session, "events", None) or [])
    outcomes = [
        o for o in tool_outcomes(events, getattr(callback_context, "invocation_id", None)) if o.ok
    ]
    found: dict[str, Any] = {}
    tag = turn_tag({o.name for o in outcomes})
    if tag:
        found["tag"] = tag
    comparisons = [o for o in outcomes if o.name == "comparar_cenarios"]
    if comparisons:
        recommended = recommended_scenario((comparisons[-1].envelope or {}).get("dados"))
        if recommended:
            found["recomendado"] = recommended
    if not found:
        return None
    metadata = dict(llm_response.custom_metadata or {})
    bussola = dict(metadata.get("bussola") or {})
    for key, value in found.items():
        bussola.setdefault(key, value)
    metadata["bussola"] = bussola
    llm_response.custom_metadata = metadata
    return None
