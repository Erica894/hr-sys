from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.shortcuts import get_object_or_404
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentProposal
from apps.lti.models import LTIGrant
from apps.reward_cycle.services import get_allocation_rows, generate_proposals
from apps.reward_cycle.serializers import (
    AllocationRowSerializer, SaveProposalsItemSerializer, RewardCycleSerializer,
)


class RewardCycleListView(generics.ListAPIView):
    queryset = RewardCycle.objects.all().order_by("-created_at")
    serializer_class = RewardCycleSerializer
    permission_classes = [permissions.IsAuthenticated]


class AllocationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        if cycle.status == "DRAFT" and cycle.linked_adjustment_plan and cycle.linked_lti_plan:
            with transaction.atomic():
                generate_proposals(cycle, cycle.linked_adjustment_plan, cycle.linked_lti_plan)
        rows = get_allocation_rows(cycle)
        return Response({
            "cycle": RewardCycleSerializer(cycle).data,
            "rows": AllocationRowSerializer(rows, many=True).data,
        })


class SaveProposalsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, pk=cycle_id)
        if cycle.status not in ("DRAFT", "ALLOCATING"):
            return Response({"detail": "cycle not editable"}, status=400)
        items = SaveProposalsItemSerializer(data=request.data.get("items", []), many=True)
        items.is_valid(raise_exception=True)
        for it in items.validated_data:
            if "annual_manager_delta_pct" in it:
                AdjustmentProposal.objects.filter(
                    plan=cycle.linked_adjustment_plan, employee_id=it["employee_id"]
                ).update(annual_manager_delta_pct=it["annual_manager_delta_pct"])
            if "granted_ads" in it:
                grant = LTIGrant.objects.filter(
                    plan=cycle.linked_lti_plan, employee_id=it["employee_id"]
                ).first()
                if grant:
                    grant.granted_ads = it["granted_ads"]
                    grant.save(update_fields=["granted_ads"])
        if cycle.status == "DRAFT":
            cycle.status = "ALLOCATING"
            cycle.save(update_fields=["status"])
        return Response({"ok": True})
