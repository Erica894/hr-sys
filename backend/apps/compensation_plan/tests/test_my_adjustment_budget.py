"""我的调薪预算 API：DEPT_HEAD / CENTER_HEAD 隔离 + 普通员工空集。"""
import pytest
from datetime import date
from decimal import Decimal
from rest_framework.test import APIClient

from apps.iam.models import User, OrgUnit, OrgUnitManager
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentBudgetCell


@pytest.fixture
def setup(db):
    cycle = RewardCycle.objects.create(code="MY1", name="m", period="2026", status="DRAFT")
    d1 = OrgUnit.objects.create(code="D1", name="D1", type="DEPT")
    d2 = OrgUnit.objects.create(code="D2", name="D2", type="DEPT")
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=d1, budget_amount_cny=Decimal("100000"),
    )
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=d2, budget_amount_cny=Decimal("200000"),
    )
    return {"cycle": cycle, "d1": d1, "d2": d2}


@pytest.mark.django_db
def test_dept_head_only_sees_own_dept(setup):
    u = User.objects.create_user(email="dh1@x.com", employee_no="MDH1", password="x")
    OrgUnitManager.objects.create(
        org_unit=setup["d1"], manager=u, role_in_unit="DEPT_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    c = APIClient()
    c.force_authenticate(u)
    r = c.get(f"/api/budgets/my-adjustment/?cycle_id={setup['cycle'].id}")
    assert r.status_code == 200
    targets = r.json()["targets"]
    assert len(targets) == 1
    assert targets[0]["target_org_unit_id"] == setup["d1"].id
    assert targets[0]["budget_amount_cny"] == "100000.00"


@pytest.mark.django_db
def test_unassigned_user_gets_empty(setup):
    u = User.objects.create_user(email="emp@x.com", employee_no="MEMP1", password="x")
    c = APIClient()
    c.force_authenticate(u)
    r = c.get(f"/api/budgets/my-adjustment/?cycle_id={setup['cycle'].id}")
    assert r.status_code == 200
    assert r.json()["targets"] == []


@pytest.mark.django_db
def test_missing_cycle_id_returns_400(setup):
    u = User.objects.create_user(email="x2@x.com", employee_no="MX2", password="x")
    c = APIClient()
    c.force_authenticate(u)
    r = c.get("/api/budgets/my-adjustment/")
    assert r.status_code == 400
