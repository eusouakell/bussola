"""Planejado contra realizado (006 §3.2). Funções puras: sem I/O e sem LLM.

- ``planejado``: ``aporte_mensal`` do plano ativo.
- ``realizado``: ``sobra`` do mês em ``resumo_mes``.
- ``desvio``: ``realizado − planejado``.
- ``status`` com tolerância de 10% do planejado (INFERRED, 006 §10):
  ``desvio`` abaixo da faixa, ``folga`` acima e ``no_plano`` dentro dela
  (limites incluídos).
- ``categoria_desvio``: a macro com o maior aumento positivo contra a linha
  de base (média por macro de 202501 até o início do plano; mês sem dados
  conta 0).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bussola_agent.acompanhamento.money import money

TOLERANCE = 0.10

STATUS_ON_TRACK = "no_plano"
STATUS_DEVIATION = "desvio"
STATUS_SURPLUS = "folga"
STATUSES: tuple[str, ...] = (STATUS_ON_TRACK, STATUS_DEVIATION, STATUS_SURPLUS)


@dataclass(frozen=True)
class DeviationResult:
    planned: float
    actual: float
    deviation: float
    tolerance: float
    status: str

    def as_dict(self) -> dict[str, Any]:
        """Campos com os nomes do contrato (front e tabela ``acompanhamento``)."""
        return {
            "planejado": self.planned,
            "realizado": self.actual,
            "desvio": self.deviation,
            "tolerancia": self.tolerance,
            "status": self.status,
        }


def compute_deviation(
    planned: float, actual: float, tolerance: float = TOLERANCE
) -> DeviationResult:
    """Desvio e status do mês, com valores arredondados para 2 casas."""
    planned_r = money(planned)
    actual_r = money(actual)
    deviation = money(actual_r - planned_r)
    band = money(abs(planned_r) * tolerance)
    if deviation < -band:
        status = STATUS_DEVIATION
    elif deviation > band:
        status = STATUS_SURPLUS
    else:
        status = STATUS_ON_TRACK
    return DeviationResult(planned_r, actual_r, deviation, band, status)


def _macro_totals(gastos_macro: Sequence[Mapping[str, Any]] | None) -> list[tuple[str, float]]:
    totals: list[tuple[str, float]] = []
    for item in gastos_macro or []:
        macro = item.get("macro")
        total = item.get("total")
        numeric = isinstance(total, int | float) and not isinstance(total, bool)
        if isinstance(macro, str) and numeric:
            totals.append((macro, float(total)))
    return totals


def baseline_by_macro(
    monthly_gastos: Sequence[Sequence[Mapping[str, Any]] | None],
) -> dict[str, float]:
    """Média por macro sobre os meses dados (um item por mês; ``None`` = mês sem dados).

    Todos os meses entram no denominador, inclusive os sem dados.
    """
    sums: dict[str, float] = {}
    for gastos in monthly_gastos:
        for macro, total in _macro_totals(gastos):
            sums[macro] = sums.get(macro, 0.0) + total
    months = max(len(monthly_gastos), 1)
    return {macro: money(total / months) for macro, total in sums.items()}


def deviation_category(
    gastos_macro: Sequence[Mapping[str, Any]] | None, baseline: Mapping[str, float]
) -> dict[str, Any] | None:
    """Macro com o maior aumento positivo contra a linha de base, ou ``None``.

    Devolve ``{macro, valor_mes, media_base, aumento}``. Empates ficam com a
    primeira macro na ordem de ``gastos_macro``.
    """
    best: dict[str, Any] | None = None
    highest = 0.0
    for macro, total in _macro_totals(gastos_macro):
        base = money(baseline.get(macro, 0.0))
        increase = money(total - base)
        if increase > highest:
            highest = increase
            best = {
                "macro": macro,
                "valor_mes": money(total),
                "media_base": base,
                "aumento": increase,
            }
    return best
