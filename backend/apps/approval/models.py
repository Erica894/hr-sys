from django.db import models


class ApprovalChainTemplate(models.Model):
    SCENARIOS = [
        ("ADJUSTMENT", "Adjustment"),
        ("BONUS", "Bonus"),
        ("LTI", "LTI"),
        ("REWARD_CYCLE", "Reward Cycle"),
        ("DELEGATION", "Delegation"),
    ]
    scenario = models.CharField(max_length=32, choices=SCENARIOS)
    name = models.CharField(max_length=128)
    status = models.CharField(max_length=16, default="ACTIVE")
    version = models.IntegerField(default=1)
    is_default = models.BooleanField(default=False)
    nodes = models.JSONField(default=list)
    effective_from = models.DateField(null=True)
    effective_to = models.DateField(null=True)

    class Meta:
        db_table = "approval_chain_template"


class ApprovalInstance(models.Model):
    template = models.ForeignKey(ApprovalChainTemplate, on_delete=models.PROTECT)
    subject_type = models.CharField(max_length=32)
    subject_id = models.BigIntegerField()
    current_node = models.IntegerField(default=0)
    status = models.CharField(max_length=32, default="RUNNING")
    over_budget_flag = models.BooleanField(default=False)
    over_budget_details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "approval_instance"


class ApprovalStep(models.Model):
    ACTIONS = [
        ("APPROVE", "Approve"),
        ("REJECT_BATCH", "Reject Batch"),
        ("REJECT_INDIVIDUAL", "Reject Individual"),
        ("REJECT_WITH_COMMENT", "Reject With Comment"),
    ]
    instance = models.ForeignKey(ApprovalInstance, on_delete=models.CASCADE, related_name="steps")
    node_index = models.IntegerField()
    approver_user_id = models.BigIntegerField()
    action = models.CharField(max_length=32, choices=ACTIONS)
    comment = models.TextField(blank=True)
    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "approval_step"
