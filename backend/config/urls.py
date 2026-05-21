from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/auth/", include("apps.iam.urls")),
    path("api/", include("apps.reward_cycle.urls")),
    path("api/", include("apps.approval.urls")),
    path("api/", include("apps.lti.urls")),
    path("api/admin/", include("apps.hr_master.admin_urls")),
    path("api/admin/", include("apps.compensation_plan.admin_urls")),
    path("api/admin/", include("apps.lti.admin_urls")),
    path("api/admin/", include("apps.bonus_pool.admin_urls")),
    path("api/budgets/", include("apps.compensation_plan.budget_urls")),
    path("api/analytics/", include("apps.analytics.urls")),
]
