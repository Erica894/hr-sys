from rest_framework import serializers
from apps.bonus_pool.models import BonusPlan


class BonusPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BonusPlan
        fields = [
            "id", "code", "name", "period", "status",
            "budget_total_cny", "scope", "formula", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
