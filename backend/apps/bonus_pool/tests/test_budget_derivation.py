"""年终奖派生预算 service 测试。

派生公式 (年终奖口径):
  amount = monthly_salary × base_months × factor
"""
from decimal import Decimal
import pytest
from django.core.management import call_command

from apps.reward_cycle.models import RewardCycle
from apps.hr_master.models import Employee
from apps.bonus_pool.models import (
    BonusBudgetOverride,
    BonusCategoryFactor,
    RegionalBonusRule,
)
from apps.bonus_pool.services.budget_derivation import derive_bonus_budget


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")


@pytest.fixture
def cycle(seeded):
    return RewardCycle.objects.get(code="RC-2026-01")


def _rule(cycle, country, base_months):
    return RegionalBonusRule.objects.update_or_create(
        reward_cycle=cycle, country=country,
        defaults={"base_months": Decimal(str(base_months))},
    )[0]


def _factor(cycle, cat1, factor):
    return BonusCategoryFactor.objects.update_or_create(
        reward_cycle=cycle, employee_category_1=cat1,
        defaults={"factor": Decimal(str(factor))},
    )[0]


def test_single_employee_amount(cycle):
    """alice E001 月薪 50000 MGMT CN, base=1.5, factor=1.2 → 50000×1.5×1.2 = 90000"""
    _rule(cycle, "CN", "1.5")
    _factor(cycle, "MANAGEMENT", "1.2")

    result = derive_bonus_budget(cycle)
    rows = [r for r in result["rows"] if r["employee_category_1"] == "MANAGEMENT" and r["country"] == "CN"]
    assert len(rows) >= 1
    # alice 应该在其中
    total_mgmt_cn = sum(r["derived_amount_cny"] for r in rows)
    # 至少包含 alice 的 90000
    assert total_mgmt_cn >= Decimal("90000.00")


def test_missing_rule_marks_bucket(cycle):
    """缺 RegionalBonusRule → bucket missing_rule=True, amount=0, count 仍计入。"""
    _factor(cycle, "MANAGEMENT", "1.2")
    # 不配 CN rule

    result = derive_bonus_budget(cycle)
    cn_rows = [r for r in result["rows"] if r["country"] == "CN"]
    assert len(cn_rows) > 0
    for r in cn_rows:
        assert r["missing_rule"] is True
        assert r["derived_amount_cny"] == Decimal("0.00")
        assert r["employee_count"] >= 1


def test_missing_factor_marks_bucket(cycle):
    """缺 BonusCategoryFactor → bucket missing_factor=True, amount=0。"""
    _rule(cycle, "CN", "1.5")
    # 不配 MANAGEMENT factor

    result = derive_bonus_budget(cycle)
    mgmt_rows = [r for r in result["rows"] if r["employee_category_1"] == "MANAGEMENT"]
    assert len(mgmt_rows) > 0
    for r in mgmt_rows:
        assert r["missing_factor"] is True
        assert r["derived_amount_cny"] == Decimal("0.00")


def test_inactive_employee_excluded(cycle):
    """status != ACTIVE 的员工不计入。"""
    _rule(cycle, "CN", "1.5")
    _factor(cycle, "STAFF", "1.0")
    _factor(cycle, "MANAGEMENT", "1.0")

    baseline = derive_bonus_budget(cycle)
    baseline_total = baseline["employee_total"]

    bob = Employee.objects.get(employee_no="E002")
    bob.status = "INACTIVE"
    bob.save(update_fields=["status"])

    result = derive_bonus_budget(cycle)
    assert result["employee_total"] == baseline_total - 1


def test_department_pool_sums_slices(cycle):
    """部门池金额 = 该部门下所有切片之和。"""
    _rule(cycle, "CN", "1.5")
    _factor(cycle, "MANAGEMENT", "1.0")
    _factor(cycle, "STAFF", "1.0")

    result = derive_bonus_budget(cycle)
    for d in result["departments"]:
        if d["department_id"] is None:
            continue
        # 派生金额应为该部门所有切片之和
        slices_sum = sum(
            r["derived_amount_cny"] for r in result["rows"]
            if r["department_id"] == d["department_id"]
        )
        assert d["derived_amount_cny"] == slices_sum.quantize(Decimal("0.01"))


def test_override_replaces_derived_for_department(cycle):
    """BonusBudgetOverride 存在 → effective_amount_cny = override, source=IMPORTED。"""
    from apps.iam.models import OrgUnit
    _rule(cycle, "CN", "1.5")
    _factor(cycle, "MANAGEMENT", "1.0")
    _factor(cycle, "STAFF", "1.0")

    baseline = derive_bonus_budget(cycle)
    target_dept = next(
        (d for d in baseline["departments"]
         if d["department_id"] is not None and d["derived_amount_cny"] > 0),
        None,
    )
    assert target_dept is not None
    dept = OrgUnit.objects.get(id=target_dept["department_id"])

    BonusBudgetOverride.objects.create(
        reward_cycle=cycle, department=dept,
        override_amount_cny=Decimal("999999.00"), source="IMPORTED",
    )

    result = derive_bonus_budget(cycle)
    overridden = next(
        d for d in result["departments"] if d["department_id"] == dept.id
    )
    assert overridden["override_amount_cny"] == Decimal("999999.00")
    assert overridden["effective_amount_cny"] == Decimal("999999.00")
    assert overridden["source"] == "IMPORTED"
