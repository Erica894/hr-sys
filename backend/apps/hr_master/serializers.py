from rest_framework import serializers
from apps.hr_master.models import (
    CategoryScheme,
    EmployeeCategory,
    EmployeeCategoryAssignment,
    Employee,
)


class EmployeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeCategory
        fields = ["id", "scheme", "code", "name", "sort_order"]
        read_only_fields = ["id"]


class CategorySchemeSerializer(serializers.ModelSerializer):
    categories = EmployeeCategorySerializer(many=True, read_only=True)
    assignment_count = serializers.SerializerMethodField()

    class Meta:
        model = CategoryScheme
        fields = [
            "id", "code", "name", "status", "description",
            "created_at", "categories", "assignment_count",
        ]
        read_only_fields = ["id", "created_at", "categories", "assignment_count"]

    def get_assignment_count(self, obj):
        return obj.assignments.count()


class EmployeeCategoryAssignmentSerializer(serializers.ModelSerializer):
    employee_no = serializers.CharField(source="employee.employee_no", read_only=True)
    employee_name = serializers.CharField(source="employee.name_cn", read_only=True)
    dept_name = serializers.CharField(source="employee.dept_name", read_only=True)
    category_code = serializers.CharField(source="category.code", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = EmployeeCategoryAssignment
        fields = [
            "id", "employee", "scheme", "category",
            "employee_no", "employee_name", "dept_name",
            "category_code", "category_name",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "employee_no", "employee_name", "dept_name",
            "category_code", "category_name",
        ]

    def validate(self, attrs):
        scheme = attrs.get("scheme") or getattr(self.instance, "scheme", None)
        category = attrs.get("category") or getattr(self.instance, "category", None)
        if scheme and category and category.scheme_id != scheme.id:
            raise serializers.ValidationError(
                {"category": "类别桶必须属于当前方案"}
            )
        return attrs
