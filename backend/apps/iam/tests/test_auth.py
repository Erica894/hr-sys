import pytest
from rest_framework.test import APIClient
from apps.iam.models import User, Role, UserRole


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def hr_user(db):
    user = User.objects.create_user(email="hr@example.com", employee_no="HR001", password="pass123")
    role = Role.objects.create(code="HR_ADMIN", name="薪酬HR")
    UserRole.objects.create(user=user, role=role, scope_type="GLOBAL")
    return user


@pytest.mark.django_db
def test_login_returns_tokens(client, hr_user):
    resp = client.post("/api/auth/login/", {"email": "hr@example.com", "password": "pass123"})
    assert resp.status_code == 200
    assert "access" in resp.data


@pytest.mark.django_db
def test_login_wrong_password(client, hr_user):
    resp = client.post("/api/auth/login/", {"email": "hr@example.com", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_mfa_setup_and_verify(client, hr_user):
    client.force_authenticate(user=hr_user)
    resp = client.post("/api/auth/mfa/setup/")
    assert resp.status_code == 200
    assert "totp_uri" in resp.data
    import pyotp
    totp = pyotp.TOTP(hr_user.totp_secret if hr_user.totp_secret else resp.data["secret"])
    verify_resp = client.post("/api/auth/mfa/verify/", {"code": totp.now()})
    assert verify_resp.status_code == 200
