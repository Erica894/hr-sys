"""Full phase-1 happy path exercised via API in a single pytest."""
import pyotp
import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from django.db import connection
from apps.iam.models import User
from apps.iam.services import generate_totp_secret
from apps.reward_cycle.models import RewardCycle


@pytest.fixture
def stack(db):
    call_command("seed_phase1")
    hr = User.objects.get(email="hr@demo.com")
    hr.totp_secret = generate_totp_secret()
    hr.mfa_enabled = True
    hr.save(update_fields=["totp_secret", "mfa_enabled"])
    return hr


def _c(email):
    c = APIClient()
    c.force_authenticate(User.objects.get(email=email))
    return c


def test_phase1_end_to_end(stack):
    hr_user = stack
    hr = _c("hr@demo.com")
    dept = _c("depthead@demo.com")

    cycle = RewardCycle.objects.first()
    cid = cycle.id

    # 1. Allocation list has 5 rows (triggers generate_proposals on DRAFT)
    r = hr.get(f"/api/reward-cycle/{cid}/allocation/")
    assert r.status_code == 200, r.data
    assert len(r.data["rows"]) == 5

    # 2. HR edits Alice: manager_delta=0.02, granted_ads=200
    alice_row = next(row for row in r.data["rows"] if row.get("name_cn") or row.get("employee_code"))
    alice_emp_id = alice_row["employee_id"]
    r2 = hr.patch(
        f"/api/reward-cycle/{cid}/proposals/",
        {"items": [{
            "employee_id": alice_emp_id,
            "annual_manager_delta_pct": "0.02",
            "granted_ads": 200,
        }]},
        format="json",
    )
    assert r2.status_code == 200, r2.data

    # 3. Submit
    r3 = hr.post(f"/api/reward-cycle/{cid}/submit/")
    assert r3.status_code == 200, r3.data
    inst_id = r3.data["instance_id"]

    # 4. Dept head approves step 1
    r4 = dept.post(
        f"/api/approval/{inst_id}/action/",
        {"action": "APPROVE", "comment": "ok from dept"},
        format="json",
    )
    assert r4.status_code == 200, r4.data
    assert r4.data["current_step"] == 2

    # 5. HR approves step 2
    r5 = hr.post(
        f"/api/approval/{inst_id}/action/",
        {"action": "APPROVE", "comment": "final"},
        format="json",
    )
    assert r5.status_code == 200, r5.data
    assert r5.data["status"] == "APPROVED"

    # 6. Cycle now APPROVED_PENDING_EXECUTE
    cycle.refresh_from_db()
    assert cycle.status == "APPROVED_PENDING_EXECUTE"

    # 7. HR executes with MFA
    code = pyotp.TOTP(hr_user.totp_secret).now()
    r7 = hr.post(f"/api/reward-cycle/{cid}/execute/", HTTP_X_MFA_CODE=code)
    assert r7.status_code == 200, r7.data
    cycle.refresh_from_db()
    assert cycle.status == "EXECUTED"

    # 8. Alice views own proposal, PENDING, 200 ADS
    alice = _c("alice@demo.com")
    r8 = alice.get(f"/api/reward-cycle/{cid}/my-proposal/")
    assert r8.status_code == 200, r8.data
    assert r8.data["ack_status"] == "PENDING"
    assert r8.data["granted_ads"] == 200

    # 9. Alice acknowledges
    r9 = alice.post(f"/api/reward-cycle/{cid}/ack/", {"comment": "ok"}, format="json")
    assert r9.status_code == 200, r9.data

    # 10. Ack status now ACKNOWLEDGED
    r10 = alice.get(f"/api/reward-cycle/{cid}/my-proposal/")
    assert r10.data["ack_status"] == "ACKNOWLEDGED"

    # 11. Audit log contains SUBMIT, APPROVE, EXECUTE, ACK
    with connection.cursor() as c:
        c.execute("SELECT action FROM audit.audit_log ORDER BY id")
        actions = [row[0] for row in c.fetchall()]
    for a in ["SUBMIT", "APPROVE", "EXECUTE", "ACK"]:
        assert a in actions, f"missing {a} in audit log (got {actions})"
