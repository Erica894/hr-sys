from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentProposal
from apps.compensation_plan.services.budget_distribution import compute_distribution
from apps.compensation_plan.services.budget_aggregation import aggregate_lti_allocated
from apps.compensation_plan.services.org_targets import validate_target_set
from apps.iam.models import OrgUnit
from apps.iam.permissions import IsHRAdmin
from apps.iam.scoping import resolve_user_org_scope
from apps.lti.models import LTIGrant, EmployeeAck, LTIPlan, LTIBudgetCell
from apps.lti.serializers import (
    LTIPlanSerializer,
    LTIBudgetCellSerializer,
    TargetLTIBudgetCellSerializer,
)
from apps.hr_master.models import Employee
from apps.audit.services import log_action


def _employee_for(user):
    return Employee.objects.filter(user=user).first()


class EmployeeProposalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        emp = _employee_for(request.user)
        if not emp:
            return Response({"detail": "not an employee"}, status=404)
        if cycle.status != "EXECUTED":
            return Response({"detail": "cycle not executed"}, status=400)

        p = AdjustmentProposal.objects.filter(
            plan=cycle.linked_adjustment_plan, employee=emp
        ).first() if cycle.linked_adjustment_plan else None
        g = LTIGrant.objects.filter(
            plan=cycle.linked_lti_plan, employee=emp
        ).first() if cycle.linked_lti_plan else None
        ack = EmployeeAck.objects.filter(
            subject_type="REWARD_CYCLE", subject_id=cycle.id, employee=emp
        ).first()

        return Response({
            "cycle_code": cycle.code,
            "annual_final_pct": str(p.annual_final_pct) if p else None,
            "promotion_adjustment_pct": str(p.promotion_adjustment_pct) if p else None,
            "proposed_monthly_salary": str(p.proposed_salary) if p else None,
            "granted_ads": g.granted_ads if g else 0,
            "ack_status": "ACKNOWLEDGED" if ack else "PENDING",
            "ack_id": ack.id if ack else None,
        })


class AckView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        emp = _employee_for(request.user)
        if not emp:
            return Response({"detail": "not an employee"}, status=404)
        if cycle.status != "EXECUTED":
            return Response({"detail": "cycle not executed"}, status=400)

        ack, _ = EmployeeAck.objects.get_or_create(
            subject_type="REWARD_CYCLE", subject_id=cycle.id, employee=emp
        )
        log_action(
            "ACK", request.user, "RewardCycle", cycle.id,
            {}, {"employee_id": emp.id, "ack_id": ack.id},
        )
        return Response({"ack_id": ack.id, "status": "ACKNOWLEDGED"})


LTI_CATEGORIES = ["MANAGEMENT", "STAFF"]


class _LtiCascadeBlocked(Exception):
    def __init__(self, payload):
        self.payload = payload
        super().__init__(str(payload))


class LTIPlanViewSet(viewsets.ModelViewSet):
    queryset = LTIPlan.objects.all().order_by("-id")
    serializer_class = LTIPlanSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def perform_create(self, serializer):
        instance = serializer.save()
        log_action(
            "CREATE", self.request.user, "LTIPlan", instance.id,
            {}, serializer.data,
        )

    def perform_update(self, serializer):
        before = LTIPlanSerializer(serializer.instance).data
        instance = serializer.save()
        log_action(
            "UPDATE", self.request.user, "LTIPlan", instance.id,
            before, serializer.data,
        )

    def perform_destroy(self, instance):
        before = LTIPlanSerializer(instance).data
        rid = instance.id
        instance.delete()
        log_action(
            "DELETE", self.request.user, "LTIPlan", rid,
            before, {},
        )


def _ensure_company_lti_cells(plan):
    for cat in LTI_CATEGORIES:
        LTIBudgetCell.objects.get_or_create(
            plan=plan, employee_category_1=cat, target_org_unit=None,
            defaults={
                "headcount_quota": 0, "shares_quota_ads": 0,
                "headcount_used": 0, "shares_used_ads": 0,
            },
        )


def _company_lti_cell(plan, cat):
    return LTIBudgetCell.objects.get(
        plan=plan, employee_category_1=cat, target_org_unit__isnull=True,
    )


def _attach_lti_used(cells, allocated_map):
    for c in cells:
        if c.target_org_unit_id is None:
            continue
        c.shares_used_ads = int(allocated_map.get((c.target_org_unit_id, c.employee_category_1), 0))


class LTIBudgetView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def get(self, request, plan_id):
        plan = get_object_or_404(LTIPlan, id=plan_id)
        _ensure_company_lti_cells(plan)
        company_cells = list(
            LTIBudgetCell.objects.filter(
                plan=plan, target_org_unit__isnull=True
            ).order_by("employee_category_1")
        )
        target_cells = list(
            LTIBudgetCell.objects.filter(
                plan=plan, target_org_unit__isnull=False
            ).select_related("target_org_unit").order_by(
                "employee_category_1", "target_org_unit__code"
            )
        )
        allocated_map = aggregate_lti_allocated(plan)
        _attach_lti_used(target_cells, allocated_map)
        return Response({
            "rows": LTIBudgetCellSerializer(company_cells, many=True).data,
            "company": LTIBudgetCellSerializer(company_cells, many=True).data,
            "targets": TargetLTIBudgetCellSerializer(target_cells, many=True).data,
        })

    def put(self, request, plan_id):
        plan = get_object_or_404(LTIPlan, id=plan_id)
        _ensure_company_lti_cells(plan)
        rows = request.data.get("rows", [])

        for row in rows:
            cat = row.get("employee_category_1")
            if cat not in LTI_CATEGORIES:
                return Response(
                    {"error": f"invalid category: {cat}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        cascade = []
        try:
            with transaction.atomic():
                for row in rows:
                    cat = row.get("employee_category_1")
                    cell = _company_lti_cell(plan, cat)
                    cell.headcount_quota = int(row.get("headcount_quota", cell.headcount_quota))
                    cell.shares_quota_ads = int(row.get("shares_quota_ads", cell.shares_quota_ads))
                    cell.save(update_fields=["headcount_quota", "shares_quota_ads"])

                allocated_map = aggregate_lti_allocated(plan)
                for cat in LTI_CATEGORIES:
                    company = _company_lti_cell(plan, cat)
                    rule = company.distribution_rule
                    if rule not in ("HEADCOUNT", "SALARY_TOTAL"):
                        continue
                    existing_ids = list(
                        LTIBudgetCell.objects.filter(
                            plan=plan, employee_category_1=cat,
                            target_org_unit__isnull=False,
                        ).values_list("target_org_unit_id", flat=True)
                    )
                    if not existing_ids:
                        continue
                    distribution = compute_distribution(
                        total=company.shares_quota_ads,
                        cat1=cat, mode=rule,
                        target_unit_ids=existing_ids,
                        integer_units=True,
                    )
                    for ou_id, new_shares in distribution.items():
                        actual = int(allocated_map.get((ou_id, cat), 0))
                        if int(new_shares) < actual:
                            raise _LtiCascadeBlocked({
                                "employee_category_1": cat,
                                "target_org_unit_id": ou_id,
                                "rule": rule,
                                "requested": int(new_shares),
                                "already_allocated": actual,
                            })
                    for ou_id, new_shares in distribution.items():
                        LTIBudgetCell.objects.filter(
                            plan=plan, employee_category_1=cat,
                            target_org_unit_id=ou_id,
                        ).update(shares_quota_ads=int(new_shares))
                    cascade.append({
                        "employee_category_1": cat,
                        "rule": rule,
                        "distribution": {str(k): int(v) for k, v in distribution.items()},
                    })
        except _LtiCascadeBlocked as e:
            return Response(
                {"error": "DEPT_REDUCE_BELOW_ALLOCATED", "detail": e.payload},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_action(
            "UPDATE", request.user, "LTIBudget", plan.id,
            {}, {"rows": rows, "cascade": cascade},
        )
        cells = LTIBudgetCell.objects.filter(
            plan=plan, target_org_unit__isnull=True
        ).order_by("employee_category_1")
        return Response({
            "rows": LTIBudgetCellSerializer(cells, many=True).data,
            "cascade": cascade,
        })


class PatchLtiTargetsView(APIView):
    """HR 在已下发部门表里手动微调单格 RSU 股数; 带 allocated 护栏。"""
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def patch(self, request, plan_id):
        plan = get_object_or_404(LTIPlan, id=plan_id)
        items = request.data.get("targets") or []
        if not items:
            return Response({"error": "targets required"}, status=400)

        ids = [int(it.get("id")) for it in items if it.get("id") is not None]
        cells = list(
            LTIBudgetCell.objects.filter(
                id__in=ids, plan=plan, target_org_unit__isnull=False,
            )
        )
        if len(cells) != len(set(ids)):
            return Response({"error": "unknown or out-of-plan cell id"}, status=400)
        cells_by_id = {c.id: c for c in cells}

        allocated_map = aggregate_lti_allocated(plan)
        try:
            with transaction.atomic():
                for it in items:
                    cell = cells_by_id[int(it["id"])]
                    new_shares = int(it.get("shares_quota_ads", 0))
                    actual = int(allocated_map.get(
                        (cell.target_org_unit_id, cell.employee_category_1), 0
                    ))
                    if new_shares < actual:
                        raise _LtiCascadeBlocked({
                            "employee_category_1": cell.employee_category_1,
                            "target_org_unit_id": cell.target_org_unit_id,
                            "requested": new_shares,
                            "already_allocated": actual,
                        })
                    cell.shares_quota_ads = new_shares
                    cell.save(update_fields=["shares_quota_ads"])
        except _LtiCascadeBlocked as e:
            return Response(
                {"error": "DEPT_REDUCE_BELOW_ALLOCATED", "detail": e.payload},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_action(
            "UPDATE", request.user, "LTIBudgetTargets", plan.id,
            {}, {"targets": items},
        )
        return Response({"ok": True, "updated": len(items)})


class DistributeLtiBudgetView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def post(self, request, plan_id):
        plan = get_object_or_404(LTIPlan, id=plan_id)
        _ensure_company_lti_cells(plan)

        cat = request.data.get("employee_category_1")
        mode = request.data.get("mode")
        target_ids = request.data.get("target_org_unit_ids") or []
        manual_amounts = request.data.get("manual_amounts") or {}
        dry_run = bool(request.data.get("dry_run"))

        if cat not in LTI_CATEGORIES:
            return Response({"error": "invalid employee_category_1"}, status=400)
        if mode not in ("MANUAL", "HEADCOUNT", "SALARY_TOTAL"):
            return Response({"error": "invalid mode"}, status=400)
        if not target_ids:
            return Response({"error": "target_org_unit_ids required"}, status=400)

        try:
            validate_target_set(target_ids)
        except ValueError as e:
            return Response(
                {"error": "TARGETS_OVERLAP", "detail": str(e)}, status=400,
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

        company = _company_lti_cell(plan, cat)
        try:
            distribution = compute_distribution(
                total=company.shares_quota_ads,
                cat1=cat, mode=mode,
                target_unit_ids=[ou.id for ou in ous],
                manual_amounts=manual_amounts if mode == "MANUAL" else None,
                integer_units=True,
            )
        except ValueError as e:
            return Response(
                {"error": "COMPUTE_FAILED", "detail": str(e)}, status=400,
            )

        if not dry_run:
            allocated_map = aggregate_lti_allocated(plan)
            for ou_id, new_shares in distribution.items():
                actual = int(allocated_map.get((ou_id, cat), 0))
                if int(new_shares) < actual:
                    return Response({
                        "error": "DEPT_REDUCE_BELOW_ALLOCATED",
                        "detail": {
                            "target_org_unit_id": ou_id,
                            "requested": int(new_shares),
                            "already_allocated": actual,
                        },
                    }, status=400)

        if dry_run:
            return Response({
                "dry_run": True,
                "company_total": int(company.shares_quota_ads),
                "distribution": [
                    {"target_org_unit_id": k, "shares_ads": int(v)}
                    for k, v in distribution.items()
                ],
            })

        with transaction.atomic():
            LTIBudgetCell.objects.filter(
                plan=plan, employee_category_1=cat, target_org_unit__isnull=False,
            ).delete()
            for ou_id, shares in distribution.items():
                LTIBudgetCell.objects.create(
                    plan=plan, employee_category_1=cat, target_org_unit_id=ou_id,
                    shares_quota_ads=int(shares),
                    headcount_quota=0,
                )
            company.distribution_rule = mode
            company.save(update_fields=["distribution_rule"])

        log_action(
            "DISTRIBUTE", request.user, "LTIBudget", plan.id,
            {}, {
                "employee_category_1": cat, "mode": mode,
                "distribution": {str(k): int(v) for k, v in distribution.items()},
            },
        )
        return Response({
            "ok": True,
            "distribution": [
                {"target_org_unit_id": k, "shares_ads": int(v)}
                for k, v in distribution.items()
            ],
        })


class MyLtiBudgetView(APIView):
    """DEPT_HEAD / CENTER_HEAD 看自己负责单元的 LTI 额度。"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cycle_id = request.query_params.get("cycle_id")
        if not cycle_id:
            return Response({"error": "cycle_id required"}, status=400)
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        plan = cycle.linked_lti_plan
        if not plan:
            return Response({"cycle_id": cycle.id, "targets": []})

        scope = resolve_user_org_scope(request.user)
        scope_ids = list(scope.filter(type__in=("DEPT", "CENTER")).values_list("id", flat=True))

        cells = list(
            LTIBudgetCell.objects.filter(
                plan=plan,
                target_org_unit__isnull=False,
                target_org_unit_id__in=scope_ids,
            ).select_related("target_org_unit").order_by(
                "target_org_unit__code", "employee_category_1"
            )
        )
        allocated_map = aggregate_lti_allocated(plan)
        _attach_lti_used(cells, allocated_map)

        return Response({
            "cycle_id": cycle.id,
            "plan_id": plan.id,
            "targets": TargetLTIBudgetCellSerializer(cells, many=True).data,
        })
