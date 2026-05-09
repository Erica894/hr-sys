import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.lti.models import LTIPlan, LTIBudgetCell


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
    assert c.get("/api/admin/lti-plans/").status_code == 401


def test_non_hr_gets_403(alice):
    assert alice.get("/api/admin/lti-plans/").status_code == 403


def test_hr_can_list(hr):
    assert hr.get("/api/admin/lti-plans/").status_code == 200


def test_hr_can_create(hr):
    payload = {
        "code": "LTI-2026-TEST",
        "name": "2026 RSU test",
        "grant_date": "2026-06-01",
        "total_shares": 10000,
        "share_unit": "ADS",
        "unit_price_at_grant": "25.5000",
        "vesting_schedule": {"y1": 0.25, "y2": 0.25, "y3": 0.25, "y4": 0.25},
        "cliff_months": 12,
        "stock_code": "TEST",
    }
    r = hr.post("/api/admin/lti-plans/", payload, format="json")
    assert r.status_code == 201, r.data
    assert LTIPlan.objects.filter(code="LTI-2026-TEST").exists()


def test_hr_can_update_and_delete(hr):
    plan = LTIPlan.objects.create(
        code="LTI-X", name="X", grant_date="2026-06-01",
        unit_price_at_grant=10,
    )
    r = hr.patch(f"/api/admin/lti-plans/{plan.id}/", {"name": "Y"}, format="json")
    assert r.status_code == 200
    plan.refresh_from_db()
    assert plan.name == "Y"
    r2 = hr.delete(f"/api/admin/lti-plans/{plan.id}/")
    assert r2.status_code == 204


def test_budget_get_returns_two_cells(hr):
    plan = LTIPlan.objects.create(
        code="LTI-B", name="B", grant_date="2026-06-01", unit_price_at_grant=10,
    )
    r = hr.get(f"/api/admin/lti-plans/{plan.id}/budget/")
    assert r.status_code == 200
    assert len(r.data["rows"]) == 2
    cats = {row["employee_category_1"] for row in r.data["rows"]}
    assert cats == {"MANAGEMENT", "STAFF"}


def test_budget_put_updates_quota(hr):
    plan = LTIPlan.objects.create(
        code="LTI-C", name="C", grant_date="2026-06-01", unit_price_at_grant=10,
    )
    hr.get(f"/api/admin/lti-plans/{plan.id}/budget/")
    r = hr.put(
        f"/api/admin/lti-plans/{plan.id}/budget/",
        {"rows": [
            {"employee_category_1": "MANAGEMENT", "headcount_quota": 5, "shares_quota_ads": 10000},
            {"employee_category_1": "STAFF", "headcount_quota": 20, "shares_quota_ads": 40000},
        ]},
        format="json",
    )
    assert r.status_code == 200, r.data
    mgmt = LTIBudgetCell.objects.get(plan=plan, employee_category_1="MANAGEMENT")
    assert mgmt.headcount_quota == 5
    assert mgmt.shares_quota_ads == 10000
