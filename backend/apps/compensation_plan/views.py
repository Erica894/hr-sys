from decimal import Decimal
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.iam.permissions import IsHRAdmin
from apps.iam.scoping import resolve_user_org_scope
from apps.iam.models import OrgUnit
from apps.compensation_plan.models import (
    AdjustmentPlan,
    AdjustmentBudgetCell,
    AdjustmentMatrixCell,
    BudgetOverride,
    RegionalAdjustmentRule,
    EmployeeCategoryFactor,
)
from apps.compensation_plan.serializers import (
    AdjustmentPlanSerializer,
    AdjustmentBudgetCellSerializer,
    AdjustmentMatrixCellSerializer,
    TargetAdjustmentBudgetCellSerializer,
    RegionalAdjustmentRuleSerializer,
    EmployeeCategoryFactorSerializer,
)
from apps.compensation_plan.services.budget_distribution import compute_distribution
from apps.compensation_plan.services.budget_aggregation import (
    aggregate_adjustment_allocated,
)
from apps.compensation_plan.services.budget_derivation import derive_budget
from apps.compensation_plan.services.budget_override_import import (
    ImportError as OverrideImportError,
    build_template_xlsx,
    import_overrides,
)
from apps.compensation_plan.services.org_targets import validate_target_set
from apps.reward_cycle.models import RewardCycle
from apps.audit.services import log_action


ADJ_TYPES = ["ANNUAL", "PROMOTION"]
CATEGORIES = ["MANAGEMENT", "STAFF"]


class _CascadeBlocked(Exception):
    def __init__(self, payload):
        self.payload = payload
        super().__init__(str(payload))


class AdjustmentPlanViewSet(viewsets.ModelViewSet):
    queryset = AdjustmentPlan.objects.all().order_by("-id")
    serializer_class = AdjustmentPlanSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def perform_create(self, serializer):
        instance = serializer.save(created_by_id=self.request.user.id)
        log_action(
            event="CREATE", actor=self.request.user,
            resource_type="AdjustmentPlan", resource_id=instance.id,
            before={}, after=serializer.data,
        )

    def perform_update(self, serializer):
        before = AdjustmentPlanSerializer(serializer.instance).data
        instance = serializer.save()
        log_action(
            event="UPDATE", actor=self.request.user,
            resource_type="AdjustmentPlan", resource_id=instance.id,
            before=before, after=serializer.data,
        )

    def perform_destroy(self, instance):
        before = AdjustmentPlanSerializer(instance).data
        rid = instance.id
        instance.delete()
        log_action(
            event="DELETE", actor=self.request.user,
            resource_type="AdjustmentPlan", resource_id=rid,
            before=before, after={},
        )


def _ensure_company_cells(cycle):
    for adj in ADJ_TYPES:
        for cat in CATEGORIES:
            AdjustmentBudgetCell.objects.get_or_create(
                reward_cycle=cycle,
                adjustment_type=adj,
                employee_category_1=cat,
                department=None,
                defaults={"budget_amount_cny": 0, "allocated_amount_cny": 0},
            )


def _company_cell(cycle, adj, cat):
    return AdjustmentBudgetCell.objects.get(
        reward_cycle=cycle, adjustment_type=adj, employee_category_1=cat,
        department__isnull=True,
    )


def _attach_allocated(cells, allocated_map):
    """把 on-the-fly 聚合写入每个目标 cell 的 allocated_amount_cny（不入库）。"""
    for cell in cells:
        if cell.department_id is None:
            continue
        key = (cell.department_id, cell.adjustment_type, cell.employee_category_1)
        cell.allocated_amount_cny = allocated_map.get(key, Decimal("0"))


class AdjustmentBudgetView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        _ensure_company_cells(cycle)

        company_cells = list(
            AdjustmentBudgetCell.objects.filter(
                reward_cycle=cycle, department__isnull=True
            ).order_by("adjustment_type", "employee_category_1")
        )
        target_cells = list(
            AdjustmentBudgetCell.objects.filter(
                reward_cycle=cycle, department__isnull=False
            ).select_related("department").order_by(
                "adjustment_type", "employee_category_1", "department__code"
            )
        )

        allocated_map = aggregate_adjustment_allocated(cycle)
        _attach_allocated(target_cells, allocated_map)

        return Response({
            "rows": AdjustmentBudgetCellSerializer(company_cells, many=True).data,
            "company": AdjustmentBudgetCellSerializer(company_cells, many=True).data,
            "targets": TargetAdjustmentBudgetCellSerializer(target_cells, many=True).data,
        })

    def put(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        _ensure_company_cells(cycle)
        rows = request.data.get("rows", [])

        for row in rows:
            adj = row.get("adjustment_type")
            cat = row.get("employee_category_1")
            if adj not in ADJ_TYPES or cat not in CATEGORIES:
                return Response(
                    {"error": f"invalid adjustment_type/category: {adj}/{cat}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        cascade = []
        try:
            with transaction.atomic():
                for row in rows:
                    adj = row.get("adjustment_type")
                    cat = row.get("employee_category_1")
                    cell = _company_cell(cycle, adj, cat)
                    cell.budget_amount_cny = Decimal(str(row.get("budget_amount_cny", 0)))
                    cell.save(update_fields=["budget_amount_cny"])

                allocated_map = aggregate_adjustment_allocated(cycle)
                for adj in ADJ_TYPES:
                    for cat in CATEGORIES:
                        company = _company_cell(cycle, adj, cat)
                        rule = company.distribution_rule
                        if rule not in ("HEADCOUNT", "SALARY_TOTAL"):
                            continue
                        existing_ids = list(
                            AdjustmentBudgetCell.objects.filter(
                                reward_cycle=cycle, adjustment_type=adj,
                                employee_category_1=cat, department__isnull=False,
                            ).values_list("department_id", flat=True)
                        )
                        if not existing_ids:
                            continue
                        distribution = compute_distribution(
                            total=company.budget_amount_cny,
                            cat1=cat, mode=rule,
                            target_unit_ids=existing_ids,
                        )
                        for ou_id, new_amount in distribution.items():
                            actual = allocated_map.get((ou_id, adj, cat), Decimal("0"))
                            if new_amount < actual:
                                raise _CascadeBlocked({
                                    "adjustment_type": adj,
                                    "employee_category_1": cat,
                                    "target_org_unit_id": ou_id,
                                    "rule": rule,
                                    "requested": str(new_amount),
                                    "already_allocated": str(actual),
                                })
                        for ou_id, new_amount in distribution.items():
                            AdjustmentBudgetCell.objects.filter(
                                reward_cycle=cycle, adjustment_type=adj,
                                employee_category_1=cat, department_id=ou_id,
                            ).update(budget_amount_cny=new_amount)
                        cascade.append({
                            "adjustment_type": adj,
                            "employee_category_1": cat,
                            "rule": rule,
                            "distribution": {str(k): str(v) for k, v in distribution.items()},
                        })
        except _CascadeBlocked as e:
            return Response(
                {"error": "DEPT_REDUCE_BELOW_ALLOCATED", "detail": e.payload},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_action(
            event="UPDATE", actor=request.user,
            resource_type="AdjustmentBudget", resource_id=cycle.id,
            before={}, after={"rows": rows, "cascade": cascade},
        )
        company_cells = AdjustmentBudgetCell.objects.filter(
            reward_cycle=cycle, department__isnull=True
        ).order_by("adjustment_type", "employee_category_1")
        return Response({
            "rows": AdjustmentBudgetCellSerializer(company_cells, many=True).data,
            "cascade": cascade,
        })


class PatchAdjustmentTargetsView(APIView):
    """HR 在已下发部门表里手动微调单格金额; 带 allocated 护栏。"""
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def patch(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        items = request.data.get("targets") or []
        if not items:
            return Response({"error": "targets required"}, status=400)

        ids = [int(it.get("id")) for it in items if it.get("id") is not None]
        cells = list(
            AdjustmentBudgetCell.objects.filter(
                id__in=ids, reward_cycle=cycle, department__isnull=False,
            )
        )
        if len(cells) != len(set(ids)):
            return Response({"error": "unknown or out-of-cycle cell id"}, status=400)
        cells_by_id = {c.id: c for c in cells}

        allocated_map = aggregate_adjustment_allocated(cycle)
        try:
            with transaction.atomic():
                for it in items:
                    cell = cells_by_id[int(it["id"])]
                    new_amount = Decimal(str(it.get("budget_amount_cny", 0)))
                    actual = allocated_map.get(
                        (cell.department_id, cell.adjustment_type, cell.employee_category_1),
                        Decimal("0"),
                    )
                    if new_amount < actual:
                        raise _CascadeBlocked({
                            "adjustment_type": cell.adjustment_type,
                            "employee_category_1": cell.employee_category_1,
                            "target_org_unit_id": cell.department_id,
                            "requested": str(new_amount),
                            "already_allocated": str(actual),
                        })
                    cell.budget_amount_cny = new_amount
                    cell.save(update_fields=["budget_amount_cny"])
        except _CascadeBlocked as e:
            return Response(
                {"error": "DEPT_REDUCE_BELOW_ALLOCATED", "detail": e.payload},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_action(
            event="UPDATE", actor=request.user,
            resource_type="AdjustmentBudgetTargets", resource_id=cycle.id,
            before={}, after={"targets": items},
        )
        return Response({"ok": True, "updated": len(items)})


class DistributeAdjustmentBudgetView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def post(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        _ensure_company_cells(cycle)

        adj = request.data.get("adjustment_type")
        cat = request.data.get("employee_category_1")
        mode = request.data.get("mode")
        target_ids = request.data.get("target_org_unit_ids") or []
        manual_amounts = request.data.get("manual_amounts") or {}
        dry_run = bool(request.data.get("dry_run"))

        if adj not in ADJ_TYPES or cat not in CATEGORIES:
            return Response(
                {"error": "invalid adjustment_type/employee_category_1"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if mode not in ("MANUAL", "HEADCOUNT", "SALARY_TOTAL"):
            return Response({"error": "invalid mode"}, status=400)
        if not target_ids:
            return Response({"error": "target_org_unit_ids required"}, status=400)

        try:
            validate_target_set(target_ids)
        except ValueError as e:
            return Response(
                {"error": "TARGETS_OVERLAP", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = ("DEPT", "CENTER")
        ous = list(OrgUnit.objects.filter(id__in=target_ids))
        if len(ous) != len(set(int(i) for i in target_ids)):
            return Response({"error": "unknown org_unit id in targets"}, status=400)
        for ou in ous:
            if ou.type not in allowed_types:
                return Response(
                    {"error": "INVALID_TARGET_TYPE", "detail": f"{ou.code} type={ou.type}"},
                    status=400,
                )

        company = _company_cell(cycle, adj, cat)
        try:
            distribution = compute_distribution(
                total=company.budget_amount_cny,
                cat1=cat, mode=mode,
                target_unit_ids=[ou.id for ou in ous],
                manual_amounts=manual_amounts if mode == "MANUAL" else None,
            )
        except ValueError as e:
            return Response(
                {"error": "COMPUTE_FAILED", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 校验"不能减到 allocated 以下"：现有目标 cells 的实际分配不超新预算。
        if not dry_run:
            allocated_map = aggregate_adjustment_allocated(cycle)
            for ou_id, new_amount in distribution.items():
                actual = allocated_map.get((ou_id, adj, cat), Decimal("0"))
                if new_amount < actual:
                    return Response({
                        "error": "DEPT_REDUCE_BELOW_ALLOCATED",
                        "detail": {
                            "target_org_unit_id": ou_id,
                            "requested": str(new_amount),
                            "already_allocated": str(actual),
                        },
                    }, status=status.HTTP_400_BAD_REQUEST)

        if dry_run:
            return Response({
                "dry_run": True,
                "company_total": str(company.budget_amount_cny),
                "distribution": [
                    {"target_org_unit_id": k, "amount_cny": str(v)}
                    for k, v in distribution.items()
                ],
            })

        with transaction.atomic():
            AdjustmentBudgetCell.objects.filter(
                reward_cycle=cycle, adjustment_type=adj,
                employee_category_1=cat, department__isnull=False,
            ).delete()
            for ou_id, amount in distribution.items():
                AdjustmentBudgetCell.objects.create(
                    reward_cycle=cycle,
                    adjustment_type=adj,
                    employee_category_1=cat,
                    department_id=ou_id,
                    budget_amount_cny=amount,
                )
            company.distribution_rule = mode
            company.save(update_fields=["distribution_rule"])

        log_action(
            event="DISTRIBUTE", actor=request.user,
            resource_type="AdjustmentBudget", resource_id=cycle.id,
            before={}, after={
                "adjustment_type": adj, "employee_category_1": cat,
                "mode": mode,
                "distribution": {str(k): str(v) for k, v in distribution.items()},
            },
        )
        return Response({
            "ok": True,
            "distribution": [
                {"target_org_unit_id": k, "amount_cny": str(v)}
                for k, v in distribution.items()
            ],
        })


class MyAdjustmentBudgetView(APIView):
    """DEPT_HEAD / CENTER_HEAD 看自己负责单元的预算（按 OrgUnitManager 范围）。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cycle_id = request.query_params.get("cycle_id")
        if not cycle_id:
            return Response({"error": "cycle_id required"}, status=400)
        cycle = get_object_or_404(RewardCycle, id=cycle_id)

        scope = resolve_user_org_scope(request.user)
        scope_ids = list(scope.filter(type__in=("DEPT", "CENTER")).values_list("id", flat=True))

        cells = list(
            AdjustmentBudgetCell.objects.filter(
                reward_cycle=cycle,
                department__isnull=False,
                department_id__in=scope_ids,
            ).select_related("department").order_by(
                "department__code", "adjustment_type", "employee_category_1"
            )
        )
        allocated_map = aggregate_adjustment_allocated(cycle)
        _attach_allocated(cells, allocated_map)

        return Response({
            "cycle_id": cycle.id,
            "targets": TargetAdjustmentBudgetCellSerializer(cells, many=True).data,
        })


class RegionalAdjustmentRuleViewSet(viewsets.ModelViewSet):
    """层 1 规则 - 区域基准比例 CRUD."""
    queryset = RegionalAdjustmentRule.objects.all()
    serializer_class = RegionalAdjustmentRuleSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        qs = super().get_queryset().order_by("country", "adjustment_type")
        cycle = self.request.query_params.get("cycle")
        if cycle:
            qs = qs.filter(reward_cycle_id=cycle)
        return qs


class EmployeeCategoryFactorViewSet(viewsets.ModelViewSet):
    """层 1 规则 - 员工类别系数 CRUD."""
    queryset = EmployeeCategoryFactor.objects.all().select_related(
        "category", "category__scheme"
    )
    serializer_class = EmployeeCategoryFactorSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        qs = super().get_queryset().order_by("category__sort_order", "adjustment_type")
        cycle = self.request.query_params.get("cycle")
        if cycle:
            qs = qs.filter(reward_cycle_id=cycle)
        return qs


class DerivedBudgetView(APIView):
    """派生预算总览: 部门池 + (country × category × type) 切片的月度增量额。"""
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        result = derive_budget(cycle)
        rows = []
        for r in result["rows"]:
            rows.append({
                **r,
                "salary_sum_cny": str(r["salary_sum_cny"]),
                "base_pct": str(r["base_pct"]) if r["base_pct"] is not None else None,
                "factor": str(r["factor"]) if r["factor"] is not None else None,
                "derived_amount_cny": str(r["derived_amount_cny"]),
            })
        departments = []
        for d in result["departments"]:
            departments.append({
                **d,
                "derived_annual_cny": str(d["derived_annual_cny"]),
                "derived_promotion_cny": str(d["derived_promotion_cny"]),
                "derived_total_cny": str(d["derived_total_cny"]),
                "override_annual_cny": str(d["override_annual_cny"]) if d["override_annual_cny"] is not None else None,
                "override_promotion_cny": str(d["override_promotion_cny"]) if d["override_promotion_cny"] is not None else None,
                "effective_annual_cny": str(d["effective_annual_cny"]),
                "effective_promotion_cny": str(d["effective_promotion_cny"]),
                "effective_total_cny": str(d["effective_total_cny"]),
                "matrix_annual_cny": str(d["matrix_annual_cny"]),
                "matrix_promotion_cny": str(d["matrix_promotion_cny"]),
                "matrix_pool_cny": str(d["matrix_pool_cny"]),
                "discretionary_annual_cny": str(d["discretionary_annual_cny"]),
                "discretionary_promotion_cny": str(d["discretionary_promotion_cny"]),
                "discretionary_pool_cny": str(d["discretionary_pool_cny"]),
            })
        return Response({
            "cycle_id": cycle.id,
            "cycle_code": cycle.code,
            "departments": departments,
            "rows": rows,
            "total_derived_cny": str(result["total_derived_cny"]),
            "total_effective_cny": str(result["total_effective_cny"]),
            "total_matrix_cny": str(result["total_matrix_cny"]),
            "total_discretionary_cny": str(result["total_discretionary_cny"]),
            "discretionary_pct": str(result["discretionary_pct"]),
            "skipped_no_salary_count": result["skipped_no_salary_count"],
            "skipped_no_country_count": result["skipped_no_country_count"],
            "employee_total": result["employee_total"],
        })


class BudgetOverrideTemplateView(APIView):
    """下载批量导入空模板 (.xlsx)。"""
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, cycle_id):
        get_object_or_404(RewardCycle, id=cycle_id)
        content = build_template_xlsx()
        resp = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = (
            f'attachment; filename="budget-override-template-cycle-{cycle_id}.xlsx"'
        )
        return resp


class BudgetOverrideImportView(APIView):
    """批量导入部门池 override 值。整批校验失败 → 整批拒绝 + 行级错误清单。"""
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def post(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "缺少 file 字段"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            result = import_overrides(cycle, upload.read(), request.user)
        except OverrideImportError as exc:
            return Response(
                {"detail": "校验失败", "errors": exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_action(
            event="budget_override.import",
            actor=request.user,
            resource_type="reward_cycle",
            resource_id=cycle.id,
            before={},
            after=result,
        )
        return Response(result, status=status.HTTP_200_OK)


class BudgetOverrideClearView(APIView):
    """清空指定 (dept, adj_type) 的 override → 回到 DERIVED。"""
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def delete(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        dept_id = request.query_params.get("department_id")
        adj = request.query_params.get("adjustment_type")
        if not dept_id or adj not in ("ANNUAL", "PROMOTION"):
            return Response(
                {"detail": "department_id + adjustment_type 必填"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = BudgetOverride.objects.filter(
            reward_cycle=cycle, department_id=dept_id, adjustment_type=adj,
        ).delete()
        log_action(
            event="budget_override.clear",
            actor=request.user,
            resource_type="reward_cycle",
            resource_id=cycle.id,
            before={},
            after={"department_id": int(dept_id), "adjustment_type": adj, "deleted": deleted},
        )
        return Response({"deleted": deleted})


class AdjustmentMatrixCellViewSet(viewsets.ModelViewSet):
    """层 2 调薪矩阵单元格 CRUD - 按 cycle/category 过滤。"""
    queryset = AdjustmentMatrixCell.objects.all().select_related("category")
    serializer_class = AdjustmentMatrixCellSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        qs = super().get_queryset().order_by(
            "category__sort_order", "perf_grade_code", "pay_band",
        )
        cycle = self.request.query_params.get("cycle")
        category = self.request.query_params.get("category")
        if cycle:
            qs = qs.filter(reward_cycle_id=cycle)
        if category:
            qs = qs.filter(category_id=category)
        return qs
