from django.db import models
from apps.hr_master.models import Employee


DEFAULT_PERF_GRADES = [
    {"code": "STAR_5", "label": "5星", "sort_order": 1},
    {"code": "STAR_4", "label": "4星", "sort_order": 2},
    {"code": "STAR_3", "label": "3星", "sort_order": 3},
    {"code": "STAR_2", "label": "2星", "sort_order": 4},
    {"code": "STAR_1", "label": "1星", "sort_order": 5},
]


def default_perf_grades():
    return [dict(g) for g in DEFAULT_PERF_GRADES]


class AdjustmentPlan(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    period = models.CharField(max_length=16)
    status = models.CharField(max_length=32, default="DRAFT")
    formula = models.JSONField(default=dict)
    rounding_rule = models.CharField(max_length=16, default="ROUND_HALF_UP")
    perf_grades = models.JSONField(
        default=default_perf_grades,
        help_text="绩效档位列表 [{code, label, sort_order}], 默认 5 档 (5 星 -> 1 星)",
    )
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
        related_name="dept_budget_cells",
        help_text="NULL = 公司总预算层；非 NULL = 该部门分配额",
    )
    budget_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    allocated_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    distribution_rule = models.CharField(
        max_length=16,
        choices=[("MANUAL", "手动"), ("HEADCOUNT", "按人头"), ("SALARY_TOTAL", "按薪资基数")],
        default="MANUAL", blank=True,
        help_text="仅公司层 cell（department=NULL）使用，记录最近一次下发规则",
    )
    reclaimed_amount_cny = models.DecimalField(
        max_digits=16, decimal_places=2, default=0,
        help_text="EXECUTE 后回收的未用预算（仅目标层 cell）",
    )

    class Meta:
        db_table = "comp_adjustment_budget_cell"
        unique_together = [("reward_cycle", "adjustment_type", "employee_category_1", "department")]

    @property
    def remaining_amount_cny(self):
        return self.budget_amount_cny - self.allocated_amount_cny


class RegionalAdjustmentRule(models.Model):
    """区域基准调薪比例 (按 LegalEntity.country)。

    层 1 规则的一部分：每个 (周期, 国家, 调薪类型) 给一个基准比例，例如:
      - CN / ANNUAL = 5.0%
      - US / ANNUAL = 3.5%
      - SG / PROMOTION = 8.0%
    最终员工调薪比例 = base_pct × category_factor。
    """
    ADJ_TYPE = [("ANNUAL", "年度调薪"), ("PROMOTION", "晋升调薪")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE,
        related_name="regional_adjustment_rules",
    )
    country = models.CharField(max_length=8, help_text="LegalEntity.country, 如 CN / US / SG")
    adjustment_type = models.CharField(max_length=16, choices=ADJ_TYPE)
    base_pct = models.DecimalField(
        max_digits=6, decimal_places=4,
        help_text="例如 0.0500 表示 5%",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comp_regional_adjustment_rule"
        unique_together = [("reward_cycle", "country", "adjustment_type")]
        indexes = [models.Index(fields=["reward_cycle", "adjustment_type"])]


class EmployeeCategoryFactor(models.Model):
    """员工类别调节系数 (在 RegionalAdjustmentRule 基础上叠乘)。

    每个 (周期, 类别桶, 调薪类型) 给一个系数，例如:
      - 干部 / ANNUAL = 1.2 (干部年度调薪比基准高 20%)
      - 员工 / ANNUAL = 1.0
    最终员工调薪比例 = base_pct(country, type) × factor(category, type)。
    `category` 必须属于 `reward_cycle.category_scheme`。
    """
    ADJ_TYPE = [("ANNUAL", "年度调薪"), ("PROMOTION", "晋升调薪")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE,
        related_name="category_factors",
    )
    category = models.ForeignKey(
        "hr_master.EmployeeCategory", on_delete=models.PROTECT,
        related_name="adjustment_factors",
    )
    adjustment_type = models.CharField(max_length=16, choices=ADJ_TYPE)
    factor = models.DecimalField(
        max_digits=6, decimal_places=4,
        help_text="乘在基准比例之上, 1.0000 = 不调整",
        default=1,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comp_employee_category_factor"
        unique_together = [("reward_cycle", "category", "adjustment_type")]
        indexes = [models.Index(fields=["reward_cycle", "adjustment_type"])]


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


class AdjustmentMatrixCell(models.Model):
    """调薪矩阵单元格：在规则派生的基础调薪比例之上叠加"调节系数区间"。

    维度：cycle × category × perf_grade × pay_band → [coef_low, coef_high]。
    个人建议年度调薪区间 = base_pct × factor × [coef_low, coef_high]。
    perf_grade_code 必须在所属方案 `AdjustmentPlan.perf_grades` 列表中。
    """
    PAY_BAND_CHOICES = [
        ("BELOW_P50", "P50 以下"),
        ("P50_P75", "P50 - P75"),
        ("ABOVE_P75", "P75 以上"),
    ]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE,
        related_name="adjustment_matrix_cells",
    )
    category = models.ForeignKey(
        "hr_master.EmployeeCategory", on_delete=models.PROTECT,
        related_name="adjustment_matrix_cells",
    )
    perf_grade_code = models.CharField(max_length=32)
    pay_band = models.CharField(max_length=16, choices=PAY_BAND_CHOICES)
    coef_low = models.DecimalField(max_digits=5, decimal_places=4)
    coef_high = models.DecimalField(max_digits=5, decimal_places=4)
    notes = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comp_adjustment_matrix_cell"
        unique_together = [("reward_cycle", "category", "perf_grade_code", "pay_band")]
        indexes = [models.Index(fields=["reward_cycle", "category"])]


class BudgetOverride(models.Model):
    """部门池派生预算的人工覆盖值 (Sprint 2 兜底通道)。

    派生总览的部门池金额默认 = 规则自下而上派生 (source=DERIVED)。
    HR 在派生值不合理时，可上传 Excel 用 override_amount_cny 覆盖该部门 + 调薪类型的池金额，
    系统记 source=IMPORTED。护栏: override 不能低于该 (cycle, dept, adj_type) 已分配额。
    """
    ADJ_TYPE = [("ANNUAL", "年度调薪"), ("PROMOTION", "晋升调薪")]
    SOURCE = [("IMPORTED", "已导入"), ("DERIVED", "派生")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE,
        related_name="budget_overrides",
    )
    department = models.ForeignKey(
        "iam.OrgUnit", on_delete=models.CASCADE,
        related_name="budget_overrides",
        help_text="必须 type=DEPT；不允许 NULL (未分配部门不可覆盖)",
    )
    adjustment_type = models.CharField(max_length=16, choices=ADJ_TYPE)
    override_amount_cny = models.DecimalField(max_digits=16, decimal_places=2)
    source = models.CharField(max_length=16, choices=SOURCE, default="IMPORTED")
    uploaded_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="budget_overrides_uploaded",
    )
    uploaded_at = models.DateTimeField(auto_now=True)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "comp_budget_override"
        unique_together = [("reward_cycle", "department", "adjustment_type")]
        indexes = [models.Index(fields=["reward_cycle", "adjustment_type"])]
