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
    class Meta:
        model = LTIBudgetCell
        fields = [
            "employee_category_1",
            "headcount_quota", "shares_quota_ads",
            "headcount_used", "shares_used_ads",
        ]
        read_only_fields = ["headcount_used", "shares_used_ads"]
