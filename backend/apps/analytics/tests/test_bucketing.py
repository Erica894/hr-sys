from decimal import Decimal

import pytest

from apps.analytics.services.bucketing import (
    BUCKET_HIGH,
    BUCKET_IN_RANGE,
    BUCKET_LOW,
    bucket_by_matrix_tier,
    compute_tier_interval,
)


def test_compute_interval():
    low, high = compute_tier_interval(
        base_pct=Decimal("0.05"),
        factor=Decimal("1.0"),
        coef_low=Decimal("0.8"),
        coef_high=Decimal("1.2"),
    )
    assert low == Decimal("0.0400")
    assert high == Decimal("0.0600")


@pytest.mark.parametrize(
    "delta,expected",
    [
        (Decimal("0.03"), BUCKET_LOW),
        (Decimal("0.05"), BUCKET_IN_RANGE),
        (Decimal("0.04"), BUCKET_IN_RANGE),
        (Decimal("0.06"), BUCKET_IN_RANGE),
        (Decimal("0.07"), BUCKET_HIGH),
    ],
)
def test_bucket_by_matrix_tier(delta, expected):
    assert (
        bucket_by_matrix_tier(
            actual_delta=delta,
            base_pct=Decimal("0.05"),
            factor=Decimal("1.0"),
            coef_low=Decimal("0.8"),
            coef_high=Decimal("1.2"),
        )
        == expected
    )


def test_bucket_with_factor_scaling():
    # base 5% × factor 1.5 = 7.5%; coef [0.8,1.2] → [6%, 9%]
    assert bucket_by_matrix_tier(
        Decimal("0.05"), Decimal("0.05"), Decimal("1.5"),
        Decimal("0.8"), Decimal("1.2"),
    ) == BUCKET_LOW
    assert bucket_by_matrix_tier(
        Decimal("0.075"), Decimal("0.05"), Decimal("1.5"),
        Decimal("0.8"), Decimal("1.2"),
    ) == BUCKET_IN_RANGE
    assert bucket_by_matrix_tier(
        Decimal("0.10"), Decimal("0.05"), Decimal("1.5"),
        Decimal("0.8"), Decimal("1.2"),
    ) == BUCKET_HIGH
