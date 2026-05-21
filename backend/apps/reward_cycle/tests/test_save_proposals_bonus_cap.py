"""SaveProposalsView Bonus cap: 超目标层金额拒、未下发回退到公司层。"""
import pytest
from datetime import date
from decimal import Decimal
from rest_framework.test import APIClient

from apps.iam.models import User, OrgUnit, OrgUnitManager
from apps.hr_master.models import Employee
from apps.reward_cycle.models import RewardCycle
from apps.bonus_pool.models import BonusPlan, BonusBudgetCell, BonusProposal


def _setup_cycle(dept):
    plan = BonusPlan.objects.create(
        code="BC_CAP", name="bc", period="2026",
    )
    cycle = RewardCycle.objects.create(
        code="BC_CAPC", name="c", period="2026", status="ALLOCATING",
        linked_bonus_plan=plan,
    )
    e = Employee.objects.create(
        employee_no="BCAP1", name_cn="bcap1", org_unit=dept,
        employee_category_1="STAFF", status="ACTIVE", hire_date=date(2026, 1, 1),
    )
    p = BonusProposal.objects.create(
        plan=plan, employee=e,
        suggested_amount_cny=Decimal("5000"),
        manager_delta_amount_cny=Decimal("0"),
        employee_category_1_snapshot="STAFF",
    )
    return plan, cycle, e, p


@pytest.fixture
def manager_user(db):
    return User.objects.create_user(email="bcapmgr@x.com", employee_no="BCMGR", password="x")


@pytest.mark.django_db
def test_bonus_dept_cap_blocks_overage(manager_user):
    dept = OrgUnit.objects.create(code="BCD1", name="D", type="DEPT")
    OrgUnitManager.objects.create(
        org_unit=dept, manager=manager_user, role_in_unit="DEPT_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    plan, cycle, e, p = _setup_cycle(dept)
    BonusBudgetCell.objects.create(
        reward_cycle=cycle, employee_category_1="STAFF",
        target_org_unit=dept, budget_amount_cny=Decimal("8000"),
    )
    c = APIClient()
    c.force_authenticate(manager_user)
    # suggested 5000 + delta 5000 = 10000 > budget 8000
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "bonus_manager_delta_amount_cny": "5000"}],
    }, format="json")
    assert r.status_code == 400, r.json()
    body = r.json()
    assert body["error"] == "BUDGET_EXCEEDED"
    v = [x for x in body["violations"] if x.get("subject") == "BONUS"][0]
    assert v["level"] == "TARGET"
    assert v["target_org_unit_id"] == dept.id


@pytest.mark.django_db
def test_bonus_dept_cap_allows_within_budget(manager_user):
    dept = OrgUnit.objects.create(code="BCD2", name="D", type="DEPT")
    plan, cycle, e, p = _setup_cycle(dept)
    BonusBudgetCell.objects.create(
        reward_cycle=cycle, employee_category_1="STAFF",
        target_org_unit=dept, budget_amount_cny=Decimal("20000"),
    )
    c = APIClient()
    c.force_authenticate(manager_user)
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "bonus_manager_delta_amount_cny": "1000"}],
    }, format="json")
    assert r.status_code == 200, r.json()
    p.refresh_from_db()
    assert p.manager_delta_amount_cny == Decimal("1000.00")


@pytest.mark.django_db
def test_bonus_falls_back_to_company_when_no_targets(manager_user):
    dept = OrgUnit.objects.create(code="BCD3", name="D", type="DEPT")
    plan, cycle, e, p = _setup_cycle(dept)
    BonusBudgetCell.objects.create(
        reward_cycle=cycle, employee_category_1="STAFF",
        target_org_unit=None, budget_amount_cny=Decimal("5000"),
    )
    c = APIClient()
    c.force_authenticate(manager_user)
    # suggested 5000 + delta 1000 = 6000 > company budget 5000
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "bonus_manager_delta_amount_cny": "1000"}],
    }, format="json")
    assert r.status_code == 400
    v = [x for x in r.json()["violations"] if x.get("subject") == "BONUS"][0]
    assert v["level"] == "COMPANY"
