from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("django-admin/", admin.site.urls),
    # Task 4+ will uncomment these as the apps grow their urls.py
    # path("api/auth/", include("apps.iam.urls")),
    # path("api/", include("apps.hr_master.urls")),
    # path("api/", include("apps.reward_cycle.urls")),
    # path("api/", include("apps.approval.urls")),
    # path("api/", include("apps.lti.urls")),
]
