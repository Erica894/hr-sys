"""年终奖 cap_check 硬约束测试。"""
from decimal import Decimal
import pytest
from django.core.management import call_command

from apps.iam.models import OrgUnit
from apps.reward_cycle.models import RewardCycle
from apps.hr_master.models import Employee
from apps.bonus_pool.models import (
    BonusBudgetCell,
    BonusPlan,
    BonusProposal,
)
from apps.compensation_plan.services.cap_check import check_bonus_cap


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")


@pytest.fixture
def cycle(seeded):
    return RewardCycle.objects.get(code="RC-2026-01")


@pytest.fixture
def plan(cycle):
    p = BonusPlan.objects.create(
        code="BP-TEST", name="测试年终奖", period="2026", reward_cycle=cycle,
    )
    cycle.linked_bonus_plan = p
    cycle.save(update_fields=["linked_bonus_plan"])
    return p


def test_no_plan_returns_empty(cycle):
    cycle.linked_bonus_plan = None
    cycle.save(update_fields=["linked_bonus_plan"])
    assert check_bonus_cap(cycle, []) == []


def test_within_target_budget_no_violations(cycle, plan):
    alice = Employee.objects.get(employee_no="E001")
    dept = alice.org_unit
    # 沿 parent 找到 DEPT 节点
    while dept and dept.type != "DEPT":
        dept = dept.parent
    assert dept is not None

    BonusBudgetCell.objects.create(
        reward_cycle=cycle, employee_category_1="MANAGEMENT",
        target_org_unit=dept, budget_amount_cny=Decimal("100000"),
    )
    BonusProposal.objects.create(
        plan=plan, employee=alice,
        suggested_amount_cny=Decimal("50000"),
        manager_delta_amount_cny=Decimal("0"),
        employee_category_1_snapshot="MANAGEMENT",
    )
    violations = check_bonus_cap(cycle, [])
    assert violations == []


def test_exceeding_budget_returns_violation(cycle, plan):
    alice = Employee.objects.get(employee_no="E001")
    dept = alice.org_unit
    while dept and dept.type != "DEPT":
        dept = dept.parent
    assert dept is not None

    BonusBudgetCell.objects.create(
        reward_cycle=cycle, employee_category_1="MANAGEMENT",
        target_org_unit=dept, budget_amount_cny=Decimal("10000"),
    )
    BonusProposal.objects.create(
        plan=plan, employee=alice,
        suggested_amount_cny=Decimal("8000"),
        manager_delta_amount_cny=Decimal("0"),
        employee_category_1_snapshot="MANAGEMENT",
    )
    # 经理把 delta 提到 +5000 → total=13000 > 10000
    violations = check_bonus_cap(
        cycle,
        [{"employee_id": alice.id, "bonus_manager_delta_amount_cny": "5000"}],
    )
    assert len(violations) == 1
    v = violations[0]
    assert v["level"] == "TARGET"
    assert v["subject"] == "BONUS"
    assert v["target_org_unit_id"] == dept.id
    assert v["employee_category_1"] == "MANAGEMENT"


def test_company_layer_fallback_when_no_targets(cycle, plan):
    """没有目标层 cell 时，回退到公司层 cell 校验。"""
    alice = Employee.objects.get(employee_no="E001")
    BonusBudgetCell.objects.create(
        reward_cycle=cycle, employee_category_1="MANAGEMENT",
        target_org_unit=None, budget_amount_cny=Decimal("10000"),
    )
    BonusProposal.objects.create(
        plan=plan, employee=alice,
        suggested_amount_cny=Decimal("12000"),
        manager_delta_amount_cny=Decimal("0"),
        employee_category_1_snapshot="MANAGEMENT",
    )
    violations = check_bonus_cap(cycle, [])
    assert len(violations) == 1
    assert violations[0]["level"] == "COMPANY"
    assert violations[0]["subject"] == "BONUS"
