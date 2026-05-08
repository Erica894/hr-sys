from django.urls import path
from apps.reward_cycle.views import (
    RewardCycleListView, AllocationListView, SaveProposalsView,
    SubmitForApprovalView, ExecuteView,
)

urlpatterns = [
    path("reward-cycle/", RewardCycleListView.as_view()),
    path("reward-cycle/<int:cycle_id>/allocation/", AllocationListView.as_view()),
    path("reward-cycle/<int:cycle_id>/proposals/", SaveProposalsView.as_view()),
    path("reward-cycle/<int:cycle_id>/submit/", SubmitForApprovalView.as_view()),
    path("reward-cycle/<int:cycle_id>/execute/", ExecuteView.as_view()),
]
