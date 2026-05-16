from django.db import models


class EmployeeCompensationSnapshot(models.Model):
    """员工年度薪酬快照（5 列总包，统一 CNY）。

    数据来源：
    - DERIVED：cycle 执行后由 snapshot_builder 自动派生（Y/Y+1）
    - IMPORT：HR Excel 导入历史 Y-1 数据
    - DERIVED+MANUAL_BONUS：DERIVED 行被 import 命令补录了实发奖金
    """
    SNAPSHOT_KIND_CHOICES = [("ACTUAL", "已实发"), ("PROJECTED", "Y+1 预测")]

    employee = models.ForeignKey(
        "hr_master.Employee", on_delete=models.CASCADE, related_name="comp_snapshots"
    )
    year = models.IntegerField()
    snapshot_kind = models.CharField(max_length=16, choices=SNAPSHOT_KIND_CHOICES)

    annual_fixed_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_bonus_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_cash_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_rsu_value_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_total_comp_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    perf_grade_code = models.CharField(max_length=32, blank=True)
    pay_band = models.CharField(max_length=16, blank=True)
    employee_category_1_snapshot = models.CharField(max_length=16, blank=True)
    org_unit_snapshot_id = models.BigIntegerField(null=True)

    source = models.CharField(max_length=32, default="DERIVED")
    derived_from_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", null=True, blank=True, on_delete=models.SET_NULL
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_emp_comp_snapshot"
        unique_together = [("employee", "year", "snapshot_kind")]
        indexes = [
            models.Index(fields=["year", "snapshot_kind"]),
            models.Index(fields=["org_unit_snapshot_id", "year"]),
        ]


class MarketSalaryReference(models.Model):
    """市场分位参考（v1 占位，HR 上传通道留位，不展示分位线）。"""
    job_level_code = models.CharField(max_length=32)
    region = models.CharField(max_length=64)
    year = models.IntegerField()
    p50_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    p75_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    p90_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    source_note = models.CharField(max_length=200, blank=True)
    uploaded_by_id = models.BigIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_market_salary_ref"
        unique_together = [("job_level_code", "region", "year")]


class FxRateMonthly(models.Model):
    """月度汇率，单表两用：本地货币→CNY 折现金；USD→CNY 折 RSU。

    缺月查询抛 MissingFxRate（见 services/fx.py），不静默用上月，避免数据失真。
    """
    quote_currency = models.CharField(max_length=8, help_text="源币种 HKD/SGD/EUR/JPY/USD…")
    target_currency = models.CharField(max_length=8, help_text="目标币种 CNY 或 USD")
    month = models.CharField(max_length=7, help_text="2026-03")
    rate = models.DecimalField(max_digits=14, decimal_places=6, help_text="1 quote = N target")
    source = models.CharField(max_length=16, default="MANUAL")
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by_id = models.BigIntegerField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_fx_rate_monthly"
        unique_together = [("quote_currency", "target_currency", "month")]
        indexes = [models.Index(fields=["target_currency", "month"])]
