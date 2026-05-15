import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentPlan, AdjustmentBudgetCell


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")


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


def test_anonymous_gets_401(seeded):
    c = APIClient()
    r = c.get("/api/admin/adjustment-plans/")
    assert r.status_code == 401


def test_non_hr_gets_403(alice):
    r = alice.get("/api/admin/adjustment-plans/")
    assert r.status_code == 403


def test_hr_can_list(hr):
    r = hr.get("/api/admin/adjustment-plans/")
    assert r.status_code == 200


def test_hr_can_create(hr):
    payload = {
        "code": "ADJ-2026-TEST",
        "name": "2026 测试调薪方案",
        "period": "2026",
        "status": "DRAFT",
        "formula": {"rule": "flat"},
        "rounding_rule": "ROUND_HALF_UP",
    }
    r = hr.post("/api/admin/adjustment-plans/", payload, format="json")
    assert r.status_code == 201, r.data
    assert r.data["code"] == "ADJ-2026-TEST"
    assert AdjustmentPlan.objects.filter(code="ADJ-2026-TEST").exists()
    # 默认 perf_grades 由模型默认值给出
    plan = AdjustmentPlan.objects.get(code="ADJ-2026-TEST")
    assert len(plan.perf_grades) == 5
    assert plan.perf_grades[0]["code"] == "STAR_5"


def test_hr_can_update(hr):
    plan = AdjustmentPlan.objects.create(code="ADJ-X", name="X", period="2026")
    r = hr.patch(f"/api/admin/adjustment-plans/{plan.id}/", {"name": "Y"}, format="json")
    assert r.status_code == 200, r.data
    plan.refresh_from_db()
    assert plan.name == "Y"


def test_hr_can_delete(hr):
    plan = AdjustmentPlan.objects.create(code="ADJ-DEL", name="del", period="2026")
    r = hr.delete(f"/api/admin/adjustment-plans/{plan.id}/")
    assert r.status_code == 204
    assert not AdjustmentPlan.objects.filter(id=plan.id).exists()


def test_budget_get_returns_four_cells(hr):
    cycle = RewardCycle.objects.first()
    r = hr.get(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/")
    assert r.status_code == 200
    assert len(r.data["rows"]) == 4
    types = {(row["adjustment_type"], row["employee_category_1"]) for row in r.data["rows"]}
    assert types == {
        ("ANNUAL", "MANAGEMENT"), ("ANNUAL", "STAFF"),
        ("PROMOTION", "MANAGEMENT"), ("PROMOTION", "STAFF"),
    }


def test_budget_put_updates_amount_and_remaining(hr):
    cycle = RewardCycle.objects.first()
    hr.get(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/")
    cell = AdjustmentBudgetCell.objects.get(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department__isnull=True,
    )
    cell.allocated_amount_cny = 50000
    cell.save(update_fields=["allocated_amount_cny"])
    payload = {
        "rows": [
            {"adjustment_type": "ANNUAL", "employee_category_1": "STAFF",
             "budget_amount_cny": "200000.00"},
        ]
    }
    r = hr.put(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/",
        payload, format="json",
    )
    assert r.status_code == 200, r.data
    updated = next(
        row for row in r.data["rows"]
        if row["adjustment_type"] == "ANNUAL" and row["employee_category_1"] == "STAFF"
    )
    assert updated["budget_amount_cny"] == "200000.00"
    assert updated["remaining_amount_cny"] == "150000.00"


def test_budget_put_rejects_bad_type(hr):
    cycle = RewardCycle.objects.first()
    r = hr.put(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/",
        {"rows": [{"adjustment_type": "BOGUS", "employee_category_1": "STAFF",
                   "budget_amount_cny": "1"}]},
        format="json",
    )
    assert r.status_code == 400
