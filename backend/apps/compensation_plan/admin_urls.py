from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.compensation_plan.views import (
    AdjustmentPlanViewSet,
    AdjustmentBudgetView,
    BudgetOverrideClearView,
    BudgetOverrideImportView,
    BudgetOverrideTemplateView,
    DerivedBudgetView,
    DistributeAdjustmentBudgetView,
    PatchAdjustmentTargetsView,
    RegionalAdjustmentRuleViewSet,
    EmployeeCategoryFactorViewSet,
    AdjustmentMatrixCellViewSet,
)

router = DefaultRouter()
router.register("adjustment-plans", AdjustmentPlanViewSet, basename="adjustment-plan")
router.register("regional-adjustment-rules", RegionalAdjustmentRuleViewSet, basename="regional-adjustment-rule")
router.register("employee-category-factors", EmployeeCategoryFactorViewSet, basename="employee-category-factor")
router.register("adjustment-matrix-cells", AdjustmentMatrixCellViewSet, basename="adjustment-matrix-cell")

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
    path(
        "reward-cycles/<int:cycle_id>/adjustment-budget/targets/",
        PatchAdjustmentTargetsView.as_view(),
        name="adjustment-budget-targets",
    ),
    path(
        "reward-cycles/<int:cycle_id>/derived-budget/",
        DerivedBudgetView.as_view(),
        name="derived-budget",
    ),
    path(
        "reward-cycles/<int:cycle_id>/budget-overrides/template/",
        BudgetOverrideTemplateView.as_view(),
        name="budget-override-template",
    ),
    path(
        "reward-cycles/<int:cycle_id>/budget-overrides/import/",
        BudgetOverrideImportView.as_view(),
        name="budget-override-import",
    ),
    path(
        "reward-cycles/<int:cycle_id>/budget-overrides/clear/",
        BudgetOverrideClearView.as_view(),
        name="budget-override-clear",
    ),
]
