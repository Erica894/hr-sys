from decimal import Decimal

import openpyxl
import pytest
from django.core.management import call_command

from apps.analytics.models import FxRateMonthly


def _make_xlsx(tmp_path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["quote_currency", "target_currency", "month", "rate", "note"])
    for r in rows:
        ws.append(r)
    p = tmp_path / "fx.xlsx"
    wb.save(p)
    return str(p)


@pytest.mark.django_db
def test_import_creates_rows(tmp_path):
    path = _make_xlsx(tmp_path, [
        ["USD", "CNY", "2026-03", "7.2", "March"],
        ["HKD", "CNY", "2026-12", "0.92", "Dec"],
    ])
    call_command("import_fx_rates", path)
    assert FxRateMonthly.objects.count() == 2
    r = FxRateMonthly.objects.get(quote_currency="USD", target_currency="CNY", month="2026-03")
    assert r.rate == Decimal("7.2")
    assert r.source == "IMPORT"


@pytest.mark.django_db
def test_import_upserts(tmp_path):
    FxRateMonthly.objects.create(
        quote_currency="USD", target_currency="CNY", month="2026-03",
        rate=Decimal("7.0"), source="MANUAL",
    )
    path = _make_xlsx(tmp_path, [["USD", "CNY", "2026-03", "7.25", "updated"]])
    call_command("import_fx_rates", path)

    r = FxRateMonthly.objects.get(quote_currency="USD", target_currency="CNY", month="2026-03")
    assert r.rate == Decimal("7.25")
    assert r.source == "IMPORT"
    assert FxRateMonthly.objects.count() == 1
