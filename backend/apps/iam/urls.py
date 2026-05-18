from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, MFASetupView, MFAVerifyView, MyLanguageView, OrgUnitListView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("refresh/", TokenRefreshView.as_view()),
    path("mfa/setup/", MFASetupView.as_view()),
    path("mfa/verify/", MFAVerifyView.as_view()),
    path("me/language/", MyLanguageView.as_view()),
    path("org-units/", OrgUnitListView.as_view()),
]
