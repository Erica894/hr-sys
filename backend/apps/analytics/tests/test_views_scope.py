"""DEPT_HEAD 跨部门脱敏 — 决策 D 的回归测试。"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.analytics.permissions import scope_snapshot_qs, visible_org_unit_ids
from apps.hr_master.models import Employee
from apps.iam.models import OrgUnit, OrgUnitManager, Role, User, UserRole


@pytest.fixture
def two_depts(db):
    a = OrgUnit.objects.create(code="DA", name="DA", type="DEPT")
    b = OrgUnit.objects.create(code="DB", name="DB", type="DEPT")
    emp_a = Employee.objects.create(employee_no="A1", name_cn="a1", org_unit=a)
    emp_b = Employee.objects.create(employee_no="B1", name_cn="b1", org_unit=b)
    EmployeeCompensationSnapshot.objects.create(
        employee=emp_a, year=2026, snapshot_kind="ACTUAL",
        org_unit_snapshot_id=a.id,
        annual_total_comp_cny=Decimal("100000"),
    )
    EmployeeCompensationSnapshot.objects.create(
        employee=emp_b, year=2026, snapshot_kind="ACTUAL",
        org_unit_snapshot_id=b.id,
        annual_total_comp_cny=Decimal("200000"),
    )
    return a, b


def _make_dept_head(username, org_unit):
    u = User.objects.create_user(email=f"{username}@x.com", employee_no=username, password="x")
    role, _ = Role.objects.get_or_create(code="DEPT_HEAD", defaults={"name": "部门"})
    UserRole.objects.create(user=u, role=role, scope_type="DEPT", scope_ref_id=org_unit.id)
    OrgUnitManager.objects.create(
        manager=u, org_unit=org_unit, effective_from=date(2020, 1, 1)
    )
    return u


def _make_hr(username):
    u = User.objects.create_user(email=f"{username}@x.com", employee_no=username, password="x")
    role, _ = Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "HR"})
    UserRole.objects.create(user=u, role=role, scope_type="GLOBAL")
    return u


def test_hr_admin_sees_all(two_depts):
    a, b = two_depts
    hr = _make_hr("hr")
    qs = scope_snapshot_qs(EmployeeCompensationSnapshot.objects.all(), hr)
    assert qs.count() == 2
    assert visible_org_unit_ids(hr) is None


def test_dept_head_sees_only_own(two_depts):
    a, b = two_depts
    head_a = _make_dept_head("ha", a)
    qs = scope_snapshot_qs(EmployeeCompensationSnapshot.objects.all(), head_a)
    assert qs.count() == 1
    assert qs.first().org_unit_snapshot_id == a.id


def test_user_with_no_scope_sees_nothing(two_depts):
    nobody = User.objects.create_user(email="n@x.com", employee_no="N1", password="x")
    qs = scope_snapshot_qs(EmployeeCompensationSnapshot.objects.all(), nobody)
    assert qs.count() == 0
