from django.urls import path

from apps.analytics import views

urlpatterns = [
    path("overview/", views.AnalyticsOverview.as_view(), name="analytics-overview"),
    path("by-dept/", views.AnalyticsByDept.as_view(), name="analytics-by-dept"),
    path("distribution/", views.AnalyticsDistribution.as_view(), name="analytics-distribution"),
    path("employee/<int:employee_id>/timeline/",
         views.EmployeeTimeline.as_view(), name="analytics-employee-timeline"),
]
