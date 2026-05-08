from django.urls import path
from apps.approval.views import (
    MyPendingInstancesView, ApprovalInstanceDetailView, ApprovalActionView,
)

urlpatterns = [
    path("approval/my-pending/", MyPendingInstancesView.as_view()),
    path("approval/<int:pk>/", ApprovalInstanceDetailView.as_view()),
    path("approval/<int:instance_id>/action/", ApprovalActionView.as_view()),
]
