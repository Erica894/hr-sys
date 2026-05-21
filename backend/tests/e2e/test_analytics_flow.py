"""分析模块 4 个 API 端到端串联测试。

覆盖：
1. 准备两年快照 (2025/2026) + AdjustmentMatrixCell
2. /api/analytics/overview/?year=2026
3. /api/analytics/by-dept/?year=2026&compare_year=2025
4. /api/analytics/distribution/?cycle_id=N
5. /api/analytics/employee/<id>/timeline/?cycle_id=N
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.hr_master.models import Employee
from apps.iam.models import OrgUnit, Role, User, UserRole
from apps.reward_cycle.models import RewardCycle


@pytest.fixture
def hr_client(db):
    u = User.objects.create_user(email="hr@x.com", employee_no="HR1", password="x")
    role, _ = Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "HR"})
    UserRole.objects.create(user=u, role=role, scope_type="GLOBAL")
    c = APIClient()
    c.force_authenticate(u)
    return c


@pytest.fixture
def cycle(db):
    return RewardCycle.objects.create(code="C2026", name="2026", period="2026")


@pytest.fixture
def stack(db, cycle):
    a = OrgUnit.objects.create(code="DA", name="DeptA", type="DEPT")
    b = OrgUnit.objects.create(code="DB", name="DeptB", type="DEPT")
    e1 = Employee.objects.create(employee_no="E1", name_cn="e1", org_unit=a)
    e2 = Employee.objects.create(employee_no="E2", name_cn="e2", org_unit=b)
    for emp, ou, base, target in [(e1, a, 100000, 110000), (e2, b, 200000, 220000)]:
        EmployeeCompensationSnapshot.objects.create(
            employee=emp, year=2025, snapshot_kind="ACTUAL",
            org_unit_snapshot_id=ou.id,
            annual_fixed_cny=Decimal(base), annual_cash_cny=Decimal(base),
            annual_total_comp_cny=Decimal(base),
        )
        EmployeeCompensationSnapshot.objects.create(
            employee=emp, year=2026, snapshot_kind="ACTUAL",
            org_unit_snapshot_id=ou.id,
            annual_fixed_cny=Decimal(target), annual_cash_cny=Decimal(target),
            annual_total_comp_cny=Decimal(target),
        )
    return e1, e2, cycle


def test_analytics_e2e_full_loop(hr_client, stack):
    e1, e2, cycle = stack

    # 1) overview
    r = hr_client.get("/api/analytics/overview/?year=2026")
    assert r.status_code == 200
    body = r.json()
    assert body["headcount"] == 2
    assert Decimal(body["annual_fixed_cny"]["avg"]) == Decimal("165000.00")

    # 2) by-dept compare
    r = hr_client.get("/api/analytics/by-dept/?year=2026&compare_year=2025")
    assert r.status_code == 200
    body = r.json()
    assert {row["org_unit_name"] for row in body["rows"]} == {"DeptA", "DeptB"}

    # 3) distribution (无 matrix → 全部 UNKNOWN 桶)
    r = hr_client.get(f"/api/analytics/distribution/?cycle_id={cycle.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["year_from"] == 2025 and body["year_to"] == 2026
    assert all(row["bucket"] == "UNKNOWN" for row in body["rows"])

    # 4) employee timeline
    r = hr_client.get(f"/api/analytics/employee/{e1.id}/timeline/?cycle_id={cycle.id}")
    assert r.status_code == 200
    body = r.json()
    years = [row["year"] for row in body["timeline"]]
    assert years == [2025, 2026, 2027]
