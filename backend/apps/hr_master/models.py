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
