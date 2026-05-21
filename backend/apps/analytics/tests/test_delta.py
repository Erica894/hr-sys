from decimal import Decimal

import pytest

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.analytics.services.delta import (
    FIVE_COLS,
    compute_5col_delta,
)
from apps.hr_master.models import Employee
from apps.iam.models import OrgUnit


@pytest.fixture
def employee(db):
    ou = OrgUnit.objects.create(code="D1", name="D1", type="DEPT")
    return Employee.objects.create(
        employee_no="E001", name_cn="Alice", org_unit=ou, status="ACTIVE",
    )


def _snap(emp, year, kind, **cols):
    base = {
        "annual_fixed_cny": 0, "annual_bonus_cny": 0, "annual_cash_cny": 0,
        "annual_rsu_value_cny": 0, "annual_total_comp_cny": 0,
    }
    base.update(cols)
    return EmployeeCompensationSnapshot.objects.create(
        employee=emp, year=year, snapshot_kind=kind, **base,
    )


def test_normal_growth_5col(employee):
    _snap(employee, 2025, "ACTUAL",
          annual_fixed_cny=Decimal("100000"), annual_bonus_cny=Decimal("20000"),
          annual_cash_cny=Decimal("120000"), annual_rsu_value_cny=Decimal("10000"),
          annual_total_comp_cny=Decimal("130000"))
    _snap(employee, 2026, "ACTUAL",
          annual_fixed_cny=Decimal("110000"), annual_bonus_cny=Decimal("22000"),
          annual_cash_cny=Decimal("132000"), annual_rsu_value_cny=Decimal("11000"),
          annual_total_comp_cny=Decimal("143000"))

    d = compute_5col_delta(employee.id, 2025, 2026)
    assert d["annual_fixed_cny"] == Decimal("0.1000")
    assert d["annual_bonus_cny"] == Decimal("0.1000")
    assert d["annual_cash_cny"] == Decimal("0.1000")
    assert d["annual_rsu_value_cny"] == Decimal("0.1000")
    assert d["annual_total_comp_cny"] == Decimal("0.1000")
    assert set(d.keys()) == set(FIVE_COLS)


def test_zero_baseline_returns_none_for_that_col(employee):
    _snap(employee, 2025, "ACTUAL", annual_fixed_cny=Decimal("100000"))
    _snap(employee, 2026, "ACTUAL",
          annual_fixed_cny=Decimal("110000"), annual_bonus_cny=Decimal("5000"),
          annual_cash_cny=Decimal("115000"), annual_total_comp_cny=Decimal("115000"))

    d = compute_5col_delta(employee.id, 2025, 2026)
    assert d["annual_fixed_cny"] == Decimal("0.1000")
    # bonus 2025 = 0 → delta None（不能除 0）
    assert d["annual_bonus_cny"] is None
    assert d["annual_rsu_value_cny"] is None


def test_missing_year_raises(employee):
    _snap(employee, 2025, "ACTUAL", annual_fixed_cny=Decimal("100000"))
    with pytest.raises(LookupError):
        compute_5col_delta(employee.id, 2025, 2026)


def test_y_plus_1_uses_projected(employee):
    _snap(employee, 2026, "ACTUAL", annual_fixed_cny=Decimal("100000"),
          annual_cash_cny=Decimal("100000"), annual_total_comp_cny=Decimal("100000"))
    _snap(employee, 2027, "PROJECTED", annual_fixed_cny=Decimal("106000"),
          annual_cash_cny=Decimal("106000"), annual_total_comp_cny=Decimal("106000"))

    d = compute_5col_delta(employee.id, 2026, 2027)
    assert d["annual_fixed_cny"] == Decimal("0.0600")
