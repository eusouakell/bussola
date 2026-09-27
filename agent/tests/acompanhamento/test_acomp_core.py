"""Núcleo puro do 006: dinheiro, meses, desvio, linha de base e progresso (unidade)."""

import pytest

from bussola_agent.acompanhamento.desvio import (
    STATUS_DEVIATION,
    STATUS_ON_TRACK,
    STATUS_SURPLUS,
    TOLERANCE,
    baseline_by_macro,
    compute_deviation,
    deviation_category,
)
from bussola_agent.acompanhamento.money import format_brl, format_months, money
from bussola_agent.acompanhamento.periods import month_range, months_between, next_month
from bussola_agent.acompanhamento.progress import accumulated, compute_progress

# --- dinheiro ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(2.675, 2.68), (1.005, 1.01), (-1.005, -1.01), (2570.2391, 2570.24), (-0.001, 0.0)],
)
def test_money_rounds_half_up_with_two_decimals(value: float, expected: float) -> None:
    result = money(value)
    assert result == expected
    assert str(result) != "-0.0"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2570.24, "R$ 2.570,24"),
        (0, "R$ 0,00"),
        (1234567.891, "R$ 1.234.567,89"),
        (-5.5, "-R$ 5,50"),
    ],
)
def test_format_brl_uses_ptbr_separators(value: float, expected: str) -> None:
    assert format_brl(value) == expected


def test_format_months_singular_and_plural() -> None:
    assert (format_months(1), format_months(23)) == ("1 mês", "23 meses")


# --- meses ------------------------------------------------------------------


def test_next_month_turns_the_year() -> None:
    assert next_month(202506) == 202507
    assert next_month(202512) == 202601


def test_next_month_rejects_invalid_month() -> None:
    with pytest.raises(ValueError):
        next_month(202513)


def test_months_between_and_range() -> None:
    assert months_between(202506, 202507) == 1
    assert months_between(202411, 202502) == 3
    assert month_range(202501, 202503) == [202501, 202502, 202503]
    assert month_range(202503, 202501) == []


# --- desvio -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("actual", "status"),
    [
        (2250.00, STATUS_ON_TRACK),  # limite inferior incluído
        (2249.99, STATUS_DEVIATION),
        (2500.00, STATUS_ON_TRACK),
        (2750.00, STATUS_ON_TRACK),  # limite superior incluído
        (2750.01, STATUS_SURPLUS),
    ],
)
def test_deviation_status_uses_ten_percent_band(actual: float, status: str) -> None:
    result = compute_deviation(2500.0, actual)
    assert result.status == status
    assert result.tolerance == money(2500.0 * TOLERANCE) == 250.0


def test_deviation_values_follow_the_contract_names() -> None:
    result = compute_deviation(2500.0, 884.53)
    assert result.as_dict() == {
        "planejado": 2500.0,
        "realizado": 884.53,
        "desvio": -1615.47,
        "tolerancia": 250.0,
        "status": STATUS_DEVIATION,
    }


def test_negative_actual_is_a_deviation() -> None:
    result = compute_deviation(1000.0, -80.67)
    assert (result.deviation, result.status) == (-1080.67, STATUS_DEVIATION)


def test_baseline_counts_months_without_data_in_the_denominator() -> None:
    months = [
        [{"macro": "Casa", "total": 100.0}, {"macro": "Lazer", "total": 30.0}],
        None,
        [{"macro": "Casa", "total": 200.0}, {"macro": "ruim", "total": "x"}],
    ]
    assert baseline_by_macro(months) == {"Casa": 100.0, "Lazer": 10.0}
    assert baseline_by_macro([]) == {}


def test_category_is_the_largest_positive_increase() -> None:
    month = [
        {"macro": "Casa", "total": 1818.13},
        {"macro": "Viagens", "total": 935.14},
        {"macro": "Educacao", "total": 873.34},
    ]
    baseline = {"Casa": 2286.41, "Viagens": 6.51, "Educacao": 400.0}
    assert deviation_category(month, baseline) == {
        "macro": "Viagens",
        "valor_mes": 935.14,
        "media_base": 6.51,
        "aumento": 928.63,
    }


def test_category_is_none_without_a_positive_increase() -> None:
    assert deviation_category([{"macro": "Casa", "total": 10.0}], {"Casa": 20.0}) is None
    assert deviation_category(None, {}) is None


# --- progresso --------------------------------------------------------------


def test_accumulated_ignores_negative_months() -> None:
    assert accumulated([884.53, -80.67, 4218.74]) == 5103.27


def test_progress_after_three_months() -> None:
    progress = compute_progress(60000.0, 24, 202506, 202509, [884.53, 4218.74, 3723.47])
    assert progress.accumulated == 8826.74
    assert progress.remaining == 51173.26
    assert progress.percent == 14.71
    assert (progress.months_elapsed, progress.months_remaining) == (3, 21)


def test_progress_without_months_and_after_the_goal() -> None:
    empty = compute_progress(60000.0, 24, 202506, None, [])
    assert (empty.accumulated, empty.remaining, empty.months_elapsed) == (0.0, 60000.0, 0)
    done = compute_progress(1000.0, 2, 202506, 202509, [800.0, 800.0])
    assert (done.remaining, done.months_remaining, done.percent) == (0.0, 0, 160.0)


def test_progress_rejects_non_positive_target() -> None:
    with pytest.raises(ValueError):
        compute_progress(0.0, 24, 202506, 202507, [])
