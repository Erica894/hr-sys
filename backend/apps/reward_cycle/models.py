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
    category_scheme = models.ForeignKey(
        "hr_master.CategoryScheme", null=True, blank=True,
        on_delete=models.PROTECT, related_name="reward_cycles",
        help_text="该周期使用的员工类别方案；规则、预算单元的 category_id 都必须落在此方案下",
    )
    created_by_id = models.BigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    discretionary_pct = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=0.1,
        help_text="部门 head 机动盘占预算池比例 (默认 10%); 矩阵建议占 1-discretionary_pct",
    )

    class Meta:
        db_table = "reward_cycle"
