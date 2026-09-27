"""Rota recalculada: A (manter o prazo) e B (manter o aporte), com o MCP fake (unidade)."""

from typing import Any

import pytest

from bussola_agent.acompanhamento import envelopes
from bussola_agent.acompanhamento.routes import (
    ROUTE_KEEP_CONTRIBUTION,
    ROUTE_KEEP_TERM,
    ImplausibleTermError,
    SimulationRequest,
    build_routes,
    resolve_simulation,
    response_matches,
    simulate_locally,
)
from tests.support.acompanhamento_fakes import ANCHOR_USER_ID, FixtureMcp, FixtureMcpGateway

SCOPE = {"id_usuario": ANCHOR_USER_ID, "ate_anomes": 202507}
PREMISES = {"capacidade_mensal": 1729.0, "rendimento_mensal": 0.0}


async def _routes(mcp: FixtureMcp, **overrides: Any) -> tuple[list[dict[str, Any]], list[str]]:
    kwargs: dict[str, Any] = {
        "remaining": 59115.47,
        "contribution": 2500.0,
        "months_remaining": 23,
        "months_elapsed": 1,
        "cut": 202507,
    }
    kwargs.update(overrides)
    return await build_routes(FixtureMcpGateway(mcp), SCOPE, **kwargs)


async def test_routes_use_the_mcp_answer_when_it_matches_the_request() -> None:
    mcp = FixtureMcp(canned=False)
    routes, warnings = await _routes(mcp)

    assert warnings == []
    route_a, route_b = routes
    assert (route_a["id"], route_a["aporte_mensal"], route_a["prazo_meses"]) == ("A", 2570.24, 23)
    assert route_a["prazo_total_meses"] == 24
    assert (route_b["id"], route_b["aporte_mensal"], route_b["prazo_meses"]) == ("B", 2500.0, 24)
    assert route_b["prazo_total_meses"] == 25
    assert route_a["simulacao"]["dados"]["viavel"] is False
    assert envelopes.WARNING_LOCAL_ROUTE not in route_a["simulacao"]["avisos"]
    # O escopo das chamadas vem do state, e a entrada é o valor restante.
    tool, args = mcp.calls[0]
    assert tool == "simular_objetivo"
    assert args == {
        "valor_alvo": 59115.47,
        "prazo_meses": 23,
        "id_usuario": ANCHOR_USER_ID,
        "ate_anomes": 202507,
    }
    assert mcp.calls[1][1]["aporte_mensal"] == 2500.0


async def test_routes_fall_back_to_the_local_rule_with_the_mcp_capacity() -> None:
    """O mock do 000 devolve sempre o golden de 30 mil em 24 meses."""
    routes, warnings = await _routes(FixtureMcp())

    assert warnings == []
    assert [(r["id"], r["aporte_mensal"], r["prazo_meses"]) for r in routes] == [
        (ROUTE_KEEP_TERM, 2570.24, 23),
        (ROUTE_KEEP_CONTRIBUTION, 2500.0, 24),
    ]
    simulation = routes[0]["simulacao"]
    assert simulation["dados"]["premissas"]["capacidade_mensal"] == 1729.0
    assert simulation["dados"]["folga_mensal"] == -841.24
    assert envelopes.WARNING_LOCAL_ROUTE in simulation["avisos"]
    assert simulation["fonte"]["periodo"]["fim"] <= 202507


async def test_routes_are_skipped_with_a_warning_when_the_mcp_fails() -> None:
    routes, warnings = await _routes(FixtureMcp(fail_tools={"simular_objetivo": "INDISPONIVEL"}))
    assert routes == []
    assert warnings == [
        envelopes.warning_route_unavailable("A"),
        envelopes.warning_route_unavailable("B"),
    ]


async def test_no_routes_when_nothing_remains() -> None:
    mcp = FixtureMcp()
    assert await _routes(mcp, remaining=0.0) == ([], [])
    assert mcp.calls == []


async def test_route_a_needs_months_left_and_route_b_needs_a_contribution() -> None:
    routes, warnings = await _routes(FixtureMcp(), months_remaining=0)
    assert [r["id"] for r in routes] == ["B"]
    assert warnings == []

    routes, warnings = await _routes(FixtureMcp(), contribution=0.0)
    assert [r["id"] for r in routes] == ["A"]
    assert warnings == [envelopes.warning_route_unavailable("B")]


@pytest.mark.parametrize(("contribution", "elapsed"), [(100.0, 1), (200.0, 70)])
async def test_route_b_is_dropped_beyond_360_months(contribution: float, elapsed: int) -> None:
    routes, warnings = await _routes(
        FixtureMcp(), contribution=contribution, months_elapsed=elapsed
    )
    assert [r["id"] for r in routes] == ["A"]
    assert warnings == [envelopes.warning_route_unavailable("B")]


def test_simulate_locally_matches_the_golden_rule() -> None:
    by_term = simulate_locally(SimulationRequest(30000.0, term_months=24), 1729.0, PREMISES)
    assert (by_term["aporte_mensal"], by_term["viavel"], by_term["folga_mensal"]) == (
        1250.0,
        True,
        479.0,
    )
    by_contribution = simulate_locally(
        SimulationRequest(30000.0, contribution=1250.0), 1729.0, PREMISES
    )
    assert (by_contribution["modo"], by_contribution["prazo_meses"]) == ("aporte", 24)


def test_simulate_locally_rejects_implausible_terms() -> None:
    with pytest.raises(ImplausibleTermError):
        simulate_locally(SimulationRequest(1000.0, term_months=361), 1729.0, PREMISES)
    with pytest.raises(ImplausibleTermError):
        simulate_locally(SimulationRequest(1_000_000.0, contribution=10.0), 1729.0, PREMISES)
    with pytest.raises(ValueError):
        SimulationRequest(1000.0)


def test_response_matches_only_the_same_request() -> None:
    golden = {"valor_alvo": 30000.0, "aporte_mensal": 1250.0, "prazo_meses": 24}
    assert response_matches(SimulationRequest(30000.0, term_months=24), golden)
    assert response_matches(SimulationRequest(30000.0, contribution=1250.0), golden)
    assert not response_matches(SimulationRequest(59115.47, term_months=23), golden)
    assert not response_matches(SimulationRequest(30000.0, term_months=12), golden)
    assert not response_matches(SimulationRequest(30000.0, term_months=24), {"valor_alvo": 1})


class _FutureGateway:
    """Devolve uma simulação com período depois do corte (vazamento temporal)."""

    async def monthly_summary(self, anomes: int, state: Any) -> dict[str, Any]:
        raise AssertionError("não usado")

    async def simulate_goal(self, valor_alvo: float, state: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "dados": {"valor_alvo": valor_alvo, "aporte_mensal": 1.0, "prazo_meses": 23},
            "fonte": {"ferramenta": "simular_objetivo", "periodo": {"inicio": 1, "fim": 202512}},
            "avisos": [],
        }


async def test_simulation_after_the_cut_is_discarded() -> None:
    request = SimulationRequest(59115.47, term_months=23)
    assert await resolve_simulation(_FutureGateway(), SCOPE, request, 202507) is None
