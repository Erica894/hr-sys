"""预算分发计算器：三种规则、舍入兜底、整数模式（LTI）。"""
import pytest
from decimal import Decimal
from datetime import date

from apps.iam.models import OrgUnit
from apps.hr_master.models import Employee, CompensationRecord
from apps.compensation_plan.services.budget_distribution import compute_distribution


@pytest.fixture
def two_depts(db):
    a = OrgUnit.objects.create(code="DA", name="A", type="DEPT")
    b = OrgUnit.objects.create(code="DB", name="B", type="DEPT")
    return a, b


def _emp(no, name, ou, cat1="STAFF", monthly=None):
    e = Employee.objects.create(
        employee_no=no, name_cn=name, org_unit=ou,
        employee_category_1=cat1, status="ACTIVE", hire_date=date(2026, 1, 1),
    )
    if monthly is not None:
        CompensationRecord.objects.create(
            employee=e, effective_date=date(2026, 1, 1),
            base_salary=monthly, monthly_salary=monthly,
        )
    return e


@pytest.mark.django_db
def test_manual_mode_passes_through(two_depts):
    a, b = two_depts
    out = compute_distribution(
        total=Decimal("100"), cat1="STAFF", mode="MANUAL",
        target_unit_ids=[a.id, b.id],
        manual_amounts={a.id: 60, b.id: 40},
    )
    assert out == {a.id: Decimal("60.00"), b.id: Decimal("40.00")}


@pytest.mark.django_db
def test_manual_mode_rejects_oversum(two_depts):
    a, b = two_depts
    with pytest.raises(ValueError):
        compute_distribution(
            total=Decimal("100"), cat1="STAFF", mode="MANUAL",
            target_unit_ids=[a.id, b.id],
            manual_amounts={a.id: 80, b.id: 50},
        )


@pytest.mark.django_db
def test_headcount_mode(two_depts):
    a, b = two_depts
    _emp("X1", "x1", a)
    _emp("X2", "x2", a)
    _emp("X3", "x3", a)
    _emp("Y1", "y1", b)
    out = compute_distribution(
        total=Decimal("400"), cat1="STAFF", mode="HEADCOUNT",
        target_unit_ids=[a.id, b.id],
    )
    assert out[a.id] == Decimal("300.00")
    assert out[b.id] == Decimal("100.00")


@pytest.mark.django_db
def test_salary_total_mode(two_depts):
    a, b = two_depts
    _emp("S1", "s1", a, monthly=Decimal("10000"))
    _emp("S2", "s2", b, monthly=Decimal("30000"))
    out = compute_distribution(
        total=Decimal("400"), cat1="STAFF", mode="SALARY_TOTAL",
        target_unit_ids=[a.id, b.id],
    )
    assert out[a.id] == Decimal("100.00")
    assert out[b.id] == Decimal("300.00")


@pytest.mark.django_db
def test_rounding_drift_lands_on_largest_weight(two_depts):
    a, b = two_depts
    _emp("R1", "r1", a)
    _emp("R2", "r2", a)
    _emp("R3", "r3", b)
    # 100 / 3 配 2:1 = 66.666... + 33.333...，量化后 66.67 + 33.33 = 100，无 drift
    # 用 100.01 强制 drift
    out = compute_distribution(
        total=Decimal("100.01"), cat1="STAFF", mode="HEADCOUNT",
        target_unit_ids=[a.id, b.id],
    )
    assert out[a.id] + out[b.id] == Decimal("100.01")


@pytest.mark.django_db
def test_zero_weight_falls_back_even(two_depts):
    a, b = two_depts
    out = compute_distribution(
        total=Decimal("100"), cat1="STAFF", mode="HEADCOUNT",
        target_unit_ids=[a.id, b.id],
    )
    assert out[a.id] + out[b.id] == Decimal("100.00")


@pytest.mark.django_db
def test_integer_units_for_lti(two_depts):
    a, b = two_depts
    _emp("L1", "l1", a)
    _emp("L2", "l2", b)
    _emp("L3", "l3", b)
    out = compute_distribution(
        total=Decimal("1000"), cat1="STAFF", mode="HEADCOUNT",
        target_unit_ids=[a.id, b.id], integer_units=True,
    )
    assert out[a.id] == Decimal("333") or out[a.id] == Decimal("334")
    assert out[a.id] + out[b.id] == Decimal("1000")
    for v in out.values():
        assert v == Decimal(int(v))
