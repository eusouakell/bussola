"""Plano ativo e a chave ``acompanhamento_contexto`` do state (contratos §6).

Ordem de resolução do plano ativo (``plano_id`` do state):

1. snapshot em ``acompanhamento_contexto.plano_vigente`` com o mesmo
   ``plano_id`` (plano já acompanhado ou ajustado pelo 006);
2. ``RegistroApp.obter_plano(plano_id)`` (plano gravado pelo 005);
3. derivação do state do 004: ``objetivo.valor_alvo`` + o cenário
   ``cenario_escolhido`` em ``cenarios`` (aporte e prazo). Serve enquanto o
   registro do 005 não estiver ligado ao do 006.

O início do acompanhamento (``inicio_anomes``) é o ``ate_anomes`` da criação
do primeiro plano da linhagem; planos ajustados herdam esse início.
"""

import copy
from collections.abc import Mapping, MutableMapping
from dataclasses import asdict, dataclass
from typing import Any

from bussola_agent.estado import (
    CHAVE_ACOMPANHAMENTO,
    CHAVE_ATE_ANOMES,
    CHAVE_CENARIO_ESCOLHIDO,
    CHAVE_CENARIOS,
    CHAVE_OBJETIVO,
    CHAVE_PLANO_ID,
    anomes_valido,
)
from bussola_agent.persistencia import RegistroApp

CONTEXT_KEY = "acompanhamento_contexto"
DEFAULT_OBJECTIVE = "Objetivo financeiro"


@dataclass(frozen=True)
class ActivePlan:
    plano_id: str
    cenario: str
    valor_alvo: float
    aporte_mensal: float
    prazo_meses: int
    criado_em_anomes: int
    inicio_anomes: int
    objetivo: str

    def public(self) -> dict[str, Any]:
        """Plano no formato do front (``status_plano.dados.plano``)."""
        data = asdict(self)
        data.pop("objetivo")
        return data

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_snapshot(cls, data: Mapping[str, Any]) -> "ActivePlan | None":
        try:
            plan = cls(
                plano_id=str(data["plano_id"]),
                cenario=str(data["cenario"]),
                valor_alvo=float(data["valor_alvo"]),
                aporte_mensal=float(data["aporte_mensal"]),
                prazo_meses=int(data["prazo_meses"]),
                criado_em_anomes=int(data["criado_em_anomes"]),
                inicio_anomes=int(data["inicio_anomes"]),
                objetivo=str(data.get("objetivo") or DEFAULT_OBJECTIVE),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return plan if _plausible(plan) else None


def _plausible(plan: ActivePlan) -> bool:
    return (
        plan.valor_alvo > 0
        and plan.aporte_mensal >= 0
        and 1 <= plan.prazo_meses <= 360
        and anomes_valido(plan.criado_em_anomes)
        and anomes_valido(plan.inicio_anomes)
    )


# ---------------------------------------------------------------------------
# acompanhamento_contexto
# ---------------------------------------------------------------------------


def read_context(state: Mapping[str, Any]) -> dict[str, Any]:
    """Cópia profunda de ``acompanhamento_contexto`` (``{}`` se ausente ou inválido)."""
    value = state.get(CONTEXT_KEY)
    return copy.deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def write_context(state: MutableMapping[str, Any], context: Mapping[str, Any]) -> None:
    """Reatribui a chave (o ``State`` do ADK só registra o delta em ``__setitem__``)."""
    state[CONTEXT_KEY] = copy.deepcopy(dict(context))


def lineage(context: Mapping[str, Any]) -> list[str]:
    planos = context.get("planos")
    return [p for p in planos if isinstance(p, str)] if isinstance(planos, list) else []


def history_for(state: Mapping[str, Any], plan_ids: list[str]) -> list[dict[str, Any]]:
    """Meses de ``acompanhamento`` que pertencem à linhagem ``plan_ids``."""
    items = state.get(CHAVE_ACOMPANHAMENTO)
    if not isinstance(items, list):
        return []
    wanted = set(plan_ids)
    return [dict(i) for i in items if isinstance(i, Mapping) and i.get("plano_id") in wanted]


# ---------------------------------------------------------------------------
# Resolução
# ---------------------------------------------------------------------------


def _objective_text(objetivo: Any) -> str:
    if isinstance(objetivo, Mapping):
        for key in ("descricao", "tipo"):
            value = objetivo.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return DEFAULT_OBJECTIVE


def _chosen_scenario(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    chosen = state.get(CHAVE_CENARIO_ESCOLHIDO)
    cenarios = state.get(CHAVE_CENARIOS)
    if not isinstance(chosen, str) or not isinstance(cenarios, Mapping):
        return None
    items = cenarios.get("cenarios")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, Mapping) and str(item.get("nome", "")).casefold() == chosen.casefold():
            return item
    return None


def _start_for(plan_id: str, context: Mapping[str, Any], created: int) -> int:
    start = context.get("inicio_anomes")
    if plan_id in lineage(context) and anomes_valido(start):
        return int(start)
    return created


def resolve_active_plan(state: Mapping[str, Any], registry: RegistroApp) -> ActivePlan | None:
    """Plano ativo do state, ou ``None`` se não houver ``plano_id`` ou dados suficientes."""
    plan_id = state.get(CHAVE_PLANO_ID)
    if not isinstance(plan_id, str) or not plan_id:
        return None
    context = read_context(state)

    snapshot = context.get("plano_vigente")
    if isinstance(snapshot, Mapping) and snapshot.get("plano_id") == plan_id:
        plan = ActivePlan.from_snapshot(snapshot)
        if plan is not None:
            return plan

    stored = registry.obter_plano(plan_id)
    if stored is not None:
        plan = ActivePlan(
            plano_id=stored.plano_id,
            cenario=stored.cenario,
            valor_alvo=float(stored.valor_alvo),
            aporte_mensal=float(stored.aporte_mensal),
            prazo_meses=int(stored.prazo_meses),
            criado_em_anomes=int(stored.ate_anomes),
            inicio_anomes=_start_for(plan_id, context, int(stored.ate_anomes)),
            objetivo=stored.objetivo or DEFAULT_OBJECTIVE,
        )
        return plan if _plausible(plan) else None

    return _derive_from_state(state, plan_id, context)


def _derive_from_state(
    state: Mapping[str, Any], plan_id: str, context: Mapping[str, Any]
) -> ActivePlan | None:
    objetivo = state.get(CHAVE_OBJETIVO)
    scenario = _chosen_scenario(state)
    created = state.get(CHAVE_ATE_ANOMES)
    if not isinstance(objetivo, Mapping) or scenario is None or not anomes_valido(created):
        return None
    try:
        plan = ActivePlan(
            plano_id=plan_id,
            cenario=str(scenario.get("nome")),
            valor_alvo=float(objetivo["valor_alvo"]),
            aporte_mensal=float(scenario["aporte_mensal"]),
            prazo_meses=int(scenario["prazo_meses"]),
            criado_em_anomes=int(created),
            inicio_anomes=_start_for(plan_id, context, int(created)),
            objetivo=_objective_text(objetivo),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return plan if _plausible(plan) else None
