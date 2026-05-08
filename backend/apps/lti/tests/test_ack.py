import pytest
import pyotp
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle
from apps.reward_cycle.execute import execute_reward_cycle
from apps.reward_cycle.services import generate_proposals
from apps.lti.models import EmployeeAck


@pytest.fixture
def executed_cycle(db):
    call_command("seed_phase1")
    cycle = RewardCycle.objects.first()
    generate_proposals(cycle, cycle.linked_adjustment_plan, cycle.linked_lti_plan)
    cycle.status = "APPROVED_PENDING_EXECUTE"
    cycle.save()
    hr = User.objects.get(email="hr@demo.com")
    hr.totp_secret = pyotp.random_base32()
    hr.mfa_enabled = True
    hr.save(update_fields=["totp_secret", "mfa_enabled"])
    execute_reward_cycle(cycle, hr)
    cycle.refresh_from_db()
    return cycle


def test_employee_sees_own_proposal_and_acks(executed_cycle):
    cycle = executed_cycle
    assert cycle.status == "EXECUTED"
    u = User.objects.get(email="alice@demo.com")
    c = APIClient()
    c.force_authenticate(u)

    r = c.get(f"/api/reward-cycle/{cycle.id}/my-proposal/")
    assert r.status_code == 200, r.data
    assert r.data["cycle_code"] == cycle.code
    assert r.data["ack_status"] == "PENDING"

    r2 = c.post(
        f"/api/reward-cycle/{cycle.id}/ack/",
        {"comment": "confirmed"}, format="json",
    )
    assert r2.status_code == 200
    assert r2.data["status"] == "ACKNOWLEDGED"

    r3 = c.get(f"/api/reward-cycle/{cycle.id}/my-proposal/")
    assert r3.data["ack_status"] == "ACKNOWLEDGED"
    assert EmployeeAck.objects.filter(
        subject_type="REWARD_CYCLE", subject_id=cycle.id
    ).count() == 1


def test_ack_idempotent(executed_cycle):
    cycle = executed_cycle
    u = User.objects.get(email="bob@demo.com")
    c = APIClient()
    c.force_authenticate(u)
    c.post(f"/api/reward-cycle/{cycle.id}/ack/")
    c.post(f"/api/reward-cycle/{cycle.id}/ack/")
    assert EmployeeAck.objects.filter(
        subject_type="REWARD_CYCLE", subject_id=cycle.id,
        employee__user=u,
    ).count() == 1


def test_non_employee_rejected(executed_cycle):
    cycle = executed_cycle
    hr = User.objects.get(email="hr@demo.com")
    c = APIClient()
    c.force_authenticate(hr)
    r = c.get(f"/api/reward-cycle/{cycle.id}/my-proposal/")
    assert r.status_code == 404
