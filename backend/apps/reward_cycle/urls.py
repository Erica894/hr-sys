from django.urls import path
from apps.reward_cycle.views import RewardCycleListView, AllocationListView, SaveProposalsView

urlpatterns = [
    path("reward-cycle/", RewardCycleListView.as_view()),
    path("reward-cycle/<int:cycle_id>/allocation/", AllocationListView.as_view()),
    path("reward-cycle/<int:cycle_id>/proposals/", SaveProposalsView.as_view()),
]
