from rest_framework import serializers
from apps.approval.models import ApprovalInstance, ApprovalStep


class ApprovalStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalStep
        fields = ["id", "node_index", "approver_user_id", "action", "comment", "acted_at"]


class ApprovalInstanceSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True, read_only=True)
    current_step = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalInstance
        fields = ["id", "template_id", "subject_type", "subject_id", "status",
                  "current_node", "current_step", "over_budget_flag", "steps", "created_at"]

    def get_current_step(self, obj):
        return obj.current_node + 1
