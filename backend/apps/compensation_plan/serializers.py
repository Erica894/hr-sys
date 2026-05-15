from rest_framework import serializers
from apps.compensation_plan.models import (
    AdjustmentPlan,
    AdjustmentBudgetCell,
    AdjustmentMatrixCell,
    RegionalAdjustmentRule,
    EmployeeCategoryFactor,
)


class RegionalAdjustmentRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegionalAdjustmentRule
        fields = [
            "id", "reward_cycle", "country", "adjustment_type",
            "base_pct", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EmployeeCategoryFactorSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.code", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    scheme_code = serializers.CharField(source="category.scheme.code", read_only=True)

    class Meta:
        model = EmployeeCategoryFactor
        fields = [
            "id", "reward_cycle", "category", "adjustment_type",
            "factor", "notes",
            "category_code", "category_name", "scheme_code",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "category_code", "category_name", "scheme_code",
        ]

    def validate(self, attrs):
        cycle = attrs.get("reward_cycle") or getattr(self.instance, "reward_cycle", None)
        category = attrs.get("category") or getattr(self.instance, "category", None)
        if cycle and category:
            scheme = cycle.category_scheme
            if scheme is None or category.scheme_id != scheme.id:
                raise serializers.ValidationError(
                    {"category": "类别桶必须属于该周期绑定的方案"}
                )
        return attrs


class AdjustmentPlanSerializer(serializers.ModelSerializer):
    matrix_cell_count = serializers.SerializerMethodField()

    class Meta:
        model = AdjustmentPlan
        fields = [
            "id", "code", "name", "period", "status",
            "formula", "rounding_rule", "perf_grades",
            "reward_cycle", "created_by_id", "created_at",
            "matrix_cell_count",
        ]
        read_only_fields = ["id", "created_by_id", "created_at", "matrix_cell_count"]

    def get_matrix_cell_count(self, obj):
        if obj.reward_cycle_id is None:
            return 0
        return AdjustmentMatrixCell.objects.filter(reward_cycle_id=obj.reward_cycle_id).count()

    def validate_perf_grades(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("perf_grades 必须是列表")
        seen = set()
        for i, g in enumerate(value):
            if not isinstance(g, dict):
                raise serializers.ValidationError(f"perf_grades[{i}] 必须是对象")
            for key in ("code", "label", "sort_order"):
                if key not in g:
                    raise serializers.ValidationError(f"perf_grades[{i}] 缺少字段 {key}")
            if g["code"] in seen:
                raise serializers.ValidationError(f"perf_grades 中存在重复 code: {g['code']}")
            seen.add(g["code"])
        return value


class AdjustmentMatrixCellSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.code", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = AdjustmentMatrixCell
        fields = [
            "id", "reward_cycle", "category",
            "category_code", "category_name",
            "perf_grade_code", "pay_band",
            "coef_low", "coef_high", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "category_code", "category_name",
        ]

    def validate(self, attrs):
        cycle = attrs.get("reward_cycle") or getattr(self.instance, "reward_cycle", None)
        category = attrs.get("category") or getattr(self.instance, "category", None)
        perf_grade_code = attrs.get("perf_grade_code") or getattr(self.instance, "perf_grade_code", None)
        coef_low = attrs.get("coef_low", getattr(self.instance, "coef_low", None))
        coef_high = attrs.get("coef_high", getattr(self.instance, "coef_high", None))

        if coef_low is not None and coef_high is not None and coef_high < coef_low:
            raise serializers.ValidationError({"coef_high": "coef_high 不能小于 coef_low"})

        if cycle and category:
            scheme = cycle.category_scheme
            if scheme is None or category.scheme_id != scheme.id:
                raise serializers.ValidationError(
                    {"category": "类别必须属于该周期绑定的方案"}
                )

        if cycle and perf_grade_code:
            plan = cycle.adjustment_plans.first()
            if plan is None:
                raise serializers.ValidationError(
                    {"reward_cycle": "该周期还没有绑定的调薪方案"}
                )
            valid_codes = {g.get("code") for g in (plan.perf_grades or [])}
            if perf_grade_code not in valid_codes:
                raise serializers.ValidationError(
                    {"perf_grade_code": f"绩效档位 {perf_grade_code} 不在该方案的 perf_grades 列表中"}
                )

        return attrs


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
