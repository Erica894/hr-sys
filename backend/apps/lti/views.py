from rest_framework import permissions, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentProposal
from apps.lti.models import LTIGrant, EmployeeAck, LTIPlan, LTIBudgetCell
from apps.lti.serializers import LTIPlanSerializer, LTIBudgetCellSerializer
from apps.hr_master.models import Employee
from apps.iam.permissions import IsHRAdmin
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


class LTIBudgetView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def _ensure_cells(self, plan):
        for cat in LTI_CATEGORIES:
            LTIBudgetCell.objects.get_or_create(
                plan=plan, employee_category_1=cat,
                defaults={
                    "headcount_quota": 0, "shares_quota_ads": 0,
                    "headcount_used": 0, "shares_used_ads": 0,
                },
            )

    def get(self, request, plan_id):
        plan = get_object_or_404(LTIPlan, id=plan_id)
        self._ensure_cells(plan)
        cells = LTIBudgetCell.objects.filter(plan=plan).order_by("employee_category_1")
        return Response({"rows": LTIBudgetCellSerializer(cells, many=True).data})

    def put(self, request, plan_id):
        plan = get_object_or_404(LTIPlan, id=plan_id)
        self._ensure_cells(plan)
        for row in request.data.get("rows", []):
            cat = row.get("employee_category_1")
            if cat not in LTI_CATEGORIES:
                return Response(
                    {"error": f"invalid category: {cat}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cell = LTIBudgetCell.objects.get(plan=plan, employee_category_1=cat)
            cell.headcount_quota = int(row.get("headcount_quota", cell.headcount_quota))
            cell.shares_quota_ads = int(row.get("shares_quota_ads", cell.shares_quota_ads))
            cell.save(update_fields=["headcount_quota", "shares_quota_ads"])
        log_action(
            "UPDATE", request.user, "LTIBudget", plan.id,
            {}, {"rows": request.data.get("rows", [])},
        )
        cells = LTIBudgetCell.objects.filter(plan=plan).order_by("employee_category_1")
        return Response({"rows": LTIBudgetCellSerializer(cells, many=True).data})
