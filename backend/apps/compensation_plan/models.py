from django.db import models
from apps.hr_master.models import Employee


class AdjustmentPlan(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    period = models.CharField(max_length=16)
    status = models.CharField(max_length=32, default="DRAFT")
    budget_total_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    scope = models.JSONField(default=dict)
    formula = models.JSONField(default=dict)
    rounding_rule = models.CharField(max_length=16, default="ROUND_HALF_UP")
    created_by_id = models.BigIntegerField(null=True)
    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="adjustment_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comp_adjustment_plan"


class AdjustmentBudgetCell(models.Model):
    ADJ_TYPE = [("ANNUAL", "年度调薪"), ("PROMOTION", "晋升调薪")]
    CAT1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE, related_name="adjustment_budget_cells",
    )
    adjustment_type = models.CharField(max_length=16, choices=ADJ_TYPE)
    employee_category_1 = models.CharField(max_length=16, choices=CAT1)
    department = models.ForeignKey(
        "iam.OrgUnit", null=True, blank=True, on_delete=models.PROTECT,
        related_name="adjustment_budget_cells",
        help_text="NULL = 公司总预算层；非 NULL = 该部门分配额",
    )
    budget_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    allocated_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        db_table = "comp_adjustment_budget_cell"
        unique_together = [("reward_cycle", "adjustment_type", "employee_category_1", "department")]

    @property
    def remaining_amount_cny(self):
        return self.budget_amount_cny - self.allocated_amount_cny


class AdjustmentProposal(models.Model):
    plan = models.ForeignKey(AdjustmentPlan, on_delete=models.CASCADE, related_name="proposals")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    local_currency = models.CharField(max_length=8, default="CNY")
    status = models.CharField(max_length=32, default="DRAFT")
    proposer_id = models.BigIntegerField(null=True)
    effective_date = models.DateField(null=True)
    calculation_basis_snapshot = models.JSONField(default=dict)
    current_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    current_job_level_snapshot = models.CharField(max_length=32, blank=True)
    job_level_promoted_snapshot = models.CharField(max_length=32, blank=True)
    employee_category_1_snapshot = models.CharField(max_length=16, default="STAFF")
    participates_annual_snapshot = models.BooleanField(default=True)
    promotion_adjustment_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    annual_suggested_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    annual_manager_delta_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    promotion_adjustment_amount_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_adjustment_amount_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_special_case = models.BooleanField(default=False)
    market_benchmark_note = models.JSONField(null=True, blank=True)
    retention_reason = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comp_adjustment_proposal"
        unique_together = [("plan", "employee")]

    @property
    def annual_final_pct(self):
        return self.annual_suggested_pct + self.annual_manager_delta_pct

    @property
    def total_adjustment_pct(self):
        return self.promotion_adjustment_pct + self.annual_final_pct

    @property
    def proposed_salary(self):
        return self.current_salary * (1 + self.total_adjustment_pct)
