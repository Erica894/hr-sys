from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.lti.views import (
    LTIPlanViewSet,
    LTIBudgetView,
    DistributeLtiBudgetView,
    PatchLtiTargetsView,
)

router = DefaultRouter()
router.register("lti-plans", LTIPlanViewSet, basename="lti-plan")

urlpatterns = router.urls + [
    path(
        "lti-plans/<int:plan_id>/budget/",
        LTIBudgetView.as_view(),
        name="lti-budget",
    ),
    path(
        "lti-plans/<int:plan_id>/budget/distribute/",
        DistributeLtiBudgetView.as_view(),
        name="lti-budget-distribute",
    ),
    path(
        "lti-plans/<int:plan_id>/budget/targets/",
        PatchLtiTargetsView.as_view(),
        name="lti-budget-targets",
    ),
]
