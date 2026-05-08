import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")


def _client(email):
    c = APIClient()
    c.force_authenticate(User.objects.get(email=email))
    return c


def test_submit_then_two_approvals_flip_cycle_to_approved(seeded):
    cycle = RewardCycle.objects.first()
    hr = _client("hr@demo.com")
    hr.get(f"/api/reward-cycle/{cycle.id}/allocation/")
    hr.patch(f"/api/reward-cycle/{cycle.id}/proposals/", {"items": []}, format="json")
    r = hr.post(f"/api/reward-cycle/{cycle.id}/submit/")
    assert r.status_code == 200
    inst_id = r.data["instance_id"]

    dept = _client("depthead@demo.com")
    r = dept.post(
        f"/api/approval/{inst_id}/action/",
        {"action": "APPROVE", "comment": "ok"}, format="json",
    )
    assert r.data["current_step"] == 2
    assert r.data["status"] == "RUNNING"

    r = hr.post(
        f"/api/approval/{inst_id}/action/",
        {"action": "APPROVE", "comment": "final"}, format="json",
    )
    assert r.data["status"] == "APPROVED"

    cycle.refresh_from_db()
    assert cycle.status == "APPROVED_PENDING_EXECUTE"
