"""Plano ativo e ``acompanhamento_contexto``: ordem de resolução (unidade)."""

from bussola_agent.acompanhamento.fakes import ANCHOR_USER_ID, plan_state
from bussola_agent.acompanhamento.plan_context import (
    CONTEXT_KEY,
    ActivePlan,
    history_for,
    read_context,
    resolve_active_plan,
    write_context,
)
from bussola_agent.persistencia import Plano, RegistroEmMemoria


def _snapshot(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "plano_id": "plano-inicial",
        "cenario": "equilibrado",
        "valor_alvo": 60000.0,
        "aporte_mensal": 2570.24,
        "prazo_meses": 24,
        "criado_em_anomes": 202507,
        "inicio_anomes": 202506,
        "objetivo": "Reserva de emergência",
    }
    data.update(overrides)
    return data


def test_no_plan_without_plano_id() -> None:
    assert resolve_active_plan(plan_state(plano_id=None), RegistroEmMemoria()) is None


def test_plan_is_derived_from_the_journey_state() -> None:
    plan = resolve_active_plan(plan_state(), RegistroEmMemoria())
    assert plan == ActivePlan(
        plano_id="plano-inicial",
        cenario="equilibrado",
        valor_alvo=60000.0,
        aporte_mensal=2500.0,
        prazo_meses=24,
        criado_em_anomes=202506,
        inicio_anomes=202506,
        objetivo="Reserva de emergência",
    )
    assert "objetivo" not in plan.public()


def test_chosen_scenario_is_matched_case_insensitively() -> None:
    state = plan_state()
    state["cenario_escolhido"] = "EQUILIBRADO"
    assert resolve_active_plan(state, RegistroEmMemoria()) is not None
    state["cenario_escolhido"] = "acelerado"
    assert resolve_active_plan(state, RegistroEmMemoria()) is None


def test_registry_plan_wins_over_the_journey_state() -> None:
    registry = RegistroEmMemoria()
    stored = Plano(
        session_id="s",
        id_usuario=ANCHOR_USER_ID,
        objetivo="Viagem",
        valor_alvo=12000.0,
        prazo_meses=12,
        cenario="acelerado",
        aporte_mensal=1000.0,
        ate_anomes=202505,
    )
    registry.registrar_plano(stored)
    plan = resolve_active_plan(plan_state(plano_id=stored.plano_id), registry)
    assert plan is not None
    assert (plan.valor_alvo, plan.aporte_mensal, plan.inicio_anomes) == (12000.0, 1000.0, 202505)


def test_snapshot_wins_and_keeps_the_lineage_start() -> None:
    state = plan_state(ate_anomes=202508)
    write_context(state, {"planos": ["plano-inicial"], "plano_vigente": _snapshot()})
    plan = resolve_active_plan(state, RegistroEmMemoria())
    assert plan is not None
    assert (plan.aporte_mensal, plan.inicio_anomes) == (2570.24, 202506)


def test_implausible_snapshot_falls_back_to_the_state() -> None:
    state = plan_state()
    write_context(state, {"plano_vigente": _snapshot(prazo_meses=0)})
    plan = resolve_active_plan(state, RegistroEmMemoria())
    assert plan is not None and plan.aporte_mensal == 2500.0


def test_context_is_copied_on_read_and_reassigned_on_write() -> None:
    state = plan_state()
    write_context(state, {"planos": ["a"]})
    context = read_context(state)
    context["planos"].append("b")
    assert state[CONTEXT_KEY] == {"planos": ["a"]}
    state[CONTEXT_KEY] = "inválido"
    assert read_context(state) == {}


def test_history_keeps_only_the_lineage_months() -> None:
    state = plan_state()
    state["acompanhamento"] = [
        {"plano_id": "outro", "anomes": 202507},
        {"plano_id": "plano-inicial", "anomes": 202507},
        "lixo",
        {"plano_id": "ajustado", "anomes": 202508},
    ]
    months = [h["anomes"] for h in history_for(state, ["plano-inicial", "ajustado"])]
    assert months == [202507, 202508]
