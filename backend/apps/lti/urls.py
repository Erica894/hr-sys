from django.urls import path
from apps.lti.views import EmployeeProposalView, AckView


urlpatterns = [
    path("reward-cycle/<int:cycle_id>/my-proposal/", EmployeeProposalView.as_view()),
    path("reward-cycle/<int:cycle_id>/ack/", AckView.as_view()),
]
