"""我的 LTI 预算 API：DEPT_HEAD 隔离 + 普通员工空集 + cycle 没绑 LTI plan 时空 targets。"""
import pytest
from datetime import date
from decimal import Decimal
from rest_framework.test import APIClient

from apps.iam.models import User, OrgUnit, OrgUnitManager
from apps.reward_cycle.models import RewardCycle
from apps.lti.models import LTIPlan, LTIBudgetCell


@pytest.fixture
def setup(db):
    plan = LTIPlan.objects.create(
        code="L_MY", name="my lti", grant_date=date(2026, 1, 1),
        total_shares=10000, unit_price_at_grant=Decimal("10.0"),
    )
    cycle = RewardCycle.objects.create(
        code="L_MY_C", name="c", period="2026", status="DRAFT",
        linked_lti_plan=plan,
    )
    d1 = OrgUnit.objects.create(code="LMD1", name="D1", type="DEPT")
    d2 = OrgUnit.objects.create(code="LMD2", name="D2", type="DEPT")
    LTIBudgetCell.objects.create(plan=plan, employee_category_1="STAFF", target_org_unit=d1, shares_quota_ads=1000)
    LTIBudgetCell.objects.create(plan=plan, employee_category_1="STAFF", target_org_unit=d2, shares_quota_ads=2000)
    return {"plan": plan, "cycle": cycle, "d1": d1, "d2": d2}


@pytest.mark.django_db
def test_dept_head_only_sees_own_dept_lti(setup):
    u = User.objects.create_user(email="ldh1@x.com", employee_no="LDH1", password="x")
    OrgUnitManager.objects.create(
        org_unit=setup["d1"], manager=u, role_in_unit="DEPT_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    c = APIClient()
    c.force_authenticate(u)
    r = c.get(f"/api/budgets/my-lti/?cycle_id={setup['cycle'].id}")
    assert r.status_code == 200
    targets = r.json()["targets"]
    assert len(targets) == 1
    assert targets[0]["target_org_unit_id"] == setup["d1"].id
    assert int(targets[0]["shares_quota_ads"]) == 1000


@pytest.mark.django_db
def test_unassigned_user_gets_empty_lti(setup):
    u = User.objects.create_user(email="lemp@x.com", employee_no="LMEMP", password="x")
    c = APIClient()
    c.force_authenticate(u)
    r = c.get(f"/api/budgets/my-lti/?cycle_id={setup['cycle'].id}")
    assert r.status_code == 200
    assert r.json()["targets"] == []


@pytest.mark.django_db
def test_cycle_without_lti_plan_returns_empty(db):
    cycle = RewardCycle.objects.create(code="NO_LTI", name="x", period="2026", status="DRAFT")
    u = User.objects.create_user(email="nlu@x.com", employee_no="NLU", password="x")
    c = APIClient()
    c.force_authenticate(u)
    r = c.get(f"/api/budgets/my-lti/?cycle_id={cycle.id}")
    assert r.status_code == 200
    assert r.json()["targets"] == []
