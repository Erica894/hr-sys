"""fx.convert 测试：缺月抛错 / 命中折算 / quote==target 直通。"""
from decimal import Decimal

import pytest

from apps.analytics.models import FxRateMonthly
from apps.analytics.services.fx import MissingFxRate, convert


@pytest.mark.django_db
def test_quote_equals_target_passthrough():
    assert convert(Decimal("100"), "CNY", "CNY", "2026-03") == Decimal("100")


@pytest.mark.django_db
def test_missing_rate_raises():
    with pytest.raises(MissingFxRate) as exc:
        convert(Decimal("100"), "HKD", "CNY", "2026-03")
    assert "HKD->CNY 2026-03" in str(exc.value)


@pytest.mark.django_db
def test_hit_rate_converts():
    FxRateMonthly.objects.create(
        quote_currency="HKD", target_currency="CNY", month="2026-03",
        rate=Decimal("0.920000"),
    )
    assert convert(Decimal("1000"), "HKD", "CNY", "2026-03") == Decimal("920.00")


@pytest.mark.django_db
def test_usd_to_cny_rsu_path():
    FxRateMonthly.objects.create(
        quote_currency="USD", target_currency="CNY", month="2026-03",
        rate=Decimal("7.200000"),
    )
    assert convert(Decimal("500"), "USD", "CNY", "2026-03") == Decimal("3600.00")
