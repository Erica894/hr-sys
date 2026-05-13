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
    """公司层 cell 的标准序列化（向后兼容现有 FE）。"""
    remaining_amount_cny = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )

    class Meta:
        model = AdjustmentBudgetCell
        fields = [
            "adjustment_type", "employee_category_1",
            "budget_amount_cny", "allocated_amount_cny", "remaining_amount_cny",
            "distribution_rule",
        ]
        read_only_fields = ["allocated_amount_cny", "remaining_amount_cny"]


class TargetAdjustmentBudgetCellSerializer(serializers.ModelSerializer):
    """目标层 cell 序列化：附带 OrgUnit 名称和类型。"""
    target_org_unit_id = serializers.IntegerField(source="department_id", read_only=True)
    target_org_unit_name = serializers.CharField(source="department.name", read_only=True)
    target_org_unit_type = serializers.CharField(source="department.type", read_only=True)
    remaining_amount_cny = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )

    class Meta:
        model = AdjustmentBudgetCell
        fields = [
            "id",
            "target_org_unit_id", "target_org_unit_name", "target_org_unit_type",
            "adjustment_type", "employee_category_1",
            "budget_amount_cny", "allocated_amount_cny",
            "remaining_amount_cny", "reclaimed_amount_cny",
        ]
