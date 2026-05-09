import pytest
from decimal import Decimal
from apps.iam.models import OrgUnit
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentBudgetCell


@pytest.mark.django_db
def test_budget_cell_can_attach_department():
    cycle = RewardCycle.objects.create(code="C2026", name="2026", period="2026", status="DRAFT")
    dept = OrgUnit.objects.create(code="D-ENG", name="工程部", type="DEPT")
    cell = AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=dept, budget_amount_cny=Decimal("100000"),
    )
    assert cell.department_id == dept.id


@pytest.mark.django_db
def test_budget_cell_company_total_has_null_department():
    cycle = RewardCycle.objects.create(code="C2026B", name="2026", period="2026", status="DRAFT")
    cell = AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=None, budget_amount_cny=Decimal("500000"),
    )
    assert cell.department is None


@pytest.mark.django_db
def test_unique_together_includes_department():
    cycle = RewardCycle.objects.create(code="C2026C", name="2026", period="2026", status="DRAFT")
    dept = OrgUnit.objects.create(code="D-FIN", name="财务部", type="DEPT")
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=dept, budget_amount_cny=Decimal("100"),
    )
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=None, budget_amount_cny=Decimal("100"),
    )
