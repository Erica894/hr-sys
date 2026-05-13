"""E2E：HR 设公司池 → HEADCOUNT 下发部门 → DEPT_HEAD 超额拒 / 改回过 → 提交 → 审批 → 执行 → reclaim 固化。"""
import pytest
import pyotp
from decimal import Decimal
from rest_framework.test import APIClient
from django.core.management import call_command

from apps.iam.models import User, OrgUnit, OrgUnitManager
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentBudgetCell, AdjustmentProposal
from apps.lti.models import LTIBudgetCell


def _client(email):
    c = APIClient()
    c.force_authenticate(User.objects.get(email=email))
    return c


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")


@pytest.mark.django_db
def test_full_flow_with_two_level_distribution_and_reclaim(seeded):
    cycle = RewardCycle.objects.first()
    eng = OrgUnit.objects.get(code="ENG")
    prod = OrgUnit.objects.get(code="PROD")

    # depthead@demo.com 在 seed 里挂 UserRole.scope_ref_id=eng；这里再补一条 OrgUnitManager 让 cap 校验能定位 ENG
    dh_user = User.objects.get(email="depthead@demo.com")
    OrgUnitManager.objects.get_or_create(
        org_unit=eng, manager=dh_user, role_in_unit="DEPT_HEAD",
        defaults={"is_primary": True, "effective_from": "2026-01-01"},
    )

    hr = _client("hr@demo.com")
    dept = _client("depthead@demo.com")

    # 1) HR 把 STAFF 池 125000 按 HEADCOUNT 切到 ENG / PROD
    r = hr.post(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/distribute/",
        {
            "adjustment_type": "ANNUAL", "employee_category_1": "STAFF",
            "mode": "HEADCOUNT", "target_org_unit_ids": [eng.id, prod.id],
        }, format="json",
    )
    assert r.status_code == 200, r.json()
    by_dept = {
        c.department_id: c.budget_amount_cny
        for c in AdjustmentBudgetCell.objects.filter(
            reward_cycle=cycle, adjustment_type="ANNUAL",
            employee_category_1="STAFF", department__isnull=False,
        )
    }
    # ENG 有 bob+eve，PROD 有 david → 2:1 切分（含舍入兜底）
    assert by_dept[eng.id] + by_dept[prod.id] == Decimal("125000.00")
    assert by_dept[eng.id] > by_dept[prod.id]

    # 2) HR 把 LTI STAFF 池 25000 ADS 按 HEADCOUNT 切到 ENG / PROD
    lti_plan = cycle.linked_lti_plan
    r = hr.post(
        f"/api/admin/lti-plans/{lti_plan.id}/budget/distribute/",
        {
            "employee_category_1": "STAFF", "mode": "HEADCOUNT",
            "target_org_unit_ids": [eng.id, prod.id],
        }, format="json",
    )
    assert r.status_code == 200, r.json()
    lti_by_ou = {
        c.target_org_unit_id: int(c.shares_quota_ads)
        for c in LTIBudgetCell.objects.filter(
            plan=lti_plan, employee_category_1="STAFF", target_org_unit__isnull=False,
        )
    }
    assert lti_by_ou[eng.id] + lti_by_ou[prod.id] == 25000

    # 3) Allocation: 在 DRAFT 触发 generate_proposals，再切到 ALLOCATING
    hr.get(f"/api/reward-cycle/{cycle.id}/allocation/")
    cycle.refresh_from_db()
    if cycle.status == "DRAFT":
        cycle.status = "ALLOCATING"
        cycle.save(update_fields=["status"])

    bob = User.objects.get(email="bob@demo.com").employee
    # 4) DEPT_HEAD 把 bob delta 拉到一个肯定超 ENG STAFF 池的值
    eng_staff_budget = by_dept[eng.id]  # ≈ 83333.33
    # bob 月薪 30000，annual_suggested=0.05 → suggested 18000；想超 ENG 池只需把 delta 拉得足够大
    big_delta = "0.50"  # → 30000 × (0.05+0.5) × 12 = 198000，远超 83333
    r = dept.patch(
        f"/api/reward-cycle/{cycle.id}/proposals/",
        {"items": [{"employee_id": bob.id, "annual_manager_delta_pct": big_delta}]},
        format="json",
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "BUDGET_EXCEEDED"
    target_violations = [v for v in body["violations"] if v.get("level") == "TARGET"]
    assert any(v["target_org_unit_id"] == eng.id for v in target_violations)

    # 5) 改回一个肯定不超 ENG STAFF 池的值
    small_delta = "0.01"
    r = dept.patch(
        f"/api/reward-cycle/{cycle.id}/proposals/",
        {"items": [{"employee_id": bob.id, "annual_manager_delta_pct": small_delta}]},
        format="json",
    )
    assert r.status_code == 200, r.json()

    # 6) 提交 + 审批：DEPT_HEAD APPROVE → HR APPROVE
    r = hr.post(f"/api/reward-cycle/{cycle.id}/submit/")
    assert r.status_code == 200, r.data
    inst_id = r.data["instance_id"]

    r = dept.post(
        f"/api/approval/{inst_id}/action/",
        {"action": "APPROVE", "comment": "ok"}, format="json",
    )
    assert r.data["status"] == "RUNNING"
    r = hr.post(
        f"/api/approval/{inst_id}/action/",
        {"action": "APPROVE", "comment": "final"}, format="json",
    )
    assert r.data["status"] == "APPROVED"
    cycle.refresh_from_db()
    assert cycle.status == "APPROVED_PENDING_EXECUTE"

    # 7) 执行（启 MFA）
    hr_user = User.objects.get(email="hr@demo.com")
    hr_user.totp_secret = pyotp.random_base32()
    hr_user.mfa_enabled = True
    hr_user.save(update_fields=["totp_secret", "mfa_enabled"])
    code = pyotp.TOTP(hr_user.totp_secret).now()
    hr2 = APIClient()
    hr2.force_authenticate(hr_user)
    r = hr2.post(f"/api/reward-cycle/{cycle.id}/execute/", HTTP_X_MFA_CODE=code)
    assert r.status_code == 200, r.data
    cycle.refresh_from_db()
    assert cycle.status == "EXECUTED"

    # 8) reclaim 固化
    eng_cell = AdjustmentBudgetCell.objects.get(
        reward_cycle=cycle, adjustment_type="ANNUAL",
        employee_category_1="STAFF", department=eng,
    )
    # ENG 内 STAFF 实际用量：bob 30000×(0.05+0.01)×12 + eve 28000×0.05×12 = 21600 + 16800 = 38400
    assert eng_cell.allocated_amount_cny == Decimal("38400.00")
    assert eng_cell.reclaimed_amount_cny == Decimal(eng_staff_budget) - Decimal("38400.00")
    assert eng_cell.reclaimed_amount_cny > Decimal("0")

    # LTI 这条流没人 granted_ads，全部 reclaim
    eng_lti = LTIBudgetCell.objects.get(
        plan=lti_plan, employee_category_1="STAFF", target_org_unit=eng,
    )
    assert eng_lti.shares_used_ads == 0
    assert eng_lti.reclaimed_shares_ads == lti_by_ou[eng.id]
