"""非 admin 入口：DEPT_HEAD / CENTER_HEAD 看自己单元的预算。"""
from django.urls import path
from apps.compensation_plan.views import MyAdjustmentBudgetView
from apps.lti.views import MyLtiBudgetView
from apps.bonus_pool.views import MyBonusBudgetView

urlpatterns = [
    path("my-adjustment/", MyAdjustmentBudgetView.as_view(), name="my-adjustment-budget"),
    path("my-lti/", MyLtiBudgetView.as_view(), name="my-lti-budget"),
    path("my-bonus/", MyBonusBudgetView.as_view(), name="my-bonus-budget"),
]
