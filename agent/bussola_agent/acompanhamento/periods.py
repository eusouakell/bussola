"""Aritmética de ``anomes`` (``AAAAMM``), sem I/O."""


def next_month(anomes: int) -> int:
    """Mês seguinte a ``anomes``, com virada de ano (202512 → 202601)."""
    year, month = divmod(anomes, 100)
    if not 1 <= month <= 12:
        raise ValueError("anomes deve estar no formato AAAAMM.")
    return (year + 1) * 100 + 1 if month == 12 else anomes + 1


def months_between(start: int, end: int) -> int:
    """Meses de ``start`` até ``end`` (``end`` − ``start``; 202506 → 202507 = 1)."""
    start_year, start_month = divmod(start, 100)
    end_year, end_month = divmod(end, 100)
    return (end_year - start_year) * 12 + (end_month - start_month)


def month_range(start: int, end: int) -> list[int]:
    """Meses de ``start`` a ``end``, inclusive (vazio se ``end < start``)."""
    months: list[int] = []
    current = start
    while current <= end:
        months.append(current)
        current = next_month(current)
    return months
