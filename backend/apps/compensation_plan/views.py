from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.iam.permissions import IsHRAdmin
from apps.compensation_plan.models import AdjustmentPlan, AdjustmentBudgetCell
from apps.compensation_plan.serializers import (
    AdjustmentPlanSerializer, AdjustmentBudgetCellSerializer,
)
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


class AdjustmentBudgetView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def _ensure_cells(self, cycle):
        for adj in ADJ_TYPES:
            for cat in CATEGORIES:
                AdjustmentBudgetCell.objects.get_or_create(
                    reward_cycle=cycle,
                    adjustment_type=adj,
                    employee_category_1=cat,
                    defaults={"budget_amount_cny": 0, "allocated_amount_cny": 0},
                )

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        self._ensure_cells(cycle)
        cells = AdjustmentBudgetCell.objects.filter(reward_cycle=cycle).order_by(
            "adjustment_type", "employee_category_1"
        )
        return Response({"rows": AdjustmentBudgetCellSerializer(cells, many=True).data})

    def put(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        self._ensure_cells(cycle)
        rows = request.data.get("rows", [])
        updated = []
        for row in rows:
            adj = row.get("adjustment_type")
            cat = row.get("employee_category_1")
            if adj not in ADJ_TYPES or cat not in CATEGORIES:
                return Response(
                    {"error": f"invalid adjustment_type/category: {adj}/{cat}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cell = AdjustmentBudgetCell.objects.get(
                reward_cycle=cycle, adjustment_type=adj, employee_category_1=cat,
            )
            cell.budget_amount_cny = Decimal(str(row.get("budget_amount_cny", 0)))
            cell.save(update_fields=["budget_amount_cny"])
            updated.append(cell)
        log_action(
            event="UPDATE", actor=request.user,
            resource_type="AdjustmentBudget", resource_id=cycle.id,
            before={}, after={"rows": rows},
        )
        all_cells = AdjustmentBudgetCell.objects.filter(reward_cycle=cycle).order_by(
            "adjustment_type", "employee_category_1"
        )
        return Response({"rows": AdjustmentBudgetCellSerializer(all_cells, many=True).data})
