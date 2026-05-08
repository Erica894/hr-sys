import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentProposal


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")


@pytest.fixture
def client(seeded):
    u = User.objects.get(email="hr@demo.com")
    c = APIClient()
    c.force_authenticate(u)
    return c


def test_allocation_list_returns_5_rows(client):
    cycle = RewardCycle.objects.first()
    r = client.get(f"/api/reward-cycle/{cycle.id}/allocation/")
    assert r.status_code == 200
    assert len(r.data["rows"]) == 5
    assert "total_comp" in r.data["rows"][0]


def test_save_proposals_updates_manager_delta(client):
    cycle = RewardCycle.objects.first()
    client.get(f"/api/reward-cycle/{cycle.id}/allocation/")
    emp_id = cycle.linked_adjustment_plan.proposals.first().employee_id
    r = client.patch(
        f"/api/reward-cycle/{cycle.id}/proposals/",
        {"items": [{"employee_id": emp_id, "annual_manager_delta_pct": "0.02"}]},
        format="json",
    )
    assert r.status_code == 200
    p = AdjustmentProposal.objects.get(plan=cycle.linked_adjustment_plan, employee_id=emp_id)
    assert str(p.annual_manager_delta_pct) == "0.0200"
