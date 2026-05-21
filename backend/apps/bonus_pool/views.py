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
from apps.audit.services import log_action
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.services.budget_distribution import compute_distribution
from apps.compensation_plan.services.org_targets import validate_target_set
from apps.bonus_pool.models import (
    BonusPlan,
    RegionalBonusRule,
    BonusCategoryFactor,
    BonusBudgetCell,
    BonusBudgetOverride,
)
from apps.bonus_pool.serializers import (
    BonusPlanSerializer,
    RegionalBonusRuleSerializer,
    BonusCategoryFactorSerializer,
    BonusBudgetCellSerializer,
    TargetBonusBudgetCellSerializer,
    BonusBudgetOverrideSerializer,
)
from apps.bonus_pool.services.budget_aggregation import aggregate_bonus_allocated
from apps.bonus_pool.services.budget_derivation import derive_bonus_budget


CATEGORIES = ["MANAGEMENT", "STAFF"]


class _BonusCascadeBlocked(Exception):
    def __init__(self, payload):
        self.payload = payload
        super().__init__(str(payload))


class BonusPlanViewSet(viewsets.ModelViewSet):
    queryset = BonusPlan.objects.all().order_by("-id")
    serializer_class = BonusPlanSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def perform_create(self, serializer):
        instance = serializer.save(created_by_id=self.request.user.id)
        log_action(
            event="CREATE", actor=self.request.user,
            resource_type="BonusPlan", resource_id=instance.id,
            before={}, after=serializer.data,
        )

    def perform_update(self, serializer):
        before = BonusPlanSerializer(serializer.instance).data
        instance = serializer.save()
        log_action(
            event="UPDATE", actor=self.request.user,
            resource_type="BonusPlan", resource_id=instance.id,
            before=before, after=serializer.data,
        )

    def perform_destroy(self, instance):
        before = BonusPlanSerializer(instance).data
        rid = instance.id
        instance.delete()
        log_action(
            event="DELETE", actor=self.request.user,
            resource_type="BonusPlan", resource_id=rid,
            before=before, after={},
        )


class RegionalBonusRuleViewSet(viewsets.ModelViewSet):
    queryset = RegionalBonusRule.objects.all()
    serializer_class = RegionalBonusRuleSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        qs = super().get_queryset().order_by("country")
        cycle = self.request.query_params.get("cycle")
        if cycle:
            qs = qs.filter(reward_cycle_id=cycle)
        return qs


class BonusCategoryFactorViewSet(viewsets.ModelViewSet):
    queryset = BonusCategoryFactor.objects.all()
    serializer_class = BonusCategoryFactorSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        qs = super().get_queryset().order_by("employee_category_1")
        cycle = self.request.query_params.get("cycle")
        if cycle:
            qs = qs.filter(reward_cycle_id=cycle)
        return qs


def _ensure_company_bonus_cells(cycle):
    for cat in CATEGORIES:
        BonusBudgetCell.objects.get_or_create(
            reward_cycle=cycle, employee_category_1=cat, target_org_unit=None,
            defaults={"budget_amount_cny": 0, "allocated_amount_cny": 0},
        )


def _company_bonus_cell(cycle, cat):
    return BonusBudgetCell.objects.get(
        reward_cycle=cycle, employee_category_1=cat, target_org_unit__isnull=True,
    )


def _attach_bonus_allocated(cells, allocated_map):
    for cell in cells:
        if cell.target_org_unit_id is None:
            continue
        key = (cell.target_org_unit_id, cell.employee_category_1)
        cell.allocated_amount_cny = allocated_map.get(key, Decimal("0"))


class BonusBudgetView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        _ensure_company_bonus_cells(cycle)

        company_cells = list(
            BonusBudgetCell.objects.filter(
                reward_cycle=cycle, target_org_unit__isnull=True
            ).order_by("employee_category_1")
        )
        target_cells = list(
            BonusBudgetCell.objects.filter(
                reward_cycle=cycle, target_org_unit__isnull=False
            ).select_related("target_org_unit").order_by(
                "employee_category_1", "target_org_unit__code"
            )
        )

        allocated_map = aggregate_bonus_allocated(cycle)
        _attach_bonus_allocated(target_cells, allocated_map)

        return Response({
            "rows": BonusBudgetCellSerializer(company_cells, many=True).data,
            "company": BonusBudgetCellSerializer(company_cells, many=True).data,
            "targets": TargetBonusBudgetCellSerializer(target_cells, many=True).data,
        })

    def put(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        _ensure_company_bonus_cells(cycle)
        rows = request.data.get("rows", [])

        for row in rows:
            cat = row.get("employee_category_1")
            if cat not in CATEGORIES:
                return Response(
                    {"error": f"invalid category: {cat}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        cascade = []
        try:
            with transaction.atomic():
                for row in rows:
                    cat = row.get("employee_category_1")
                    cell = _company_bonus_cell(cycle, cat)
                    cell.budget_amount_cny = Decimal(str(row.get("budget_amount_cny", 0)))
                    cell.save(update_fields=["budget_amount_cny"])

                allocated_map = aggregate_bonus_allocated(cycle)
                for cat in CATEGORIES:
                    company = _company_bonus_cell(cycle, cat)
                    rule = company.distribution_rule
                    if rule not in ("HEADCOUNT", "SALARY_TOTAL"):
                        continue
                    existing_ids = list(
                        BonusBudgetCell.objects.filter(
                            reward_cycle=cycle, employee_category_1=cat,
                            target_org_unit__isnull=False,
                        ).values_list("target_org_unit_id", flat=True)
                    )
                    if not existing_ids:
                        continue
                    distribution = compute_distribution(
                        total=company.budget_amount_cny,
                        cat1=cat, mode=rule,
                        target_unit_ids=existing_ids,
                    )
                    for ou_id, new_amount in distribution.items():
                        actual = allocated_map.get((ou_id, cat), Decimal("0"))
                        if new_amount < actual:
                            raise _BonusCascadeBlocked({
                                "employee_category_1": cat,
                                "target_org_unit_id": ou_id,
                                "rule": rule,
                                "requested": str(new_amount),
                                "already_allocated": str(actual),
                            })
                    for ou_id, new_amount in distribution.items():
                        BonusBudgetCell.objects.filter(
                            reward_cycle=cycle, employee_category_1=cat,
                            target_org_unit_id=ou_id,
                        ).update(budget_amount_cny=new_amount)
                    cascade.append({
                        "employee_category_1": cat,
                        "rule": rule,
                        "distribution": {str(k): str(v) for k, v in distribution.items()},
                    })
        except _BonusCascadeBlocked as e:
            return Response(
                {"error": "DEPT_REDUCE_BELOW_ALLOCATED", "detail": e.payload},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_action(
            event="UPDATE", actor=request.user,
            resource_type="BonusBudget", resource_id=cycle.id,
            before={}, after={"rows": rows, "cascade": cascade},
        )
        company_cells = BonusBudgetCell.objects.filter(
            reward_cycle=cycle, target_org_unit__isnull=True
        ).order_by("employee_category_1")
        return Response({
            "rows": BonusBudgetCellSerializer(company_cells, many=True).data,
            "cascade": cascade,
        })


class PatchBonusTargetsView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def patch(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        items = request.data.get("targets") or []
        if not items:
            return Response({"error": "targets required"}, status=400)

        ids = [int(it.get("id")) for it in items if it.get("id") is not None]
        cells = list(
            BonusBudgetCell.objects.filter(
                id__in=ids, reward_cycle=cycle, target_org_unit__isnull=False,
            )
        )
        if len(cells) != len(set(ids)):
            return Response({"error": "unknown or out-of-cycle cell id"}, status=400)
        cells_by_id = {c.id: c for c in cells}

        allocated_map = aggregate_bonus_allocated(cycle)
        try:
            with transaction.atomic():
                for it in items:
                    cell = cells_by_id[int(it["id"])]
                    new_amount = Decimal(str(it.get("budget_amount_cny", 0)))
                    actual = allocated_map.get(
                        (cell.target_org_unit_id, cell.employee_category_1),
                        Decimal("0"),
                    )
                    if new_amount < actual:
                        raise _BonusCascadeBlocked({
                            "employee_category_1": cell.employee_category_1,
                            "target_org_unit_id": cell.target_org_unit_id,
                            "requested": str(new_amount),
                            "already_allocated": str(actual),
                        })
                    cell.budget_amount_cny = new_amount
                    cell.save(update_fields=["budget_amount_cny"])
        except _BonusCascadeBlocked as e:
            return Response(
                {"error": "DEPT_REDUCE_BELOW_ALLOCATED", "detail": e.payload},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_action(
            event="UPDATE", actor=request.user,
            resource_type="BonusBudgetTargets", resource_id=cycle.id,
            before={}, after={"targets": items},
        )
        return Response({"ok": True, "updated": len(items)})


class DistributeBonusBudgetView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def post(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        _ensure_company_bonus_cells(cycle)

        cat = request.data.get("employee_category_1")
        mode = request.data.get("mode")
        target_ids = request.data.get("target_org_unit_ids") or []
        manual_amounts = request.data.get("manual_amounts") or {}
        dry_run = bool(request.data.get("dry_run"))

        if cat not in CATEGORIES:
            return Response(
                {"error": "invalid employee_category_1"},
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

        ous = list(OrgUnit.objects.filter(id__in=target_ids))
        if len(ous) != len(set(int(i) for i in target_ids)):
            return Response({"error": "unknown org_unit id in targets"}, status=400)
        for ou in ous:
            if ou.type not in ("DEPT", "CENTER"):
                return Response(
                    {"error": "INVALID_TARGET_TYPE", "detail": f"{ou.code} type={ou.type}"},
                    status=400,
                )

        company = _company_bonus_cell(cycle, cat)
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

        if not dry_run:
            allocated_map = aggregate_bonus_allocated(cycle)
            for ou_id, new_amount in distribution.items():
                actual = allocated_map.get((ou_id, cat), Decimal("0"))
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
            BonusBudgetCell.objects.filter(
                reward_cycle=cycle, employee_category_1=cat,
                target_org_unit__isnull=False,
            ).delete()
            for ou_id, amount in distribution.items():
                BonusBudgetCell.objects.create(
                    reward_cycle=cycle,
                    employee_category_1=cat,
                    target_org_unit_id=ou_id,
                    budget_amount_cny=amount,
                )
            company.distribution_rule = mode
            company.save(update_fields=["distribution_rule"])

        log_action(
            event="DISTRIBUTE", actor=request.user,
            resource_type="BonusBudget", resource_id=cycle.id,
            before={}, after={
                "employee_category_1": cat, "mode": mode,
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


class BonusDerivedBudgetView(APIView):
    """派生预算总览：部门池 + (country × category) 切片。"""
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        result = derive_bonus_budget(cycle)
        rows = []
        for r in result["rows"]:
            rows.append({
                **r,
                "salary_sum_cny": str(r["salary_sum_cny"]),
                "base_months": str(r["base_months"]) if r["base_months"] is not None else None,
                "factor": str(r["factor"]) if r["factor"] is not None else None,
                "derived_amount_cny": str(r["derived_amount_cny"]),
            })
        departments = []
        for d in result["departments"]:
            departments.append({
                **d,
                "derived_amount_cny": str(d["derived_amount_cny"]),
                "override_amount_cny": str(d["override_amount_cny"]) if d["override_amount_cny"] is not None else None,
                "effective_amount_cny": str(d["effective_amount_cny"]),
            })
        return Response({
            "cycle_id": cycle.id,
            "cycle_code": cycle.code,
            "departments": departments,
            "rows": rows,
            "total_derived_cny": str(result["total_derived_cny"]),
            "total_effective_cny": str(result["total_effective_cny"]),
            "skipped_no_salary_count": result["skipped_no_salary_count"],
            "skipped_no_country_count": result["skipped_no_country_count"],
            "employee_total": result["employee_total"],
        })


class BonusBudgetOverrideViewSet(viewsets.ModelViewSet):
    """部门池派生预算的人工覆盖值 CRUD（按 cycle 过滤）。"""
    queryset = BonusBudgetOverride.objects.all().select_related("department")
    serializer_class = BonusBudgetOverrideSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        qs = super().get_queryset().order_by("department__code")
        cycle = self.request.query_params.get("cycle")
        if cycle:
            qs = qs.filter(reward_cycle_id=cycle)
        return qs

    def perform_create(self, serializer):
        instance = serializer.save(uploaded_by=self.request.user, source="MANUAL")
        log_action(
            event="CREATE", actor=self.request.user,
            resource_type="BonusBudgetOverride", resource_id=instance.id,
            before={}, after=serializer.data,
        )

    def perform_update(self, serializer):
        before = BonusBudgetOverrideSerializer(serializer.instance).data
        instance = serializer.save(uploaded_by=self.request.user)
        log_action(
            event="UPDATE", actor=self.request.user,
            resource_type="BonusBudgetOverride", resource_id=instance.id,
            before=before, after=serializer.data,
        )


class BonusBudgetOverrideClearView(APIView):
    """清空指定 (cycle, dept) 的 override → 回到 DERIVED。"""
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def delete(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        dept_id = request.query_params.get("department_id")
        if not dept_id:
            return Response(
                {"detail": "department_id 必填"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = BonusBudgetOverride.objects.filter(
            reward_cycle=cycle, department_id=dept_id,
        ).delete()
        log_action(
            event="bonus_budget_override.clear",
            actor=request.user,
            resource_type="reward_cycle",
            resource_id=cycle.id,
            before={},
            after={"department_id": int(dept_id), "deleted": deleted},
        )
        return Response({"deleted": deleted})


class MyBonusBudgetView(APIView):
    """DEPT_HEAD / CENTER_HEAD 看自己负责单元的年终奖额度。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cycle_id = request.query_params.get("cycle_id")
        if not cycle_id:
            return Response({"error": "cycle_id required"}, status=400)
        cycle = get_object_or_404(RewardCycle, id=cycle_id)

        scope = resolve_user_org_scope(request.user)
        scope_ids = list(scope.filter(type__in=("DEPT", "CENTER")).values_list("id", flat=True))

        cells = list(
            BonusBudgetCell.objects.filter(
                reward_cycle=cycle,
                target_org_unit__isnull=False,
                target_org_unit_id__in=scope_ids,
            ).select_related("target_org_unit").order_by(
                "target_org_unit__code", "employee_category_1"
            )
        )
        allocated_map = aggregate_bonus_allocated(cycle)
        _attach_bonus_allocated(cells, allocated_map)

        return Response({
            "cycle_id": cycle.id,
            "targets": TargetBonusBudgetCellSerializer(cells, many=True).data,
        })
