"""Progresso do plano (006 §3.3, INFERRED §10). Funções puras.

- acumulado = soma dos ``realizado`` positivos dos meses acompanhados;
- restante = ``max(valor_alvo − acumulado, 0)``;
- meses decorridos = meses do início do plano até o mês avaliado;
- meses restantes = ``max(prazo_meses − decorridos, 0)``;
- percentual = ``acumulado / valor_alvo × 100``.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from bussola_agent.acompanhamento.money import money
from bussola_agent.acompanhamento.periods import months_between


@dataclass(frozen=True)
class Progress:
    accumulated: float
    remaining: float
    percent: float
    months_elapsed: int
    months_remaining: int


def accumulated(realized: Iterable[float]) -> float:
    """Soma dos valores positivos, com 2 casas."""
    return money(sum(value for value in realized if value > 0))


def compute_progress(
    target: float,
    term_months: int,
    start_anomes: int,
    current_anomes: int | None,
    realized: Iterable[float],
) -> Progress:
    """Progresso até ``current_anomes`` (``None``: nenhum mês acompanhado ainda)."""
    if target <= 0:
        raise ValueError("valor_alvo deve ser positivo.")
    total = accumulated(realized)
    elapsed = 0 if current_anomes is None else max(months_between(start_anomes, current_anomes), 0)
    return Progress(
        accumulated=total,
        remaining=money(max(target - total, 0.0)),
        percent=money(total / target * 100),
        months_elapsed=elapsed,
        months_remaining=max(term_months - elapsed, 0),
    )
