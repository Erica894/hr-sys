from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.iam.permissions import IsHRAdmin
from apps.iam.scoping import resolve_user_org_scope
from apps.iam.models import OrgUnit
from apps.compensation_plan.models import AdjustmentPlan, AdjustmentBudgetCell
from apps.compensation_plan.serializers import (
    AdjustmentPlanSerializer,
    AdjustmentBudgetCellSerializer,
    TargetAdjustmentBudgetCellSerializer,
)
from apps.compensation_plan.services.budget_distribution import compute_distribution
from apps.compensation_plan.services.budget_aggregation import (
    aggregate_adjustment_allocated,
)
from apps.compensation_plan.services.org_targets import validate_target_set
from apps.reward_cycle.models import RewardCycle
from apps.audit.services import log_action


ADJ_TYPES = ["ANNUAL", "PROMOTION"]
CATEGORIES = ["MANAGEMENT", "STAFF"]


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
            cell = _company_cell(cycle, adj, cat)
            cell.budget_amount_cny = Decimal(str(row.get("budget_amount_cny", 0)))
            cell.save(update_fields=["budget_amount_cny"])
        log_action(
            event="UPDATE", actor=request.user,
            resource_type="AdjustmentBudget", resource_id=cycle.id,
            before={}, after={"rows": rows},
        )
        company_cells = AdjustmentBudgetCell.objects.filter(
            reward_cycle=cycle, department__isnull=True
        ).order_by("adjustment_type", "employee_category_1")
        return Response({"rows": AdjustmentBudgetCellSerializer(company_cells, many=True).data})


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
