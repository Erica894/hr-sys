from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.bonus_pool.views import (
    BonusPlanViewSet,
    RegionalBonusRuleViewSet,
    BonusCategoryFactorViewSet,
    BonusBudgetOverrideViewSet,
    BonusBudgetView,
    DistributeBonusBudgetView,
    PatchBonusTargetsView,
    BonusDerivedBudgetView,
    BonusBudgetOverrideClearView,
)

router = DefaultRouter()
router.register("bonus-plans", BonusPlanViewSet, basename="bonus-plan")
router.register("regional-bonus-rules", RegionalBonusRuleViewSet, basename="regional-bonus-rule")
router.register("bonus-category-factors", BonusCategoryFactorViewSet, basename="bonus-category-factor")
router.register("bonus-budget-overrides", BonusBudgetOverrideViewSet, basename="bonus-budget-override")

urlpatterns = router.urls + [
    path(
        "reward-cycles/<int:cycle_id>/bonus-budget/",
        BonusBudgetView.as_view(),
        name="bonus-budget",
    ),
    path(
        "reward-cycles/<int:cycle_id>/bonus-budget/distribute/",
        DistributeBonusBudgetView.as_view(),
        name="bonus-budget-distribute",
    ),
    path(
        "reward-cycles/<int:cycle_id>/bonus-budget/targets/",
        PatchBonusTargetsView.as_view(),
        name="bonus-budget-targets",
    ),
    path(
        "reward-cycles/<int:cycle_id>/bonus-derived-budget/",
        BonusDerivedBudgetView.as_view(),
        name="bonus-derived-budget",
    ),
    path(
        "reward-cycles/<int:cycle_id>/bonus-budget-overrides/clear/",
        BonusBudgetOverrideClearView.as_view(),
        name="bonus-budget-override-clear",
    ),
]
