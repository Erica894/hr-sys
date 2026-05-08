import pytest
import pyotp
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentProposal
from apps.hr_master.models import CompensationRecord
from apps.lti.models import VestingEvent
from apps.reward_cycle.services import generate_proposals


@pytest.fixture
def ready_to_execute(db):
    call_command("seed_phase1")
    cycle = RewardCycle.objects.first()
    generate_proposals(cycle, cycle.linked_adjustment_plan, cycle.linked_lti_plan)
    hr = User.objects.get(email="hr@demo.com")
    hr.totp_secret = pyotp.random_base32()
    hr.mfa_enabled = True
    hr.save(update_fields=["totp_secret", "mfa_enabled"])

    p = AdjustmentProposal.objects.filter(plan=cycle.linked_adjustment_plan).first()
    p.annual_manager_delta_pct = "0.02"
    p.save()
    g = cycle.linked_lti_plan.grants.first()
    g.granted_ads = 100
    g.save()

    cycle.status = "APPROVED_PENDING_EXECUTE"
    cycle.save()
    return cycle, hr


def test_execute_creates_salary_record_and_vesting(ready_to_execute):
    cycle, hr = ready_to_execute
    c = APIClient()
    c.force_authenticate(hr)
    code = pyotp.TOTP(hr.totp_secret).now()
    r = c.post(f"/api/reward-cycle/{cycle.id}/execute/", HTTP_X_MFA_CODE=code)
    assert r.status_code == 200, r.data
    cycle.refresh_from_db()
    assert cycle.status == "EXECUTED"
    assert cycle.executed_at is not None
    # 5 employees get a new REWARD_CYCLE-sourced record
    assert CompensationRecord.objects.filter(source="REWARD_CYCLE").count() == 5
    # one grant (100 ads) → 5 vesting events
    assert VestingEvent.objects.filter(grant__granted_ads=100).count() == 5


def test_execute_without_mfa_rejected(ready_to_execute):
    cycle, hr = ready_to_execute
    c = APIClient()
    c.force_authenticate(hr)
    r = c.post(f"/api/reward-cycle/{cycle.id}/execute/")
    assert r.status_code == 403
