"""Bonus budget admin API：GET/PUT 公司层、distribute、targets PATCH。"""
import pytest
from decimal import Decimal
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.iam.models import User, OrgUnit
from apps.reward_cycle.models import RewardCycle
from apps.bonus_pool.models import BonusPlan, BonusBudgetCell


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")


@pytest.fixture
def hr(seeded):
    return User.objects.get(email="hr@demo.com")


@pytest.fixture
def cycle(seeded):
    return RewardCycle.objects.get(code="RC-2026-01")


@pytest.fixture
def plan(cycle):
    p = BonusPlan.objects.create(code="BAB", name="bab", period="2026")
    cycle.linked_bonus_plan = p
    cycle.save(update_fields=["linked_bonus_plan"])
    return p


def test_bonus_budget_get_creates_company_cells(hr, cycle, plan):
    c = APIClient()
    c.force_authenticate(hr)
    r = c.get(f"/api/admin/reward-cycles/{cycle.id}/bonus-budget/")
    assert r.status_code == 200
    rows = r.data["company"]
    assert {x["employee_category_1"] for x in rows} == {"MANAGEMENT", "STAFF"}


def test_bonus_budget_put_sets_company_amount(hr, cycle, plan):
    c = APIClient()
    c.force_authenticate(hr)
    r = c.put(
        f"/api/admin/reward-cycles/{cycle.id}/bonus-budget/",
        {"rows": [{"employee_category_1": "STAFF", "budget_amount_cny": "100000"}]},
        format="json",
    )
    assert r.status_code == 200
    cell = BonusBudgetCell.objects.get(
        reward_cycle=cycle, employee_category_1="STAFF", target_org_unit__isnull=True,
    )
    assert cell.budget_amount_cny == Decimal("100000.00")


def test_bonus_budget_distribute_manual(hr, cycle, plan):
    dept = OrgUnit.objects.create(code="BD1", name="D", type="DEPT")
    BonusBudgetCell.objects.update_or_create(
        reward_cycle=cycle, employee_category_1="STAFF", target_org_unit=None,
        defaults={"budget_amount_cny": Decimal("80000")},
    )
    c = APIClient()
    c.force_authenticate(hr)
    r = c.post(
        f"/api/admin/reward-cycles/{cycle.id}/bonus-budget/distribute/",
        {
            "employee_category_1": "STAFF",
            "mode": "MANUAL",
            "target_org_unit_ids": [dept.id],
            "manual_amounts": {str(dept.id): "80000"},
        },
        format="json",
    )
    assert r.status_code == 200, r.data
    cell = BonusBudgetCell.objects.get(
        reward_cycle=cycle, employee_category_1="STAFF", target_org_unit=dept,
    )
    assert cell.budget_amount_cny == Decimal("80000.00")


def test_bonus_derived_budget_endpoint_returns_shape(hr, cycle, plan):
    c = APIClient()
    c.force_authenticate(hr)
    r = c.get(f"/api/admin/reward-cycles/{cycle.id}/bonus-derived-budget/")
    assert r.status_code == 200
    assert "departments" in r.data
    assert "rows" in r.data
    assert "total_derived_cny" in r.data
