"""SaveProposalsView LTI cap：超目标层股数拒、未下发回退到公司层。"""
import pytest
from datetime import date
from decimal import Decimal
from rest_framework.test import APIClient

from apps.iam.models import User, OrgUnit, OrgUnitManager
from apps.hr_master.models import Employee
from apps.reward_cycle.models import RewardCycle
from apps.lti.models import LTIPlan, LTIBudgetCell, LTIGrant


def _setup_cycle(dept):
    plan = LTIPlan.objects.create(
        code="L_CAP", name="lc", grant_date=date(2026, 1, 1),
        total_shares=10000, unit_price_at_grant=Decimal("10.0"),
    )
    cycle = RewardCycle.objects.create(
        code="L_CAPC", name="c", period="2026", status="ALLOCATING",
        linked_lti_plan=plan,
    )
    e = Employee.objects.create(
        employee_no="LCAP1", name_cn="lcap1", org_unit=dept,
        employee_category_1="STAFF", status="ACTIVE", hire_date=date(2026, 1, 1),
    )
    g = LTIGrant.objects.create(
        plan=plan, employee=e, granted_ads=0,
        employee_category_1_snapshot="STAFF",
    )
    return plan, cycle, e, g


@pytest.fixture
def manager_user(db):
    return User.objects.create_user(email="lcapmgr@x.com", employee_no="LCMGR", password="x")


@pytest.mark.django_db
def test_lti_dept_cap_blocks_overage(manager_user):
    dept = OrgUnit.objects.create(code="LCD1", name="D", type="DEPT")
    OrgUnitManager.objects.create(
        org_unit=dept, manager=manager_user, role_in_unit="DEPT_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    plan, cycle, e, g = _setup_cycle(dept)
    LTIBudgetCell.objects.create(
        plan=plan, employee_category_1="STAFF",
        target_org_unit=dept, shares_quota_ads=500,
    )
    c = APIClient()
    c.force_authenticate(manager_user)
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "granted_ads": 600}],
    }, format="json")
    assert r.status_code == 400, r.json()
    body = r.json()
    assert body["error"] == "BUDGET_EXCEEDED"
    v = [x for x in body["violations"] if x.get("subject") == "LTI"][0]
    assert v["level"] == "TARGET"
    assert v["target_org_unit_id"] == dept.id


@pytest.mark.django_db
def test_lti_dept_cap_allows_within_budget(manager_user):
    dept = OrgUnit.objects.create(code="LCD2", name="D", type="DEPT")
    plan, cycle, e, g = _setup_cycle(dept)
    LTIBudgetCell.objects.create(
        plan=plan, employee_category_1="STAFF",
        target_org_unit=dept, shares_quota_ads=1000,
    )
    c = APIClient()
    c.force_authenticate(manager_user)
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "granted_ads": 800}],
    }, format="json")
    assert r.status_code == 200, r.json()


@pytest.mark.django_db
def test_lti_falls_back_to_company_when_no_targets(manager_user):
    dept = OrgUnit.objects.create(code="LCD3", name="D", type="DEPT")
    plan, cycle, e, g = _setup_cycle(dept)
    LTIBudgetCell.objects.create(
        plan=plan, employee_category_1="STAFF",
        target_org_unit=None, shares_quota_ads=400,
    )
    c = APIClient()
    c.force_authenticate(manager_user)
    r = c.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {
        "items": [{"employee_id": e.id, "granted_ads": 500}],
    }, format="json")
    assert r.status_code == 400
    v = [x for x in r.json()["violations"] if x.get("subject") == "LTI"][0]
    assert v["level"] == "COMPANY"
