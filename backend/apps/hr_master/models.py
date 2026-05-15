from django.db import models
from apps.iam.models import User, OrgUnit


class LegalEntity(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    country = models.CharField(max_length=8)
    jurisdiction = models.CharField(max_length=64, blank=True)
    default_currency = models.CharField(max_length=8, default="CNY")
    tax_id = models.CharField(max_length=64, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        db_table = "hr_legal_entity"


class Employee(models.Model):
    CATEGORY1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]
    PROMOTION = [("VERTICAL", "纵向晋升"), ("LATERAL", "横向调动"), ("NONE", "未晋升")]

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL)
    employee_no = models.CharField(max_length=32, unique=True)
    name_cn = models.CharField(max_length=64)
    name_en = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    org_unit = models.ForeignKey(OrgUnit, null=True, blank=True, on_delete=models.SET_NULL)
    manager = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    dept_name = models.CharField(max_length=128, blank=True)
    center_name = models.CharField(max_length=128, blank=True)
    team_name = models.CharField(max_length=128, blank=True)
    legal_entity = models.ForeignKey(LegalEntity, null=True, blank=True, on_delete=models.SET_NULL)
    work_location = models.CharField(max_length=128, blank=True)
    pay_country_region = models.CharField(max_length=64, blank=True)
    pay_currency = models.CharField(max_length=8, default="CNY")
    hire_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, default="ACTIVE")
    job_family = models.CharField(max_length=64, blank=True)
    job_level_current = models.CharField(max_length=32, blank=True)
    job_level_promoted = models.CharField(max_length=32, blank=True)
    position_current = models.CharField(max_length=64, blank=True)
    position_promoted = models.CharField(max_length=64, blank=True)
    is_promoted = models.BooleanField(default=False)
    promotion_category = models.CharField(max_length=16, choices=PROMOTION, default="NONE")
    participates_annual_adjustment = models.BooleanField(default=True)
    employee_category_1 = models.CharField(max_length=16, choices=CATEGORY1, default="STAFF")
    employee_category_2 = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "hr_employee"


class CategoryScheme(models.Model):
    """员工类别方案 (年度可换)。每个 RewardCycle 绑定一个方案。

    桶 (EmployeeCategory) 完全由 HR 自定义，如:
      - 2026: 干部 / 员工
      - 2027: 基干 / 中干 / 高干 / 员工
      - 2028: 干部 / senior员工 / junior员工
    """
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    status = models.CharField(
        max_length=16,
        choices=[("ACTIVE", "启用"), ("ARCHIVED", "归档")],
        default="ACTIVE",
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_category_scheme"
        ordering = ["-created_at"]


class EmployeeCategory(models.Model):
    """方案下的一个桶 (类别码)。"""
    scheme = models.ForeignKey(
        CategoryScheme, on_delete=models.CASCADE, related_name="categories"
    )
    code = models.CharField(max_length=32, help_text="方案内唯一, 如 MGMT/STAFF/SENIOR/JUNIOR")
    name = models.CharField(max_length=64, help_text="如 干部/员工/高级员工")
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "hr_employee_category"
        ordering = ["scheme_id", "sort_order"]
        unique_together = [("scheme", "code")]


class EmployeeCategoryAssignment(models.Model):
    """员工 × 方案 → 类别桶的指派。"""
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="category_assignments"
    )
    scheme = models.ForeignKey(
        CategoryScheme, on_delete=models.CASCADE, related_name="assignments"
    )
    category = models.ForeignKey(
        EmployeeCategory, on_delete=models.PROTECT, related_name="assignments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hr_employee_category_assignment"
        unique_together = [("employee", "scheme")]
        indexes = [models.Index(fields=["scheme", "category"])]


class JobGrade(models.Model):
    level = models.CharField(max_length=32, unique=True)
    band = models.CharField(max_length=32, blank=True)
    p50 = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    p75 = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    p90 = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    min_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    mid_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    max_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)

    class Meta:
        db_table = "hr_job_grade"


class CompensationRecord(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="compensation_records")
    effective_date = models.DateField()
    base_salary = models.DecimalField(max_digits=14, decimal_places=2)
    monthly_salary = models.DecimalField(max_digits=14, decimal_places=2)
    allowance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="CNY")
    source = models.CharField(max_length=16, default="MANUAL")
    version = models.IntegerField(default=1)
    superseded_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_compensation_record"


class PerformanceRating(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="perf_ratings")
    period_year = models.IntegerField()
    period_half = models.CharField(max_length=4, choices=[("H1", "上半年"), ("H2", "下半年")])
    rating = models.CharField(max_length=8, blank=True)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    source = models.CharField(max_length=16, default="IMPORT")
    locked_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "hr_performance_rating"
        unique_together = [("employee", "period_year", "period_half")]


class LevelBand(models.Model):
    """职级带（P5、P6、M1、M2 ……）。

    与既有 JobGrade.level/band 平面字段并存，不破坏既有数据；新业务（薪酬带、
    晋升路径、字段集映射）走 LevelBand → PositionGrade 的层级关系。
    """
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=64)
    order = models.IntegerField(help_text="排序权重，小的在前")
    description = models.TextField(blank=True)

    class Meta:
        db_table = "hr_level_band"
        ordering = ["order"]


class PositionGrade(models.Model):
    """职位档（同一职级带内的细分档位，如 P5-A / P5-B）。"""
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    level_band = models.ForeignKey(
        LevelBand, on_delete=models.PROTECT, related_name="position_grades"
    )
    order = models.IntegerField(default=0)
    suggested_min_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    suggested_max_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "hr_position_grade"
        ordering = ["level_band__order", "order"]


class EmployeeFreeze(models.Model):
    """员工冻结：试用期 / 离职流转 / 法务调查 / 长休等情况下不可参与调薪/年终奖。

    业务层在分配前调用 `EmployeeFreeze.has_active(emp)` 判断；end_date 为空表示
    无限期开口冻结，需手动结束。
    """
    REASON_CHOICES = [
        ("PROBATION", "试用期"),
        ("LEAVING", "离职流转"),
        ("LEGAL_HOLD", "法务调查"),
        ("LONG_LEAVE", "长期休假"),
        ("OTHER", "其他"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="freezes"
    )
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="null 表示开口冻结")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_employee_freeze"
        indexes = [models.Index(fields=["employee", "start_date"])]

    def is_active(self, as_of=None) -> bool:
        from datetime import date as _date
        if as_of is None:
            as_of = _date.today()
        if as_of < self.start_date:
            return False
        if self.end_date is not None and as_of > self.end_date:
            return False
        return True

    @classmethod
    def has_active(cls, employee, as_of=None) -> bool:
        return any(f.is_active(as_of) for f in cls.objects.filter(employee=employee))
