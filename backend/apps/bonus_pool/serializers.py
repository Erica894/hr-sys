from rest_framework import serializers
from apps.bonus_pool.models import (
    BonusPlan,
    RegionalBonusRule,
    BonusCategoryFactor,
    BonusBudgetCell,
    BonusBudgetOverride,
    BonusProposal,
)


class BonusPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BonusPlan
        fields = [
            "id", "code", "name", "period", "status",
            "budget_total_cny", "scope", "formula",
            "reward_cycle", "created_by_id", "created_at",
        ]
        read_only_fields = ["id", "created_by_id", "created_at"]


class RegionalBonusRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegionalBonusRule
        fields = [
            "id", "reward_cycle", "country", "base_months", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BonusCategoryFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = BonusCategoryFactor
        fields = [
            "id", "reward_cycle", "employee_category_1", "factor", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BonusBudgetCellSerializer(serializers.ModelSerializer):
    """公司层 cell（target_org_unit IS NULL）。"""
    remaining_amount_cny = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )

    class Meta:
        model = BonusBudgetCell
        fields = [
            "employee_category_1",
            "budget_amount_cny", "allocated_amount_cny", "remaining_amount_cny",
            "distribution_rule",
        ]
        read_only_fields = ["allocated_amount_cny", "remaining_amount_cny"]


class TargetBonusBudgetCellSerializer(serializers.ModelSerializer):
    """目标层 cell（带 OrgUnit 名称/类型）。"""
    target_org_unit_id = serializers.IntegerField(source="target_org_unit.id", read_only=True)
    target_org_unit_name = serializers.CharField(source="target_org_unit.name", read_only=True)
    target_org_unit_type = serializers.CharField(source="target_org_unit.type", read_only=True)
    remaining_amount_cny = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )

    class Meta:
        model = BonusBudgetCell
        fields = [
            "id",
            "target_org_unit_id", "target_org_unit_name", "target_org_unit_type",
            "employee_category_1",
            "budget_amount_cny", "allocated_amount_cny",
            "remaining_amount_cny", "reclaimed_amount_cny",
        ]


class BonusBudgetOverrideSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = BonusBudgetOverride
        fields = [
            "id", "reward_cycle", "department", "department_name",
            "override_amount_cny", "source", "notes", "uploaded_at",
        ]
        read_only_fields = ["id", "uploaded_at", "department_name"]


class BonusProposalSerializer(serializers.ModelSerializer):
    employee_no = serializers.CharField(source="employee.employee_no", read_only=True)
    name_cn = serializers.CharField(source="employee.name_cn", read_only=True)
    total_amount_cny = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = BonusProposal
        fields = [
            "id", "plan", "employee", "employee_no", "name_cn",
            "status", "proposer_id",
            "suggested_amount_cny", "manager_delta_amount_cny",
            "final_amount_cny", "total_amount_cny",
            "employee_category_1_snapshot", "country_snapshot",
            "monthly_salary_snapshot", "reason",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "employee_no", "name_cn", "total_amount_cny",
            "created_at", "updated_at",
        ]
