"""调薪预算下发 API：成功 / 重叠拒 / 减到 allocated 以下拒 / dry_run。"""
import pytest
from decimal import Decimal
from rest_framework.test import APIClient

from apps.iam.models import User, OrgUnit
from apps.hr_master.models import Employee
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentBudgetCell


@pytest.fixture
def hr(db):
    user = User.objects.create_user(email="hr_dist@x.com", employee_no="HR_DIST", password="x")
    from apps.iam.models import Role, UserRole
    role, _ = Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "HR"})
    UserRole.objects.create(user=user, role=role)
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def cycle_with_company_budget(db):
    cycle = RewardCycle.objects.create(code="CD1", name="C", period="2026", status="DRAFT")
    return cycle


@pytest.fixture
def two_depts(db):
    a = OrgUnit.objects.create(code="DEPTA", name="A 部门", type="DEPT")
    b = OrgUnit.objects.create(code="DEPTB", name="B 部门", type="DEPT")
    Employee.objects.create(employee_no="EA1", name_cn="ea1", org_unit=a, employee_category_1="STAFF", status="ACTIVE")
    Employee.objects.create(employee_no="EA2", name_cn="ea2", org_unit=a, employee_category_1="STAFF", status="ACTIVE")
    Employee.objects.create(employee_no="EB1", name_cn="eb1", org_unit=b, employee_category_1="STAFF", status="ACTIVE")
    return a, b


@pytest.mark.django_db
def test_distribute_headcount_creates_target_cells(hr, cycle_with_company_budget, two_depts):
    a, b = two_depts
    cycle = cycle_with_company_budget

    # HR 先设公司层 600k
    hr.put(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/", {
        "rows": [
            {"adjustment_type": "ANNUAL", "employee_category_1": "STAFF", "budget_amount_cny": "600000"},
        ],
    }, format="json")

    r = hr.post(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/distribute/",
        {
            "adjustment_type": "ANNUAL",
            "employee_category_1": "STAFF",
            "mode": "HEADCOUNT",
            "target_org_unit_ids": [a.id, b.id],
        }, format="json",
    )
    assert r.status_code == 200, r.json()
    cells = AdjustmentBudgetCell.objects.filter(
        reward_cycle=cycle, adjustment_type="ANNUAL",
        employee_category_1="STAFF", department__isnull=False,
    )
    by_dept = {c.department_id: c.budget_amount_cny for c in cells}
    assert by_dept[a.id] == Decimal("400000.00")
    assert by_dept[b.id] == Decimal("200000.00")
    # 公司层规则被记下来
    company = AdjustmentBudgetCell.objects.get(
        reward_cycle=cycle, adjustment_type="ANNUAL",
        employee_category_1="STAFF", department__isnull=True,
    )
    assert company.distribution_rule == "HEADCOUNT"


@pytest.mark.django_db
def test_distribute_dry_run_does_not_persist(hr, cycle_with_company_budget, two_depts):
    a, b = two_depts
    cycle = cycle_with_company_budget
    hr.put(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/", {
        "rows": [{"adjustment_type": "ANNUAL", "employee_category_1": "STAFF", "budget_amount_cny": "300000"}],
    }, format="json")
    r = hr.post(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/distribute/",
        {
            "adjustment_type": "ANNUAL", "employee_category_1": "STAFF",
            "mode": "HEADCOUNT", "target_org_unit_ids": [a.id, b.id], "dry_run": True,
        }, format="json",
    )
    assert r.status_code == 200
    assert r.json()["dry_run"] is True
    assert AdjustmentBudgetCell.objects.filter(
        reward_cycle=cycle, department__isnull=False
    ).count() == 0


@pytest.mark.django_db
def test_distribute_overlap_rejected(hr, cycle_with_company_budget):
    cycle = cycle_with_company_budget
    parent = OrgUnit.objects.create(code="P", name="父", type="DEPT")
    child = OrgUnit.objects.create(code="C", name="子", type="CENTER", parent=parent)
    hr.put(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/", {
        "rows": [{"adjustment_type": "ANNUAL", "employee_category_1": "STAFF", "budget_amount_cny": "100000"}],
    }, format="json")
    r = hr.post(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/distribute/",
        {
            "adjustment_type": "ANNUAL", "employee_category_1": "STAFF",
            "mode": "MANUAL", "target_org_unit_ids": [parent.id, child.id],
            "manual_amounts": {parent.id: 50000, child.id: 50000},
        }, format="json",
    )
    assert r.status_code == 400
    assert r.json()["error"] == "TARGETS_OVERLAP"


@pytest.mark.django_db
def test_distribute_rejects_non_dept_center_target(hr, cycle_with_company_budget):
    cycle = cycle_with_company_budget
    team = OrgUnit.objects.create(code="T1", name="T1", type="TEAM")
    hr.put(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/", {
        "rows": [{"adjustment_type": "ANNUAL", "employee_category_1": "STAFF", "budget_amount_cny": "10000"}],
    }, format="json")
    r = hr.post(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/distribute/",
        {
            "adjustment_type": "ANNUAL", "employee_category_1": "STAFF",
            "mode": "MANUAL", "target_org_unit_ids": [team.id],
            "manual_amounts": {team.id: 10000},
        }, format="json",
    )
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_TARGET_TYPE"


@pytest.mark.django_db
def test_get_returns_targets_section(hr, cycle_with_company_budget, two_depts):
    a, b = two_depts
    cycle = cycle_with_company_budget
    hr.put(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/", {
        "rows": [{"adjustment_type": "ANNUAL", "employee_category_1": "STAFF", "budget_amount_cny": "300000"}],
    }, format="json")
    hr.post(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/distribute/",
        {
            "adjustment_type": "ANNUAL", "employee_category_1": "STAFF",
            "mode": "MANUAL", "target_org_unit_ids": [a.id, b.id],
            "manual_amounts": {a.id: 200000, b.id: 100000},
        }, format="json",
    )
    r = hr.get(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/")
    body = r.json()
    assert "company" in body and "targets" in body
    targets = {t["target_org_unit_id"]: t for t in body["targets"]}
    assert targets[a.id]["budget_amount_cny"] == "200000.00"
    assert targets[b.id]["budget_amount_cny"] == "100000.00"
