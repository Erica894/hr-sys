from django.db import transaction
from .models import ApprovalChainTemplate, ApprovalInstance, ApprovalStep


def get_default_chain(scenario: str):
    return ApprovalChainTemplate.objects.filter(
        scenario=scenario, is_default=True, status="ACTIVE"
    ).first()


@transaction.atomic
def advance_approval(instance_id: int, actor_id: int, action: str, comment: str = ""):
    inst = ApprovalInstance.objects.select_for_update().get(id=instance_id)
    if inst.status != "RUNNING":
        raise ValueError(f"Instance {instance_id} not RUNNING (status={inst.status})")

    ApprovalStep.objects.create(
        instance=inst, node_index=inst.current_node,
        approver_user_id=actor_id, action=action, comment=comment,
    )

    if action.startswith("REJECT"):
        inst.status = "REJECTED"
        inst.save(update_fields=["status"])
        _on_rejected(inst)
        return inst

    nodes = inst.template.nodes
    next_node = inst.current_node + 1
    if next_node >= len(nodes):
        inst.status = "APPROVED"
        inst.save(update_fields=["status"])
        _on_approved(inst)
    else:
        inst.current_node = next_node
        inst.save(update_fields=["current_node"])
    return inst


def _on_approved(inst):
    if inst.subject_type == "REWARD_CYCLE":
        from apps.reward_cycle.models import RewardCycle
        RewardCycle.objects.filter(id=inst.subject_id).update(status="APPROVED_PENDING_EXECUTE")


def _on_rejected(inst):
    if inst.subject_type == "REWARD_CYCLE":
        from apps.reward_cycle.models import RewardCycle
        RewardCycle.objects.filter(id=inst.subject_id).update(status="IN_PROGRESS")
