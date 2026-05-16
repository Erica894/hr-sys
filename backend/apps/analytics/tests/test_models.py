"""三模型基础约束测试：unique_together / 默认值。"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.hr_master.models import Employee
from apps.analytics.models import (
    EmployeeCompensationSnapshot,
    FxRateMonthly,
    MarketSalaryReference,
)


@pytest.fixture
def emp(db):
    return Employee.objects.create(employee_no="E_AN_001", name_cn="snapshot_emp")


@pytest.mark.django_db
def test_snapshot_unique_employee_year_kind(emp):
    EmployeeCompensationSnapshot.objects.create(
        employee=emp, year=2026, snapshot_kind="ACTUAL",
        annual_fixed_cny=Decimal("240000"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmployeeCompensationSnapshot.objects.create(
                employee=emp, year=2026, snapshot_kind="ACTUAL",
            )


@pytest.mark.django_db
def test_snapshot_same_emp_different_kind_ok(emp):
    EmployeeCompensationSnapshot.objects.create(
        employee=emp, year=2026, snapshot_kind="ACTUAL"
    )
    EmployeeCompensationSnapshot.objects.create(
        employee=emp, year=2026, snapshot_kind="PROJECTED"
    )
    assert EmployeeCompensationSnapshot.objects.filter(employee=emp, year=2026).count() == 2


@pytest.mark.django_db
def test_fx_rate_unique_quote_target_month():
    FxRateMonthly.objects.create(
        quote_currency="USD", target_currency="CNY", month="2026-03",
        rate=Decimal("7.200000"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FxRateMonthly.objects.create(
                quote_currency="USD", target_currency="CNY", month="2026-03",
                rate=Decimal("7.300000"),
            )


@pytest.mark.django_db
def test_fx_rate_different_month_ok():
    FxRateMonthly.objects.create(
        quote_currency="HKD", target_currency="CNY", month="2026-03",
        rate=Decimal("0.920000"),
    )
    FxRateMonthly.objects.create(
        quote_currency="HKD", target_currency="CNY", month="2026-04",
        rate=Decimal("0.910000"),
    )
    assert FxRateMonthly.objects.count() == 2


@pytest.mark.django_db
def test_market_salary_unique_level_region_year():
    MarketSalaryReference.objects.create(
        job_level_code="P5", region="CN-SHA", year=2026,
        p50_cny=Decimal("400000"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MarketSalaryReference.objects.create(
                job_level_code="P5", region="CN-SHA", year=2026,
            )
