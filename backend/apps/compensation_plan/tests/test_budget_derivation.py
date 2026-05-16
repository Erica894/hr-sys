"""派生预算 service + DerivedBudgetView 测试。

派生公式 (调薪预算口径=月度增量额, 不年化):
  amount = monthly_salary × base_pct × factor
"""
from decimal import Decimal
import pytest
from rest_framework.test import APIClient
from django.core.management import call_command

from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle
from apps.hr_master.models import (
    CategoryScheme,
    EmployeeCategory,
    EmployeeCategoryAssignment,
    Employee,
)
from apps.compensation_plan.models import (
    RegionalAdjustmentRule,
    EmployeeCategoryFactor,
)
from apps.compensation_plan.services.budget_derivation import derive_budget


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")
    cycle = RewardCycle.objects.get(code="RC-2026-01")
    if cycle.category_scheme is None:
        scheme, _ = CategoryScheme.objects.get_or_create(
            code="2026-default",
            defaults={"name": "2026 默认方案", "status": "ACTIVE"},
        )
        EmployeeCategory.objects.get_or_create(
            scheme=scheme, code="MGMT",
            defaults={"name": "管理干部", "sort_order": 0},
        )
        EmployeeCategory.objects.get_or_create(
            scheme=scheme, code="STAFF",
            defaults={"name": "员工", "sort_order": 1},
        )
        cycle.category_scheme = scheme
        cycle.save(update_fields=["category_scheme"])


@pytest.fixture
def cycle(seeded):
    return RewardCycle.objects.get(code="RC-2026-01")


@pytest.fixture
def scheme(cycle):
    return cycle.category_scheme


@pytest.fixture
def cat_mgmt(scheme):
    return scheme.categories.get(code="MGMT")


@pytest.fixture
def cat_staff(scheme):
    return scheme.categories.get(code="STAFF")


@pytest.fixture
def hr(seeded):
    c = APIClient()
    c.force_authenticate(User.objects.get(email="hr@demo.com"))
    return c


@pytest.fixture
def alice(seeded):
    c = APIClient()
    c.force_authenticate(User.objects.get(email="alice@demo.com"))
    return c


def _assign(scheme, employee_no, cat):
    """把员工 (E00x) 分类到 cat 桶。"""
    emp = Employee.objects.get(employee_no=employee_no)
    EmployeeCategoryAssignment.objects.update_or_create(
        employee=emp, scheme=scheme, defaults={"category": cat},
    )
    return emp


def _rule(cycle, country, adj_type, base_pct):
    return RegionalAdjustmentRule.objects.update_or_create(
        reward_cycle=cycle, country=country, adjustment_type=adj_type,
        defaults={"base_pct": Decimal(str(base_pct))},
    )[0]


def _factor(cycle, category, adj_type, factor):
    return EmployeeCategoryFactor.objects.update_or_create(
        reward_cycle=cycle, category=category, adjustment_type=adj_type,
        defaults={"factor": Decimal(str(factor))},
    )[0]


# ============ Permission ============

def test_anonymous_gets_401(seeded, cycle):
    c = APIClient()
    r = c.get(f"/api/admin/reward-cycles/{cycle.id}/derived-budget/")
    assert r.status_code == 401


def test_non_hr_gets_403(alice, cycle):
    r = alice.get(f"/api/admin/reward-cycles/{cycle.id}/derived-budget/")
    assert r.status_code == 403


# ============ Service ============

def test_empty_scheme_returns_no_rows(seeded, cycle):
    cycle.category_scheme = None
    cycle.save(update_fields=["category_scheme"])
    result = derive_budget(cycle)
    assert result["rows"] == []
    assert result["total_derived_cny"] == Decimal("0")


def test_single_employee_amount_no_x12(cycle, scheme, cat_mgmt):
    """alice E001: 月薪 50000, MGMT, CN, ANNUAL.
    base_pct=0.05, factor=1.2 → amount = 50000 × 0.05 × 1.2 = 3000 (月度，不乘 12)
    """
    _assign(scheme, "E001", cat_mgmt)
    _rule(cycle, "CN", "ANNUAL", "0.0500")
    _factor(cycle, cat_mgmt, "ANNUAL", "1.2000")

    result = derive_budget(cycle)
    annual_rows = [r for r in result["rows"] if r["adjustment_type"] == "ANNUAL"]
    assert len(annual_rows) == 1
    row = annual_rows[0]
    assert row["country"] == "CN"
    assert row["category_code"] == "MGMT"
    assert row["employee_count"] == 1
    assert row["derived_amount_cny"] == Decimal("3000.00")
    assert row["missing_rule"] is False
    assert row["missing_factor"] is False


def test_missing_rule_marks_bucket(cycle, scheme, cat_mgmt):
    """缺 RegionalAdjustmentRule → bucket missing_rule=True, amount=0, count 仍计入。"""
    _assign(scheme, "E001", cat_mgmt)
    _factor(cycle, cat_mgmt, "ANNUAL", "1.2000")
    # 没有 _rule(cycle, "CN", "ANNUAL", ...)

    result = derive_budget(cycle)
    annual = [r for r in result["rows"] if r["adjustment_type"] == "ANNUAL"]
    assert len(annual) == 1
    row = annual[0]
    assert row["missing_rule"] is True
    assert row["employee_count"] == 1
    assert row["derived_amount_cny"] == Decimal("0.00")


def test_promotion_only_for_promoted(cycle, scheme, cat_mgmt, cat_staff):
    """alice (MGMT, is_promoted=True) 进 PROMOTION; carol (MGMT, is_promoted=False) 不进。"""
    _assign(scheme, "E001", cat_mgmt)  # alice promoted
    _assign(scheme, "E003", cat_mgmt)  # carol NOT promoted
    _rule(cycle, "CN", "PROMOTION", "0.0800")
    _factor(cycle, cat_mgmt, "PROMOTION", "1.0000")

    result = derive_budget(cycle)
    promo = [r for r in result["rows"] if r["adjustment_type"] == "PROMOTION"]
    assert len(promo) == 1
    assert promo[0]["employee_count"] == 1  # 只有 alice
    # alice 月薪 50000 × 0.08 × 1.0 = 4000
    assert promo[0]["derived_amount_cny"] == Decimal("4000.00")


def test_opt_out_employee_excluded_from_annual(cycle, scheme, cat_staff):
    """participates_annual_adjustment=False 的员工不进 ANNUAL bucket。"""
    bob = Employee.objects.get(employee_no="E002")
    bob.participates_annual_adjustment = False
    bob.save(update_fields=["participates_annual_adjustment"])

    _assign(scheme, "E002", cat_staff)  # bob, opted out
    _assign(scheme, "E005", cat_staff)  # eve, opted in
    _rule(cycle, "CN", "ANNUAL", "0.0500")
    _factor(cycle, cat_staff, "ANNUAL", "1.0000")

    result = derive_budget(cycle)
    annual = [r for r in result["rows"] if r["adjustment_type"] == "ANNUAL"]
    assert len(annual) == 1
    assert annual[0]["employee_count"] == 1  # 只有 eve
    # eve 月薪 28000 × 0.05 × 1.0 = 1400
    assert annual[0]["derived_amount_cny"] == Decimal("1400.00")


# ============ Department dimension ============

def test_department_pool_sums_slices(cycle, scheme, cat_mgmt, cat_staff):
    """部门池金额 = 该部门下所有切片之和。E001/E002/E005 ∈ ENG, E003/E004 ∈ PROD。"""
    _assign(scheme, "E001", cat_mgmt)   # ENG MGMT, alice promoted
    _assign(scheme, "E002", cat_staff)  # ENG STAFF
    _assign(scheme, "E003", cat_mgmt)   # PROD MGMT, carol not promoted
    _assign(scheme, "E005", cat_staff)  # ENG STAFF, eve
    _rule(cycle, "CN", "ANNUAL", "0.0500")
    _factor(cycle, cat_mgmt, "ANNUAL", "1.2000")
    _factor(cycle, cat_staff, "ANNUAL", "1.0000")

    result = derive_budget(cycle)
    depts = {d["department_name"]: d for d in result["departments"]}
    assert "Engineering" in depts and "Product" in depts

    eng_slices_total = sum(
        r["derived_amount_cny"]
        for r in result["rows"] if r["department_name"] == "Engineering"
    )
    assert depts["Engineering"]["derived_annual_cny"] == eng_slices_total
    # ENG: alice (50000×0.05×1.2=3000) + bob (30000×0.05×1.0=1500) + eve (28000×0.05×1.0=1400) = 5900
    assert depts["Engineering"]["derived_annual_cny"] == Decimal("5900.00")
    assert depts["Engineering"]["effective_annual_cny"] == Decimal("5900.00")
    assert depts["Engineering"]["annual_source"] == "DERIVED"
    assert depts["Engineering"]["employee_count"] == 3
    assert depts["Product"]["employee_count"] == 1


def test_employee_without_org_unit_falls_into_unassigned_bucket(cycle, scheme, cat_staff):
    """org_unit=None 的员工进入 department_id=None 的"未分配部门"伪桶。"""
    bob = Employee.objects.get(employee_no="E002")
    bob.org_unit = None
    bob.save(update_fields=["org_unit"])

    _assign(scheme, "E002", cat_staff)
    _rule(cycle, "CN", "ANNUAL", "0.0500")
    _factor(cycle, cat_staff, "ANNUAL", "1.0000")

    result = derive_budget(cycle)
    unassigned = [d for d in result["departments"] if d["department_id"] is None]
    assert len(unassigned) == 1
    assert unassigned[0]["department_name"] == "未分配部门"
    assert unassigned[0]["employee_count"] == 1


# ============ 90/10 split (matrix vs discretionary) ============


def test_pool_split_default_90_10(cycle, scheme, cat_mgmt):
    """默认 discretionary_pct=0.10 → matrix=90%, discretionary=10%。"""
    _assign(scheme, "E001", cat_mgmt)
    _rule(cycle, "CN", "ANNUAL", "0.0500")
    _factor(cycle, cat_mgmt, "ANNUAL", "1.2000")
    # discretionary_pct 默认 0.1

    result = derive_budget(cycle)
    eng = next(d for d in result["departments"] if d["department_name"] == "Engineering")
    # ENG annual derived = 3000.00, no override → effective = 3000
    assert eng["effective_annual_cny"] == Decimal("3000.00")
    assert eng["matrix_annual_cny"] == Decimal("2700.00")
    assert eng["discretionary_annual_cny"] == Decimal("300.00")
    # PROMOTION 没规则 → 0
    assert eng["matrix_pool_cny"] == Decimal("2700.00")
    assert eng["discretionary_pool_cny"] == Decimal("300.00")
    # 部门和 = total
    assert (eng["matrix_pool_cny"] + eng["discretionary_pool_cny"]
            == eng["effective_total_cny"])

    assert result["discretionary_pct"] == Decimal("0.1000")
    assert result["total_matrix_cny"] == Decimal("2700.00")
    assert result["total_discretionary_cny"] == Decimal("300.00")


def test_pool_split_custom_pct(cycle, scheme, cat_mgmt):
    """周期上调 discretionary_pct=0.20 → matrix=80%, discretionary=20%。"""
    cycle.discretionary_pct = Decimal("0.2000")
    cycle.save(update_fields=["discretionary_pct"])
    _assign(scheme, "E001", cat_mgmt)
    _rule(cycle, "CN", "ANNUAL", "0.0500")
    _factor(cycle, cat_mgmt, "ANNUAL", "1.2000")

    result = derive_budget(cycle)
    eng = next(d for d in result["departments"] if d["department_name"] == "Engineering")
    assert eng["matrix_annual_cny"] == Decimal("2400.00")
    assert eng["discretionary_annual_cny"] == Decimal("600.00")


def test_pool_split_after_override(cycle, scheme, cat_mgmt, seeded):
    """Override 覆盖总池后, 90/10 应基于覆盖值重算。"""
    from apps.iam.models import OrgUnit
    from apps.compensation_plan.models import BudgetOverride

    _assign(scheme, "E001", cat_mgmt)
    _rule(cycle, "CN", "ANNUAL", "0.0500")
    _factor(cycle, cat_mgmt, "ANNUAL", "1.2000")
    eng = OrgUnit.objects.get(code="ENG")
    BudgetOverride.objects.create(
        reward_cycle=cycle, department=eng, adjustment_type="ANNUAL",
        override_amount_cny=Decimal("10000.00"), source="IMPORTED",
    )

    result = derive_budget(cycle)
    d = next(x for x in result["departments"] if x["department_name"] == "Engineering")
    assert d["effective_annual_cny"] == Decimal("10000.00")
    # 派生原值 3000 + 90/10 都应基于 10000 重算
    assert d["matrix_annual_cny"] == Decimal("9000.00")
    assert d["discretionary_annual_cny"] == Decimal("1000.00")


# ============ View ============

def test_view_returns_summary_fields(hr, cycle, scheme, cat_mgmt):
    _assign(scheme, "E001", cat_mgmt)
    _rule(cycle, "CN", "ANNUAL", "0.0500")
    _factor(cycle, cat_mgmt, "ANNUAL", "1.2000")

    r = hr.get(f"/api/admin/reward-cycles/{cycle.id}/derived-budget/")
    assert r.status_code == 200, r.data
    body = r.data
    assert body["cycle_code"] == "RC-2026-01"
    assert "rows" in body
    assert "departments" in body
    assert "total_derived_cny" in body
    assert body["employee_total"] == 1
    annual = [row for row in body["rows"] if row["adjustment_type"] == "ANNUAL"]
    assert annual and annual[0]["derived_amount_cny"] == "3000.00"
    assert annual[0]["department_name"] == "Engineering"
    eng = [d for d in body["departments"] if d["department_name"] == "Engineering"]
    assert eng and eng[0]["derived_annual_cny"] == "3000.00"
    assert eng[0]["effective_annual_cny"] == "3000.00"
    assert eng[0]["annual_source"] == "DERIVED"
    assert eng[0]["matrix_pool_cny"] == "2700.00"
    assert eng[0]["discretionary_pool_cny"] == "300.00"
    assert body["total_matrix_cny"] == "2700.00"
    assert body["total_discretionary_cny"] == "300.00"
