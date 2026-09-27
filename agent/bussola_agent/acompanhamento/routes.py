"""Rota recalculada (006 §3.3): A = manter o prazo, B = manter o aporte.

Os números vêm de ``simular_objetivo`` (MCP). A resposta só é usada quando
corresponde à entrada (valor restante e prazo, ou valor restante e aporte).
O mock do 000 devolve sempre o golden de 30 mil em 24 meses; nesse caso a
rota aplica :func:`simulate_locally`, que é a mesma regra do golden
(rendimento 0), com a ``capacidade_mensal`` e as ``premissas`` devolvidas
pelo MCP, e acrescenta um aviso. Com o ``simular_objetivo`` real do 003, a
resposta corresponde e a regra local não entra.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from bussola_agent.acompanhamento import envelopes
from bussola_agent.acompanhamento.money import money
from bussola_agent.acompanhamento.ports import McpGateway

ROUTE_KEEP_TERM = "A"
ROUTE_KEEP_CONTRIBUTION = "B"
MAX_TERM_MONTHS = 360
_EPSILON = 0.005

_TITLES = {ROUTE_KEEP_TERM: "Manter o prazo", ROUTE_KEEP_CONTRIBUTION: "Manter o aporte"}
_DESCRIPTIONS = {
    ROUTE_KEEP_TERM: "Aumentar o aporte mensal e manter a data final do plano.",
    ROUTE_KEEP_CONTRIBUTION: "Manter o aporte atual e estender o prazo até a meta.",
}


class ImplausibleTermError(ValueError):
    """Prazo fora de 1–360 meses (``PRAZO_IMPLAUSIVEL``)."""


@dataclass(frozen=True)
class SimulationRequest:
    target: float
    term_months: int | None = None
    contribution: float | None = None

    def __post_init__(self) -> None:
        if (self.term_months is None) == (self.contribution is None):
            raise ValueError("Informe exatamente um entre prazo e aporte.")

    @property
    def mode(self) -> str:
        return "prazo" if self.term_months is not None else "aporte"


def _number(value: Any) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def simulate_locally(
    request: SimulationRequest, capacity: float, premises: Mapping[str, Any]
) -> dict[str, Any]:
    """``dados`` de ``simular_objetivo`` pela regra do golden (rendimento 0).

    - modo prazo: ``aporte = valor / prazo``;
    - modo aporte: ``prazo = ⌈valor / aporte⌉`` (acima de 360 meses levanta
      :class:`ImplausibleTermError`);
    - ``folga = capacidade − aporte`` e ``viavel = aporte ≤ capacidade``.
    """
    if request.target <= 0:
        raise ValueError("valor_alvo deve ser positivo.")
    if request.term_months is not None:
        if not 1 <= request.term_months <= MAX_TERM_MONTHS:
            raise ImplausibleTermError("prazo fora de 1 a 360 meses.")
        term = request.term_months
        contribution = money(request.target / term)
    else:
        contribution = money(request.contribution or 0.0)
        if contribution <= 0:
            raise ValueError("aporte_mensal deve ser positivo.")
        term = math.ceil(money(request.target / contribution))
        if term > MAX_TERM_MONTHS:
            raise ImplausibleTermError("prazo acima de 360 meses.")
    return {
        "modo": request.mode,
        "valor_alvo": money(request.target),
        "aporte_mensal": contribution,
        "prazo_meses": term,
        "viavel": contribution <= capacity,
        "folga_mensal": money(capacity - contribution),
        "premissas": dict(premises),
    }


def response_matches(request: SimulationRequest, dados: Mapping[str, Any]) -> bool:
    """True se a resposta do MCP foi calculada para esta entrada."""
    target = _number(dados.get("valor_alvo"))
    contribution = _number(dados.get("aporte_mensal"))
    term = dados.get("prazo_meses")
    integer_term = isinstance(term, int) and not isinstance(term, bool)
    if target is None or contribution is None or not integer_term:
        return False
    if abs(target - money(request.target)) > _EPSILON:
        return False
    if request.term_months is not None:
        return term == request.term_months
    return abs(contribution - money(request.contribution or 0.0)) <= _EPSILON


async def resolve_simulation(
    gateway: McpGateway, state: Mapping[str, Any], request: SimulationRequest, cut: int
) -> dict[str, Any] | None:
    """Envelope de simulação para ``request``, ou ``None`` se não der para calcular.

    Usa a resposta do MCP quando ela corresponde; senão, a regra local com a
    capacidade do MCP. Respostas com período depois de ``cut`` são descartadas.
    """
    envelope = await gateway.simulate_goal(
        request.target,
        state,
        prazo_meses=request.term_months,
        aporte_mensal=request.contribution,
    )
    if envelopes.error_code(envelope) is not None or not envelopes.within_cut(envelope, cut):
        return None
    dados = envelope["dados"]
    if response_matches(request, dados):
        return {
            "dados": dict(dados),
            "fonte": envelope.get("fonte"),
            "avisos": envelopes.warnings_of(envelope),
        }
    premises = dados.get("premissas")
    capacity = _number(premises.get("capacidade_mensal")) if isinstance(premises, Mapping) else None
    if capacity is None:
        return None
    try:
        local = simulate_locally(request, capacity, premises)  # type: ignore[arg-type]
    except ValueError:
        return None
    return {
        "dados": local,
        "fonte": envelope.get("fonte"),
        "avisos": [*envelopes.warnings_of(envelope), envelopes.WARNING_LOCAL_ROUTE],
    }


async def build_routes(
    gateway: McpGateway,
    state: Mapping[str, Any],
    *,
    remaining: float,
    contribution: float,
    months_remaining: int,
    months_elapsed: int,
    cut: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Rotas A e B para o valor restante, com os avisos das que não saíram.

    - A (manter o prazo): só com meses restantes.
    - B (manter o aporte): só com aporte positivo.
    - Sem valor restante, não há rota.
    - Rotas cujo prazo total passaria de 360 meses ficam de fora.
    """
    if remaining <= 0:
        return [], []
    routes: list[dict[str, Any]] = []
    warnings: list[str] = []

    if months_remaining > 0:
        simulation = await resolve_simulation(
            gateway, state, SimulationRequest(remaining, term_months=months_remaining), cut
        )
        if simulation is None:
            warnings.append(envelopes.warning_route_unavailable(ROUTE_KEEP_TERM))
        else:
            routes.append(
                _route(
                    ROUTE_KEEP_TERM,
                    contribution=money(simulation["dados"]["aporte_mensal"]),
                    term=months_remaining,
                    elapsed=months_elapsed,
                    simulation=simulation,
                )
            )

    if contribution > 0:
        simulation = await resolve_simulation(
            gateway, state, SimulationRequest(remaining, contribution=contribution), cut
        )
        term = simulation["dados"]["prazo_meses"] if simulation is not None else None
        if not isinstance(term, int) or months_elapsed + term > MAX_TERM_MONTHS:
            warnings.append(envelopes.warning_route_unavailable(ROUTE_KEEP_CONTRIBUTION))
        else:
            routes.append(
                _route(
                    ROUTE_KEEP_CONTRIBUTION,
                    contribution=money(contribution),
                    term=term,
                    elapsed=months_elapsed,
                    simulation=simulation,  # type: ignore[arg-type]
                )
            )
    else:
        warnings.append(envelopes.warning_route_unavailable(ROUTE_KEEP_CONTRIBUTION))
    return routes, warnings


def _route(
    route_id: str, *, contribution: float, term: int, elapsed: int, simulation: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": route_id,
        "titulo": _TITLES[route_id],
        "descricao": _DESCRIPTIONS[route_id],
        "aporte_mensal": contribution,
        "prazo_meses": term,
        "prazo_total_meses": elapsed + term,
        "simulacao": simulation,
    }
