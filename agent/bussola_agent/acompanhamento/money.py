"""Valores em BRL como ``float`` com 2 casas (contratos §0).

O arredondamento é *half-up* (metade para longe do zero), o mesmo do
``r2`` do front simulado, calculado em ``Decimal`` para não herdar o erro de
representação do ``float``.
"""

from decimal import ROUND_HALF_UP, Decimal

_CENTAVO = Decimal("0.01")


def money(value: float | int) -> float:
    """``value`` arredondado para 2 casas (half-up), sem ``-0.0``."""
    rounded = float(Decimal(str(value)).quantize(_CENTAVO, rounding=ROUND_HALF_UP))
    return rounded + 0.0


def format_brl(value: float | int) -> str:
    """``R$ 1.234,56`` (pt-BR), para textos montados pela ferramenta."""
    amount = money(value)
    sign = "-" if amount < 0 else ""
    integer, cents = f"{abs(amount):,.2f}".split(".")
    return f"{sign}R$ {integer.replace(',', '.')},{cents}"


def format_months(months: int) -> str:
    """``1 mês`` ou ``N meses``."""
    return "1 mês" if months == 1 else f"{months} meses"
