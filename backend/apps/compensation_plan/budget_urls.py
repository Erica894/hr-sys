"""非 admin 入口：DEPT_HEAD / CENTER_HEAD 看自己单元的预算。"""
from django.urls import path
from apps.compensation_plan.views import MyAdjustmentBudgetView

urlpatterns = [
    path("my-adjustment/", MyAdjustmentBudgetView.as_view(), name="my-adjustment-budget"),
]
