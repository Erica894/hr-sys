import pytest

from apps.analytics.services.year_window import resolve_window


class _Cycle:
    def __init__(self, period):
        self.period = period


@pytest.mark.parametrize(
    "period,expected",
    [
        ("2026", (2025, 2026, 2027)),
        ("2025", (2024, 2025, 2026)),
        ("2030", (2029, 2030, 2031)),
    ],
)
def test_resolve_window_returns_y_minus_1_y_y_plus_1(period, expected):
    assert resolve_window(_Cycle(period)) == expected


def test_resolve_window_rejects_non_year_period():
    with pytest.raises(ValueError):
        resolve_window(_Cycle("2026Q1"))
    with pytest.raises(ValueError):
        resolve_window(_Cycle(""))
