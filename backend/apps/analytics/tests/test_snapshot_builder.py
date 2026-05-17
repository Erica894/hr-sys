"""snapshot_builder 派生测试 — 多币种 + 多月薪制 + RSU。"""
from datetime import date
from decimal import Decimal

import pytest

from apps.analytics.models import FxRateMonthly
from apps.analytics.services.snapshot_builder import build_snapshot_for_employee
from apps.hr_master.models import CompensationRecord, Employee, LegalEntity
from apps.lti.models import LTIGrant, LTIPlan, StockPriceMonthly


@pytest.mark.django_db
def test_china_employee_12_months_no_rsu():
    le = LegalEntity.objects.create(code="CN", name="中国大陆", country="CN")
    emp = Employee.objects.create(
        employee_no="E_SB_001", name_cn="zhangsan", legal_entity=le,
        pay_currency="CNY", status="ACTIVE",
    )
    CompensationRecord.objects.create(
        employee=emp, effective_date=date(2026, 1, 1),
        base_salary=Decimal("20000"), monthly_salary=Decimal("20000"),
        currency="CNY",
    )

    snap = build_snapshot_for_employee(emp, 2026, "ACTUAL")

    assert snap.annual_fixed_cny == Decimal("240000.00")
    assert snap.annual_bonus_cny == Decimal("0.00")
    assert snap.annual_cash_cny == Decimal("240000.00")
    assert snap.annual_rsu_value_cny == Decimal("0.00")
    assert snap.annual_total_comp_cny == Decimal("240000.00")
    assert snap.source == "DERIVED"


@pytest.mark.django_db
def test_china_employee_with_rsu():
    le = LegalEntity.objects.create(code="CN2", name="中国大陆", country="CN")
    emp = Employee.objects.create(
        employee_no="E_SB_002", name_cn="lisi", legal_entity=le,
        pay_currency="CNY", status="ACTIVE",
    )
    CompensationRecord.objects.create(
        employee=emp, effective_date=date(2026, 1, 1),
        base_salary=Decimal("20000"), monthly_salary=Decimal("20000"), currency="CNY",
    )
    plan = LTIPlan.objects.create(
        code="LTI2026", name="2026 RSU", grant_date=date(2026, 1, 1),
        unit_price_at_grant=Decimal("10.0000"), stock_code="ABCD",
    )
    LTIGrant.objects.create(
        plan=plan, employee=emp, stock_code="ABCD",
        unit_price_at_grant=Decimal("10.0000"),
        pending_shares_by_year={"2026": 50},
    )
    StockPriceMonthly.objects.create(
        stock_code="ABCD", month="2026-03",
        closing_price=Decimal("10.0000"), currency="USD",
    )
    FxRateMonthly.objects.create(
        quote_currency="USD", target_currency="CNY", month="2026-03",
        rate=Decimal("7.200000"),
    )

    snap = build_snapshot_for_employee(emp, 2026, "ACTUAL")

    assert snap.annual_fixed_cny == Decimal("240000.00")
    assert snap.annual_rsu_value_cny == Decimal("3600.00")  # 50 × 10 × 7.2
    assert snap.annual_total_comp_cny == Decimal("243600.00")


@pytest.mark.django_db
def test_hk_employee_13_months_hkd_to_cny():
    le = LegalEntity.objects.create(
        code="HK", name="香港", country="HK",
        fixed_pay_months_per_year=Decimal("13"),
    )
    emp = Employee.objects.create(
        employee_no="E_SB_003", name_cn="hkstaff", legal_entity=le,
        pay_currency="HKD", status="ACTIVE",
    )
    CompensationRecord.objects.create(
        employee=emp, effective_date=date(2026, 1, 1),
        base_salary=Decimal("30000"), monthly_salary=Decimal("30000"),
        currency="HKD",
    )
    FxRateMonthly.objects.create(
        quote_currency="HKD", target_currency="CNY", month="2026-12",
        rate=Decimal("0.920000"),
    )

    snap = build_snapshot_for_employee(emp, 2026, "ACTUAL")

    # 30000 HKD × 13 = 390000 HKD; × 0.92 = 358800 CNY
    assert snap.annual_fixed_cny == Decimal("358800.00")
    assert snap.annual_total_comp_cny == Decimal("358800.00")


@pytest.mark.django_db
def test_idempotent_update_or_create():
    le = LegalEntity.objects.create(code="CN3", name="中国大陆", country="CN")
    emp = Employee.objects.create(
        employee_no="E_SB_004", name_cn="x", legal_entity=le,
        pay_currency="CNY", status="ACTIVE",
    )
    CompensationRecord.objects.create(
        employee=emp, effective_date=date(2026, 1, 1),
        base_salary=Decimal("10000"), monthly_salary=Decimal("10000"), currency="CNY",
    )
    s1 = build_snapshot_for_employee(emp, 2026, "ACTUAL")
    s2 = build_snapshot_for_employee(emp, 2026, "ACTUAL")
    assert s1.pk == s2.pk
