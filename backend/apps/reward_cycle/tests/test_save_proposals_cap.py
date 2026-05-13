"""SaveProposalsView 调薪 cap 校验：超部门额度拒、未下发回退到公司层。"""
import pytest
from datetime import date
from decimal import Decimal
from rest_framework.test import APIClient

from apps.iam.models import User, OrgUnit, OrgUnitManager
from apps.hr_master.models import Employee
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import (
    AdjustmentPlan, AdjustmentBudgetCell, AdjustmentProposal,
)


def _make_cycle_with_plan_and_emp(salary, dept):
    plan = AdjustmentPlan.objects.create(code="P_CAP", name="cap", period="2026", status="DRAFT")
    cycle = RewardCycle.objects.create(
        code="C_CAP", name="cap", period="2026", status="ALLOCATING",
        linked_adjustment_plan=plan,
    )
    e = Employee.objects.create(
        employee_no="E_CAP1", name_cn="cap1", org_unit=dept,
        employee_category_1="STAFF", status="ACTIVE", hire_date=date(2026, 1, 1),
    )
    AdjustmentProposal.objects.create(
        plan=plan, employee=e, current_salary=Decimal(str(salary)),
        annual_suggested_pct=Decimal("0.05"),
        annual_manager_delta_pct=Decimal("0"),
        employee_category_1_snapshot="STAFF",
    )
    return plan, cycle, e


@pytest.fixture
def manager_user(db):
    return User.objects.create_user(email="capmgr@x.com", employee_no="CAP_MGR", password="x")


@pytest.mark.django_db
def test_dept_cap_blocks_overage(manager_user):
    dept = OrgUnit.objects.create(code="D_CAP", name="D", type="DEPT")
    OrgUnitManager.objects.create(
        org_unit=dept, manager=manager_user, role_in_unit="DEPT_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    plan, cycle, e = _make_cycle_with_plan_and_emp(Decimal("10000"), dept)
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=dept, budget_amount_cny=Decimal("6000"),
    )

    c = APIClient()
    c.force_authenticate(manager_user)
    # 10000 × (0.05 + 0.01) × 12 = 7200，超 6000
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "annual_manager_delta_pct": "0.01"}],
    }, format="json")
    assert r.status_code == 400
    assert r.json()["error"] == "BUDGET_EXCEEDED"
    v = r.json()["violations"][0]
    assert v["level"] == "TARGET"
    assert v["target_org_unit_id"] == dept.id


@pytest.mark.django_db
def test_dept_cap_allows_within_budget(manager_user):
    dept = OrgUnit.objects.create(code="D_OK", name="D", type="DEPT")
    plan, cycle, e = _make_cycle_with_plan_and_emp(Decimal("10000"), dept)
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=dept, budget_amount_cny=Decimal("8000"),
    )

    c = APIClient()
    c.force_authenticate(manager_user)
    # 10000 × (0.05 + 0.01) × 12 = 7200，不超 8000
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "annual_manager_delta_pct": "0.01"}],
    }, format="json")
    assert r.status_code == 200, r.json()


@pytest.mark.django_db
def test_falls_back_to_company_when_no_target_cells(manager_user):
    dept = OrgUnit.objects.create(code="D_FB", name="D", type="DEPT")
    plan, cycle, e = _make_cycle_with_plan_and_emp(Decimal("10000"), dept)
    # 只有公司层 cell，没下发
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=None, budget_amount_cny=Decimal("5000"),
    )

    c = APIClient()
    c.force_authenticate(manager_user)
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "annual_manager_delta_pct": "0.01"}],
    }, format="json")
    # 7200 > 5000 → 公司层超
    assert r.status_code == 400
    v = r.json()["violations"][0]
    assert v["level"] == "COMPANY"
