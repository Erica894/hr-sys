from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, MFASetupView, MFAVerifyView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("refresh/", TokenRefreshView.as_view()),
    path("mfa/setup/", MFASetupView.as_view()),
    path("mfa/verify/", MFAVerifyView.as_view()),
]
