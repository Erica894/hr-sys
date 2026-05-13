from rest_framework import serializers
from apps.lti.models import LTIPlan, LTIBudgetCell


class LTIPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = LTIPlan
        fields = [
            "id", "code", "name", "grant_date",
            "total_shares", "share_unit", "unit_price_at_grant",
            "vesting_schedule", "cliff_months", "stock_code",
            "plan_doc_url", "reward_cycle",
        ]
        read_only_fields = ["id"]


class LTIBudgetCellSerializer(serializers.ModelSerializer):
    """公司层 cell 的标准序列化（向后兼容现有 FE）。"""

    class Meta:
        model = LTIBudgetCell
        fields = [
            "employee_category_1",
            "headcount_quota", "shares_quota_ads",
            "headcount_used", "shares_used_ads",
            "distribution_rule",
        ]
        read_only_fields = ["headcount_used", "shares_used_ads"]


class TargetLTIBudgetCellSerializer(serializers.ModelSerializer):
    """目标层 cell 序列化：附带 OrgUnit 名称和类型。"""
    target_org_unit_id = serializers.IntegerField(read_only=True)
    target_org_unit_name = serializers.CharField(source="target_org_unit.name", read_only=True)
    target_org_unit_type = serializers.CharField(source="target_org_unit.type", read_only=True)

    class Meta:
        model = LTIBudgetCell
        fields = [
            "id",
            "target_org_unit_id", "target_org_unit_name", "target_org_unit_type",
            "employee_category_1",
            "headcount_quota", "shares_quota_ads",
            "headcount_used", "shares_used_ads",
            "reclaimed_shares_ads",
        ]
