from decimal import Decimal
from rest_framework import serializers
from apps.reward_cycle.models import RewardCycle


class RewardCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RewardCycle
        fields = ["id", "code", "name", "status", "period", "created_at"]


class AllocationRowSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(source="employee.id")
    employee_no = serializers.CharField(source="employee.employee_no")
    name_cn = serializers.CharField(source="employee.name_cn")
    dept_name = serializers.CharField(source="employee.dept_name")
    job_level_current = serializers.CharField(source="employee.job_level_current")
    job_level_promoted = serializers.CharField(source="employee.job_level_promoted", allow_null=True)
    is_promoted = serializers.BooleanField(source="employee.is_promoted")
    participates_annual = serializers.BooleanField(source="employee.participates_annual_adjustment")
    current_monthly_salary = serializers.SerializerMethodField()
    annual_suggested_pct = serializers.SerializerMethodField()
    annual_manager_delta_pct = serializers.SerializerMethodField()
    annual_final_pct = serializers.SerializerMethodField()
    promotion_adjustment_pct = serializers.SerializerMethodField()
    total_adjustment_pct = serializers.SerializerMethodField()
    proposed_monthly_salary = serializers.SerializerMethodField()
    granted_ads = serializers.SerializerMethodField()
    unit_price_at_grant = serializers.SerializerMethodField()
    annual_base = serializers.SerializerMethodField()
    annual_rsu_value = serializers.SerializerMethodField()
    total_comp = serializers.SerializerMethodField()

    def _p(self, obj):
        return obj["proposal"]

    def _g(self, obj):
        return obj["grant"]

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
