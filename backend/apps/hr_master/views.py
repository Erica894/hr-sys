from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.iam.permissions import IsHRAdmin
from apps.hr_master.models import (
    CategoryScheme,
    EmployeeCategory,
    EmployeeCategoryAssignment,
    Employee,
)
from apps.hr_master.serializers import (
    CategorySchemeSerializer,
    EmployeeCategorySerializer,
    EmployeeCategoryAssignmentSerializer,
)
from apps.audit.services import log_action


class CategorySchemeViewSet(viewsets.ModelViewSet):
    queryset = CategoryScheme.objects.all().prefetch_related("categories")
    serializer_class = CategorySchemeSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def perform_create(self, serializer):
        instance = serializer.save()
        log_action(
            event="CREATE", actor=self.request.user,
            resource_type="CategoryScheme", resource_id=instance.id,
            before={}, after=serializer.data,
        )

    def perform_update(self, serializer):
        before = CategorySchemeSerializer(serializer.instance).data
        instance = serializer.save()
        log_action(
            event="UPDATE", actor=self.request.user,
            resource_type="CategoryScheme", resource_id=instance.id,
            before=before, after=serializer.data,
        )

    def perform_destroy(self, instance):
        if instance.assignments.exists() or instance.reward_cycles.exists():
            return Response(
                {"error": "SCHEME_IN_USE",
                 "detail": "方案已被员工赋桶或周期绑定，无法删除；请先归档或迁移"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rid = instance.id
        instance.delete()
        log_action(
            event="DELETE", actor=self.request.user,
            resource_type="CategoryScheme", resource_id=rid,
            before={}, after={},
        )

    @action(detail=True, methods=["get"], url_path="filter-facets")
    def filter_facets(self, request, pk=None):
        """前端构造筛选面板用的可选值清单 (职级/岗位/部门 distinct)。"""
        levels = list(
            Employee.objects
            .exclude(job_level_current="")
            .values_list("job_level_current", flat=True)
            .distinct().order_by("job_level_current")
        )
        families = list(
            Employee.objects
            .exclude(job_family="")
            .values_list("job_family", flat=True)
            .distinct().order_by("job_family")
        )
        depts = list(
            Employee.objects
            .exclude(dept_name="")
            .values_list("dept_name", flat=True)
            .distinct().order_by("dept_name")
        )
        return Response({"job_levels": levels, "job_families": families, "depts": depts})

    @action(detail=True, methods=["post"], url_path="bulk-assign")
    def bulk_assign(self, request, pk=None):
        """按"个人标签"多条件筛选员工 → 批量赋到一个桶。

        body:
        {
          "category_code": "MGMT",
          "filters": {
            "job_levels": ["M1", "M2"],      # 多选, OR
            "job_families": ["ENG"],          # 多选, OR (可空)
            "depts": ["ENG"],                 # 多选, OR (可空)
            "position_contains": "Manager",   # 子串匹配 (可空)
            "has_reports": true | false | null  # 是否有直接下属
          },
          "dry_run": true   # true 只返回命中名单不写库
        }
        """
        scheme = self.get_object()
        cat_code = request.data.get("category_code")
        filters = request.data.get("filters") or {}
        dry_run = bool(request.data.get("dry_run"))

        if not cat_code:
            return Response({"error": "category_code required"}, status=400)
        try:
            cat = scheme.categories.get(code=cat_code)
        except EmployeeCategory.DoesNotExist:
            return Response(
                {"error": "CATEGORY_NOT_IN_SCHEME", "detail": cat_code},
                status=400,
            )

        qs = Employee.objects.all()
        levels = filters.get("job_levels") or []
        families = filters.get("job_families") or []
        depts = filters.get("depts") or []
        pos_kw = (filters.get("position_contains") or "").strip()
        has_reports = filters.get("has_reports")

        if levels:
            qs = qs.filter(job_level_current__in=levels)
        if families:
            qs = qs.filter(job_family__in=families)
        if depts:
            qs = qs.filter(dept_name__in=depts)
        if pos_kw:
            qs = qs.filter(position_current__icontains=pos_kw)
        if has_reports is True:
            qs = qs.filter(reports__isnull=False).distinct()
        elif has_reports is False:
            qs = qs.filter(reports__isnull=True)

        # 命中预览总是返回
        matched = list(qs.values(
            "id", "employee_no", "name_cn", "dept_name",
            "job_level_current", "position_current",
        ))

        if dry_run:
            return Response({"matched_count": len(matched), "matched": matched})

        if not matched:
            return Response({"updated": 0, "matched": []})

        with transaction.atomic():
            for emp_id in [m["id"] for m in matched]:
                EmployeeCategoryAssignment.objects.update_or_create(
                    employee_id=emp_id, scheme=scheme,
                    defaults={"category": cat},
                )
        return Response({"updated": len(matched), "matched": matched})


class EmployeeCategoryViewSet(viewsets.ModelViewSet):
    queryset = EmployeeCategory.objects.all().select_related("scheme")
    serializer_class = EmployeeCategorySerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        scheme_id = self.request.query_params.get("scheme")
        if scheme_id:
            qs = qs.filter(scheme_id=scheme_id)
        return qs

    def perform_destroy(self, instance):
        if instance.assignments.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {"error": "CATEGORY_IN_USE",
                 "detail": f"已有 {instance.assignments.count()} 名员工绑定此桶"},
            )
        instance.delete()


class EmployeeCategoryAssignmentViewSet(viewsets.ModelViewSet):
    queryset = (
        EmployeeCategoryAssignment.objects
        .select_related("employee", "scheme", "category")
        .order_by("employee__employee_no")
    )
    serializer_class = EmployeeCategoryAssignmentSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        scheme = self.request.query_params.get("scheme")
        category = self.request.query_params.get("category")
        dept = self.request.query_params.get("dept")
        if scheme:
            qs = qs.filter(scheme_id=scheme)
        if category:
            qs = qs.filter(category_id=category)
        if dept:
            qs = qs.filter(employee__dept_name=dept)
        return qs

    @action(detail=False, methods=["get"], url_path="missing")
    def missing(self, request):
        """列出指定方案下尚未赋桶的员工。"""
        scheme_id = request.query_params.get("scheme")
        if not scheme_id:
            return Response({"error": "scheme is required"}, status=400)
        assigned_ids = (
            EmployeeCategoryAssignment.objects
            .filter(scheme_id=scheme_id)
            .values_list("employee_id", flat=True)
        )
        unassigned = Employee.objects.exclude(id__in=assigned_ids).values(
            "id", "employee_no", "name_cn", "dept_name", "employee_category_1",
        )
        return Response(list(unassigned))
