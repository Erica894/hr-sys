import pytest
from apps.approval.models import ApprovalChainTemplate, ApprovalInstance
from apps.approval.services import get_default_chain, advance_approval
from apps.reward_cycle.models import RewardCycle
from apps.iam.models import User, Role


@pytest.fixture
def chain(db):
    return ApprovalChainTemplate.objects.create(
        scenario="REWARD_CYCLE", name="默认链", is_default=True,
        status="ACTIVE", version=1,
        nodes=[
            {"code": "DEPT_HEAD", "role": "DEPT_HEAD", "scope": "DEPT_HEAD_OF(subject)", "optional": True},
            {"code": "HR_ADMIN", "role": "HR_ADMIN", "scope": "GLOBAL", "optional": False},
        ],
    )


@pytest.mark.django_db
def test_get_default_chain_returns_two_nodes(chain):
    c = get_default_chain("REWARD_CYCLE")
    assert c is not None
    assert len(c.nodes) == 2


@pytest.mark.django_db
def test_advance_approval_full_flow(chain):
    Role.objects.get_or_create(code="DEPT_HEAD", defaults={"name": "部门负责人"})
    Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "薪酬HR"})
    dh = User.objects.create_user(email="dh@t.com", employee_no="D001", password="p")
    hr = User.objects.create_user(email="hr@t.com", employee_no="H001", password="p")
    cycle = RewardCycle.objects.create(code="RC-T1", name="T1", period="2026", status="APPROVING")
    inst = ApprovalInstance.objects.create(
        template=chain, subject_type="REWARD_CYCLE",
        subject_id=cycle.id, current_node=0,
    )
    advance_approval(inst.id, dh.id, "APPROVE", "ok")
    inst.refresh_from_db()
    assert inst.current_node == 1
    assert inst.status == "RUNNING"
    advance_approval(inst.id, hr.id, "APPROVE", "final")
    inst.refresh_from_db()
    assert inst.status == "APPROVED"
    cycle.refresh_from_db()
    assert cycle.status == "APPROVED_PENDING_EXECUTE"


@pytest.mark.django_db
def test_reject_sets_instance_rejected(chain):
    Role.objects.get_or_create(code="DEPT_HEAD", defaults={"name": "部门负责人"})
    dh = User.objects.create_user(email="dh@t.com", employee_no="D001", password="p")
    cycle = RewardCycle.objects.create(code="RC-T2", name="T2", period="2026", status="APPROVING")
    inst = ApprovalInstance.objects.create(
        template=chain, subject_type="REWARD_CYCLE",
        subject_id=cycle.id, current_node=0,
    )
    advance_approval(inst.id, dh.id, "REJECT_BATCH", "退回")
    inst.refresh_from_db()
    assert inst.status == "REJECTED"
    cycle.refresh_from_db()
    assert cycle.status == "IN_PROGRESS"
