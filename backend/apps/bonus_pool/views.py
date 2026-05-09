from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from apps.iam.permissions import IsHRAdmin
from apps.bonus_pool.models import BonusPlan
from apps.bonus_pool.serializers import BonusPlanSerializer


class BonusPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BonusPlan.objects.all().order_by("-id")
    serializer_class = BonusPlanSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
