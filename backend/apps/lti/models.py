from django.db import models
from apps.hr_master.models import Employee


class LTIPlan(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    grant_date = models.DateField()
    total_shares = models.BigIntegerField(default=0)
    share_unit = models.CharField(max_length=8, default="ADS")
    unit_price_at_grant = models.DecimalField(max_digits=10, decimal_places=4)
    vesting_schedule = models.JSONField(default=dict)
    cliff_months = models.IntegerField(default=12)
    plan_doc_url = models.TextField(blank=True)
    stock_code = models.CharField(max_length=16, blank=True)
    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lti_plans",
    )

    class Meta:
        db_table = "lti_plan"


class LTIBudgetCell(models.Model):
    CAT1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]
    plan = models.ForeignKey(LTIPlan, on_delete=models.CASCADE, related_name="budget_cells")
    employee_category_1 = models.CharField(max_length=16, choices=CAT1)
    target_org_unit = models.ForeignKey(
        "iam.OrgUnit", null=True, blank=True, on_delete=models.PROTECT,
        related_name="lti_budget_cells",
        help_text="NULL = 公司层；非 NULL = 该 DEPT/CENTER 单元的下发额度",
    )
    headcount_quota = models.IntegerField(default=0)
    shares_quota_ads = models.BigIntegerField(default=0)
    headcount_used = models.IntegerField(default=0)
    shares_used_ads = models.BigIntegerField(default=0)
    distribution_rule = models.CharField(
        max_length=16,
        choices=[("MANUAL", "手动"), ("HEADCOUNT", "按人头"), ("SALARY_TOTAL", "按薪资基数")],
        default="MANUAL", blank=True,
        help_text="仅公司层 cell 使用，记录最近一次下发规则",
    )
    reclaimed_shares_ads = models.BigIntegerField(
        default=0,
        help_text="EXECUTE 后回收的未授予股数（仅目标层）",
    )

    class Meta:
        db_table = "lti_budget_cell"
        unique_together = [("plan", "employee_category_1", "target_org_unit")]


class LTIGrant(models.Model):
    plan = models.ForeignKey(LTIPlan, on_delete=models.CASCADE, related_name="grants")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    status = models.CharField(max_length=16, default="PROPOSED")
    is_eligible = models.BooleanField(default=True)
    grant_tier = models.CharField(max_length=8, blank=True)
    suggested_range_min_ads = models.IntegerField(default=0)
    suggested_range_max_ads = models.IntegerField(default=0)
    granted_ads = models.IntegerField(default=0)
    employee_category_1_snapshot = models.CharField(max_length=16, default="STAFF")
    stock_code = models.CharField(max_length=16, blank=True)
    unit_price_at_grant = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    pending_shares_by_year = models.JSONField(default=dict)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lti_grant"
        unique_together = [("plan", "employee")]


class VestingEvent(models.Model):
    grant = models.ForeignKey(LTIGrant, on_delete=models.CASCADE, related_name="vesting_events")
    scheduled_date = models.DateField()
    scheduled_shares = models.IntegerField()
    actual_date = models.DateField(null=True)
    actual_shares = models.IntegerField(null=True)
    status = models.CharField(max_length=16, default="PENDING")

    class Meta:
        db_table = "lti_vesting_event"


class StockPriceMonthly(models.Model):
    stock_code = models.CharField(max_length=16)
    month = models.CharField(max_length=7)
    closing_price = models.DecimalField(max_digits=10, decimal_places=4)
    currency = models.CharField(max_length=8, default="USD")
    source = models.CharField(max_length=16, default="MARKET")
    locked_by_id = models.BigIntegerField(null=True)
    locked_at = models.DateTimeField(null=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "lti_stock_price_monthly"
        unique_together = [("stock_code", "month")]


class EmployeeAck(models.Model):
    subject_type = models.CharField(max_length=16)
    subject_id = models.BigIntegerField()
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    acked_at = models.DateTimeField(auto_now_add=True)
    signature_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "lti_employee_ack"
        unique_together = [("subject_type", "subject_id", "employee")]
