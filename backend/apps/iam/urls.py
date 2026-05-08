from django.urls import path
from .views import LoginView, MFASetupView, MFAVerifyView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("mfa/setup/", MFASetupView.as_view()),
    path("mfa/verify/", MFAVerifyView.as_view()),
]
