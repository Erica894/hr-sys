from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentProposal
from apps.lti.models import LTIGrant, EmployeeAck
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
