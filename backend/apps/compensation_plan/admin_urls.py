from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.compensation_plan.views import (
    AdjustmentPlanViewSet,
    AdjustmentBudgetView,
    DistributeAdjustmentBudgetView,
)

router = DefaultRouter()
router.register("adjustment-plans", AdjustmentPlanViewSet, basename="adjustment-plan")

urlpatterns = router.urls + [
    path(
        "reward-cycles/<int:cycle_id>/adjustment-budget/",
        AdjustmentBudgetView.as_view(),
        name="adjustment-budget",
    ),
    path(
        "reward-cycles/<int:cycle_id>/adjustment-budget/distribute/",
        DistributeAdjustmentBudgetView.as_view(),
        name="adjustment-budget-distribute",
    ),
]
