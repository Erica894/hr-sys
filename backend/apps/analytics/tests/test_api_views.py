"""分析模块 4 个 API 的契约/数据流测试。"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.hr_master.models import Employee
from apps.iam.models import OrgUnit, OrgUnitManager, Role, User, UserRole
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
def two_emps_two_years(db):
    a = OrgUnit.objects.create(code="DA", name="DeptA", type="DEPT")
    b = OrgUnit.objects.create(code="DB", name="DeptB", type="DEPT")
    e1 = Employee.objects.create(employee_no="E1", name_cn="e1", org_unit=a)
    e2 = Employee.objects.create(employee_no="E2", name_cn="e2", org_unit=b)
    for emp, ou, base, target in [(e1, a, 100000, 110000), (e2, b, 200000, 210000)]:
        EmployeeCompensationSnapshot.objects.create(
            employee=emp, year=2025, snapshot_kind="ACTUAL",
            org_unit_snapshot_id=ou.id,
            annual_fixed_cny=Decimal(str(base)),
            annual_cash_cny=Decimal(str(base)),
            annual_total_comp_cny=Decimal(str(base)),
        )
        EmployeeCompensationSnapshot.objects.create(
            employee=emp, year=2026, snapshot_kind="ACTUAL",
            org_unit_snapshot_id=ou.id,
            annual_fixed_cny=Decimal(str(target)),
            annual_cash_cny=Decimal(str(target)),
            annual_total_comp_cny=Decimal(str(target)),
        )
    return e1, e2, a, b


def test_overview_returns_aggregates(hr_client, two_emps_two_years):
    r = hr_client.get("/api/analytics/overview/?year=2026")
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2026
    assert body["headcount"] == 2
    assert Decimal(body["annual_fixed_cny"]["avg"]) == Decimal("160000.00")


def test_overview_requires_year(hr_client):
    r = hr_client.get("/api/analytics/overview/")
    assert r.status_code == 400


def test_by_dept_two_year_compare(hr_client, two_emps_two_years):
    r = hr_client.get("/api/analytics/by-dept/?year=2026&compare_year=2025")
    assert r.status_code == 200
    body = r.json()
    assert {row["org_unit_name"] for row in body["rows"]} == {"DeptA", "DeptB"}
    a_row = next(row for row in body["rows"] if row["org_unit_name"] == "DeptA")
    assert abs(float(a_row["annual_fixed_cny"]["delta"]) - 0.1) < 1e-6


def test_distribution_endpoint_exists(hr_client, cycle, two_emps_two_years):
    r = hr_client.get(f"/api/analytics/distribution/?cycle_id={cycle.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["year_from"] == 2025 and body["year_to"] == 2026
    # 没有 matrix cell 全部落 UNKNOWN
    assert all(row["bucket"] == "UNKNOWN" for row in body["rows"])


def test_employee_timeline(hr_client, cycle, two_emps_two_years):
    e1, *_ = two_emps_two_years
    r = hr_client.get(
        f"/api/analytics/employee/{e1.id}/timeline/?cycle_id={cycle.id}"
    )
    assert r.status_code == 200
    body = r.json()
    years = [row["year"] for row in body["timeline"]]
    assert years == [2025, 2026, 2027]
    y2026 = next(row for row in body["timeline"] if row["year"] == 2026)
    assert Decimal(y2026["annual_fixed_cny"]) == Decimal("110000.00")


def test_employee_timeline_404_when_no_data(hr_client, cycle, two_emps_two_years):
    r = hr_client.get(
        f"/api/analytics/employee/99999/timeline/?cycle_id={cycle.id}"
    )
    assert r.status_code == 404
