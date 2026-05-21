"""E2E bonus subflow: 公司层 → 部门下发 → 经理调整 → 执行 → cell 固化。

复用 seed_phase1 的 5 名员工 / depthead，在已有的 RewardCycle 上挂 BonusPlan，
模拟从预算配置到执行后回收的完整路径。
"""
import pytest
import pyotp
from decimal import Decimal
from rest_framework.test import APIClient
from django.core.management import call_command

from apps.iam.models import User
from apps.iam.services import generate_totp_secret
from apps.hr_master.models import Employee
from apps.reward_cycle.models import RewardCycle
from apps.bonus_pool.models import (
    BonusPlan, BonusBudgetCell, BonusProposal,
)


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


def test_bonus_subflow_budget_to_finalize(stack):
    hr_user = stack
    hr = _c("hr@demo.com")
    cycle = RewardCycle.objects.first()
    cid = cycle.id

    plan = BonusPlan.objects.create(
        code="BE2E", name="bonus e2e", period="2026",
    )
    cycle.linked_bonus_plan = plan
    cycle.save(update_fields=["linked_bonus_plan"])

    # 1. HR 配置公司层预算（通过 API）
    r = hr.put(
        f"/api/admin/reward-cycles/{cid}/bonus-budget/",
        {"rows": [
            {"employee_category_1": "MANAGEMENT", "budget_amount_cny": "200000"},
            {"employee_category_1": "STAFF", "budget_amount_cny": "500000"},
        ]},
        format="json",
    )
    assert r.status_code == 200, r.data

    # 2. 触发 generate_proposals（GET allocation 时自动生成）
    r = hr.get(f"/api/reward-cycle/{cid}/allocation/")
    assert r.status_code == 200, r.data

    # 3. BonusProposal 已为每位员工创建
    proposals = BonusProposal.objects.filter(plan=plan)
    assert proposals.count() == 5

    # 4. 在公司层预算下，HR 给 alice 设置 bonus delta（应通过 cap）
    alice_emp_id = Employee.objects.get(employee_no="E001").id
    r = hr.patch(
        f"/api/reward-cycle/{cid}/proposals/",
        {"items": [{
            "employee_id": alice_emp_id,
            "bonus_manager_delta_amount_cny": "1000",
        }]},
        format="json",
    )
    assert r.status_code == 200, r.data

    p = proposals.get(employee_id=alice_emp_id)
    assert p.manager_delta_amount_cny == Decimal("1000.00")

    # 5. 提交审批 → 部门头 → HR
    r = hr.post(f"/api/reward-cycle/{cid}/submit/")
    assert r.status_code == 200, r.data
    inst_id = r.data["instance_id"]

    dept = _c("depthead@demo.com")
    r = dept.post(
        f"/api/approval/{inst_id}/action/",
        {"action": "APPROVE", "comment": "ok"}, format="json",
    )
    assert r.status_code == 200

    r = hr.post(
        f"/api/approval/{inst_id}/action/",
        {"action": "APPROVE", "comment": "final"}, format="json",
    )
    assert r.status_code == 200

    cycle.refresh_from_db()
    assert cycle.status == "APPROVED_PENDING_EXECUTE"

    # 6. HR 执行（MFA）→ 验证 BonusProposal 锁定 + cell 固化
    code = pyotp.TOTP(hr_user.totp_secret).now()
    r = hr.post(f"/api/reward-cycle/{cid}/execute/", HTTP_X_MFA_CODE=code)
    assert r.status_code == 200, r.data

    cycle.refresh_from_db()
    assert cycle.status == "EXECUTED"

    # 所有 BonusProposal 已锁定
    for bp in BonusProposal.objects.filter(plan=plan):
        assert bp.status == "EXECUTED"
        assert bp.final_amount_cny == bp.suggested_amount_cny + bp.manager_delta_amount_cny

    # 公司层 cell 仍存在（不会被回收，仅作展示）
    company_cells = BonusBudgetCell.objects.filter(
        reward_cycle=cycle, target_org_unit__isnull=True,
    )
    assert company_cells.count() == 2
