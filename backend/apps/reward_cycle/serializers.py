from decimal import Decimal
from rest_framework import serializers
from apps.reward_cycle.models import RewardCycle


class RewardCycleSerializer(serializers.ModelSerializer):
    budget_year = serializers.SerializerMethodField()
    category_scheme_code = serializers.CharField(
        source="category_scheme.code", read_only=True, default=None,
    )

    class Meta:
        model = RewardCycle
        fields = [
            "id", "code", "name", "status", "period", "budget_year",
            "category_scheme", "category_scheme_code", "created_at",
        ]

    def get_budget_year(self, obj):
        scope = obj.scope or {}
        if "budget_year" in scope:
            return scope.get("budget_year")
        try:
            return int(str(obj.period)[:4])
        except (ValueError, TypeError):
            return None


class AllocationRowSerializer(serializers.Serializer):
    # 基础信息
    employee_id = serializers.IntegerField(source="employee.id")
    employee_no = serializers.CharField(source="employee.employee_no")
    name_cn = serializers.CharField(source="employee.name_cn")
    dept_name = serializers.CharField(source="employee.dept_name")
    center_name = serializers.CharField(source="employee.center_name", allow_blank=True)
    job_level_current = serializers.CharField(source="employee.job_level_current", allow_blank=True)
    job_level_promoted = serializers.CharField(source="employee.job_level_promoted", allow_blank=True, allow_null=True)
    position_promoted = serializers.CharField(source="employee.position_promoted", allow_blank=True)
    position_current = serializers.CharField(source="employee.position_current", allow_blank=True)
    employee_category_1 = serializers.CharField(source="employee.employee_category_1", allow_blank=True)
    employee_category_2 = serializers.CharField(source="employee.employee_category_2", allow_blank=True)
    hire_date = serializers.DateField(source="employee.hire_date", allow_null=True)
    pay_country_region = serializers.CharField(source="employee.pay_country_region", allow_blank=True)
    pay_currency = serializers.CharField(source="employee.pay_currency", allow_blank=True)

    # 绩效（Y-1）
    perf_y_minus_1_h1 = serializers.SerializerMethodField()
    perf_y_minus_1_h2 = serializers.SerializerMethodField()

    # 参与标志
    is_promoted = serializers.BooleanField(source="employee.is_promoted")
    promotion_category = serializers.CharField(source="employee.promotion_category", allow_blank=True)
    participates_annual = serializers.BooleanField(source="employee.participates_annual_adjustment")

    # 当前月薪
    current_monthly_salary = serializers.SerializerMethodField()

    # 调薪分配
    annual_suggested_pct = serializers.SerializerMethodField()
    annual_manager_delta_pct = serializers.SerializerMethodField()
    annual_final_pct = serializers.SerializerMethodField()
    promotion_adjustment_pct = serializers.SerializerMethodField()
    total_adjustment_pct = serializers.SerializerMethodField()
    proposed_monthly_salary = serializers.SerializerMethodField()

    # RSU
    granted_ads = serializers.SerializerMethodField()
    unit_price_at_grant = serializers.SerializerMethodField()

    # 总包
    annual_base = serializers.SerializerMethodField()
    annual_rsu_value = serializers.SerializerMethodField()
    total_comp = serializers.SerializerMethodField()

    def _p(self, obj):
        return obj.get("proposal")

    def _g(self, obj):
        return obj.get("grant")

    def _perf(self, obj):
        return obj.get("perf") or {}

    def get_perf_y_minus_1_h1(self, o):
        return self._perf(o).get("y_minus_1_h1")

    def get_perf_y_minus_1_h2(self, o):
        return self._perf(o).get("y_minus_1_h2")

    def get_current_monthly_salary(self, o):
        p = self._p(o)
        return p.current_salary if p else None

    def get_annual_suggested_pct(self, o):
        p = self._p(o)
        return p.annual_suggested_pct if p else None

    def get_annual_manager_delta_pct(self, o):
        p = self._p(o)
        return p.annual_manager_delta_pct if p else None

    def get_annual_final_pct(self, o):
        p = self._p(o)
        return p.annual_final_pct if p else None

    def get_promotion_adjustment_pct(self, o):
        p = self._p(o)
        return p.promotion_adjustment_pct if p else None

    def get_total_adjustment_pct(self, o):
        p = self._p(o)
        return p.total_adjustment_pct if p else None

    def get_proposed_monthly_salary(self, o):
        p = self._p(o)
        return p.proposed_salary.quantize(Decimal("0.01")) if p else None

    def get_granted_ads(self, o):
        g = self._g(o)
        return g.granted_ads if g else 0

    def get_unit_price_at_grant(self, o):
        g = self._g(o)
        return g.unit_price_at_grant if g else None

    def get_annual_base(self, o):
        p = self._p(o)
        if not p:
            return None
        return (p.proposed_salary * 12).quantize(Decimal("0.01"))

    def get_annual_rsu_value(self, o):
        g = self._g(o)
        if not g or not g.granted_ads:
            return Decimal("0.00")
        return (Decimal(g.granted_ads) * g.unit_price_at_grant / Decimal("5")).quantize(Decimal("0.01"))

    def get_total_comp(self, o):
        base = self.get_annual_base(o) or Decimal("0")
        rsu = self.get_annual_rsu_value(o) or Decimal("0")
        return (base + rsu).quantize(Decimal("0.01"))


class SaveProposalsItemSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    annual_manager_delta_pct = serializers.DecimalField(max_digits=6, decimal_places=4, required=False)
    granted_ads = serializers.IntegerField(required=False, min_value=0)
