from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.approval.models import ApprovalInstance
from apps.approval.serializers import ApprovalInstanceSerializer
from apps.approval.services import advance_approval
from apps.audit.services import log_action


class MyPendingInstancesView(generics.ListAPIView):
    serializer_class = ApprovalInstanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_role_codes = set(
            self.request.user.roles.values_list("role__code", flat=True)
        )
        pending_ids = []
        qs = ApprovalInstance.objects.filter(status="RUNNING").select_related("template")
        for inst in qs:
            nodes = inst.template.nodes or []
            if inst.current_node < len(nodes):
                if nodes[inst.current_node].get("role") in user_role_codes:
                    pending_ids.append(inst.id)
        return ApprovalInstance.objects.filter(id__in=pending_ids).order_by("-created_at")


class ApprovalInstanceDetailView(generics.RetrieveAPIView):
    queryset = ApprovalInstance.objects.all()
    serializer_class = ApprovalInstanceSerializer
    permission_classes = [permissions.IsAuthenticated]


class ApprovalActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, instance_id):
        instance = get_object_or_404(ApprovalInstance, pk=instance_id)
        action = request.data.get("action")
        comment = request.data.get("comment", "")
        if action not in ("APPROVE", "REJECT", "REJECT_BATCH",
                           "REJECT_INDIVIDUAL", "REJECT_WITH_COMMENT"):
            return Response({"detail": "invalid action"}, status=400)
        svc_action = "REJECT_BATCH" if action == "REJECT" else action
        advance_approval(instance.id, request.user.id, svc_action, comment)
        instance.refresh_from_db()
        log_action(action, request.user, "ApprovalInstance", instance.id,
                   {}, {"comment": comment})
        return Response(ApprovalInstanceSerializer(instance).data)
