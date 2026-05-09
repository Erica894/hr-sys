from rest_framework import serializers
from apps.compensation_plan.models import AdjustmentPlan, AdjustmentBudgetCell


class AdjustmentPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjustmentPlan
        fields = [
            "id", "code", "name", "period", "status",
            "budget_total_cny", "scope", "formula", "rounding_rule",
            "reward_cycle", "created_by_id", "created_at",
        ]
        read_only_fields = ["id", "created_by_id", "created_at"]


class AdjustmentBudgetCellSerializer(serializers.ModelSerializer):
    remaining_amount_cny = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )

    class Meta:
        model = AdjustmentBudgetCell
        fields = [
            "adjustment_type", "employee_category_1",
            "budget_amount_cny", "allocated_amount_cny", "remaining_amount_cny",
        ]
        read_only_fields = ["allocated_amount_cny", "remaining_amount_cny"]
