from django.db import models
from apps.hr_master.models import Employee


class BonusPlan(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    period = models.CharField(max_length=16)
    status = models.CharField(max_length=32, default="DRAFT")
    budget_total_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    scope = models.JSONField(default=dict, blank=True)
    formula = models.JSONField(default=dict, blank=True)
    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="bonus_plans",
    )
    created_by_id = models.BigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bonus_plan"


class RegionalBonusRule(models.Model):
    """区域基准年终奖月数 (按 LegalEntity.country)。

    层 1 规则：每个 (周期, 国家) 给一个基准月数，例如:
      - CN = 1.5 个月
      - US = 1.0 个月
    最终员工年终奖金额 = monthly_salary × base_months × category_factor。
    """
    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE,
        related_name="regional_bonus_rules",
    )
    country = models.CharField(max_length=8, help_text="LegalEntity.country, 如 CN / US / SG")
    base_months = models.DecimalField(
        max_digits=6, decimal_places=4,
        help_text="例如 1.5000 表示 1.5 个月薪",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bonus_regional_rule"
        unique_together = [("reward_cycle", "country")]
        indexes = [models.Index(fields=["reward_cycle"])]


class BonusCategoryFactor(models.Model):
    """员工类别调节系数 (在 RegionalBonusRule 基础上叠乘)。

    每个 (周期, 类别桶) 给一个系数，例如:
      - 干部 = 1.2 (干部年终奖比基准高 20%)
      - 员工 = 1.0
    最终员工年终奖金额 = monthly_salary × base_months(country) × factor(category)。
    """
    CAT1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE,
        related_name="bonus_category_factors",
    )
    employee_category_1 = models.CharField(max_length=16, choices=CAT1)
    factor = models.DecimalField(
        max_digits=6, decimal_places=4,
        help_text="乘在基准月数之上, 1.0000 = 不调整",
        default=1,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bonus_category_factor"
        unique_together = [("reward_cycle", "employee_category_1")]
        indexes = [models.Index(fields=["reward_cycle"])]


class BonusBudgetCell(models.Model):
    """年终奖预算单元 (cycle × 类别 × 部门)。

    NULL target_org_unit = 公司层；非 NULL = 该部门下发额度。
    """
    CAT1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE,
        related_name="bonus_budget_cells",
    )
    employee_category_1 = models.CharField(max_length=16, choices=CAT1)
    target_org_unit = models.ForeignKey(
        "iam.OrgUnit", null=True, blank=True, on_delete=models.PROTECT,
        related_name="bonus_budget_cells",
        help_text="NULL = 公司层；非 NULL = 该 DEPT/CENTER 单元的下发额度",
    )
    budget_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    allocated_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    distribution_rule = models.CharField(
        max_length=16,
        choices=[("MANUAL", "手动"), ("HEADCOUNT", "按人头"), ("SALARY_TOTAL", "按薪资基数")],
        default="MANUAL", blank=True,
        help_text="仅公司层 cell 使用，记录最近一次下发规则",
    )
    reclaimed_amount_cny = models.DecimalField(
        max_digits=16, decimal_places=2, default=0,
        help_text="EXECUTE 后回收的未用预算（仅目标层 cell）",
    )

    class Meta:
        db_table = "bonus_budget_cell"
        unique_together = [("reward_cycle", "employee_category_1", "target_org_unit")]

    @property
    def remaining_amount_cny(self):
        return self.budget_amount_cny - self.allocated_amount_cny


class BonusBudgetOverride(models.Model):
    """部门池派生预算的人工覆盖值。

    派生总览的部门池金额默认 = 规则自下而上派生 (source=DERIVED)。
    HR 在派生值不合理时，可上传 Excel 用 override_amount_cny 覆盖该部门池金额，
    系统记 source=IMPORTED。护栏: override 不能低于该 (cycle, dept) 已分配额。
    """
    SOURCE = [("IMPORTED", "已导入"), ("DERIVED", "派生")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE,
        related_name="bonus_budget_overrides",
    )
    department = models.ForeignKey(
        "iam.OrgUnit", on_delete=models.CASCADE,
        related_name="bonus_budget_overrides",
        help_text="必须 type=DEPT；不允许 NULL (未分配部门不可覆盖)",
    )
    override_amount_cny = models.DecimalField(max_digits=16, decimal_places=2)
    source = models.CharField(max_length=16, choices=SOURCE, default="IMPORTED")
    uploaded_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="bonus_budget_overrides_uploaded",
    )
    uploaded_at = models.DateTimeField(auto_now=True)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "bonus_budget_override"
        unique_together = [("reward_cycle", "department")]
        indexes = [models.Index(fields=["reward_cycle"])]


class BonusProposal(models.Model):
    plan = models.ForeignKey(BonusPlan, on_delete=models.CASCADE, related_name="proposals")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    status = models.CharField(max_length=32, default="DRAFT")
    proposer_id = models.BigIntegerField(null=True)
    suggested_amount_cny = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="规则派生的建议金额 = monthly_salary × base_months × factor",
    )
    manager_delta_amount_cny = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="经理可调增减额（正负）",
    )
    final_amount_cny = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="EXECUTE 时锁定 = suggested + manager_delta",
    )
    employee_category_1_snapshot = models.CharField(max_length=16, default="STAFF")
    country_snapshot = models.CharField(max_length=8, blank=True)
    monthly_salary_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bonus_proposal"
        unique_together = [("plan", "employee")]

    @property
    def total_amount_cny(self):
        return self.suggested_amount_cny + self.manager_delta_amount_cny
