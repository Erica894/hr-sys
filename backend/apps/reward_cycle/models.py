from django.db import models


class RewardCycle(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    period = models.CharField(max_length=16)
    status = models.CharField(max_length=32, default="DRAFT")
    scope = models.JSONField(default=dict)
    linked_adjustment_plan = models.OneToOneField(
        "compensation_plan.AdjustmentPlan", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reward_cycle_link",
    )
    linked_lti_plan = models.OneToOneField(
        "lti.LTIPlan", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reward_cycle_link",
    )
    total_comp_config = models.JSONField(default=dict)
    created_by_id = models.BigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reward_cycle"
