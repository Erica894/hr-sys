"""EXECUTE 后目标层 cell 的 allocated/reclaim 固化（核算用）。"""
import pytest
from datetime import date
from decimal import Decimal

from apps.iam.models import User, OrgUnit
from apps.hr_master.models import Employee
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import (
    AdjustmentPlan, AdjustmentProposal, AdjustmentBudgetCell,
)
from apps.lti.models import LTIPlan, LTIBudgetCell, LTIGrant
from apps.reward_cycle.execute import execute_reward_cycle


@pytest.fixture
def actor(db):
    return User.objects.create_user(email="exec_actor@x.com", employee_no="EXACT", password="x")


@pytest.mark.django_db
def test_execute_finalizes_adjustment_reclaim(actor):
    dept = OrgUnit.objects.create(code="EXD", name="D", type="DEPT")
    plan = AdjustmentPlan.objects.create(code="EXP", name="exp", period="2026", status="DRAFT")
    cycle = RewardCycle.objects.create(
        code="EXC", name="c", period="2026", status="APPROVED_PENDING_EXECUTE",
        linked_adjustment_plan=plan,
    )
    e = Employee.objects.create(
        employee_no="EX1", name_cn="ex1", org_unit=dept,
        employee_category_1="STAFF", status="ACTIVE", hire_date=date(2026, 1, 1),
    )
    AdjustmentProposal.objects.create(
        plan=plan, employee=e, current_salary=Decimal("10000"),
        annual_suggested_pct=Decimal("0.05"),
        annual_manager_delta_pct=Decimal("0"),
        employee_category_1_snapshot="STAFF",
    )
    cell = AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=dept, budget_amount_cny=Decimal("10000"),
    )

    execute_reward_cycle(cycle, actor)
    cell.refresh_from_db()
    # allocated = 10000 × 0.05 × 12 = 6000
    assert cell.allocated_amount_cny == Decimal("6000.00")
    assert cell.reclaimed_amount_cny == Decimal("4000.00")


@pytest.mark.django_db
def test_execute_finalizes_lti_reclaim(actor):
    dept = OrgUnit.objects.create(code="EXLD", name="LD", type="DEPT")
    lti = LTIPlan.objects.create(
        code="EXL", name="exl", grant_date=date(2026, 1, 1),
        total_shares=10000, unit_price_at_grant=Decimal("10.0"),
    )
    cycle = RewardCycle.objects.create(
        code="EXLC", name="c", period="2026", status="APPROVED_PENDING_EXECUTE",
        linked_lti_plan=lti,
    )
    e = Employee.objects.create(
        employee_no="EXL1", name_cn="exl1", org_unit=dept,
        employee_category_1="STAFF", status="ACTIVE", hire_date=date(2026, 1, 1),
    )
    LTIGrant.objects.create(
        plan=lti, employee=e, granted_ads=300,
        employee_category_1_snapshot="STAFF",
    )
    cell = LTIBudgetCell.objects.create(
        plan=lti, employee_category_1="STAFF",
        target_org_unit=dept, shares_quota_ads=1000,
    )

    execute_reward_cycle(cycle, actor)
    cell.refresh_from_db()
    assert cell.shares_used_ads == 300
    assert cell.reclaimed_shares_ads == 700
