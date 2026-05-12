"""MfaChallenge 模型用例：创建、过期判断、purpose 枚举完整。"""
import pytest
from datetime import timedelta
from django.utils import timezone

from apps.iam.models import MfaChallenge, User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="mfa@x.com", employee_no="MFA1", password="x", mfa_enabled=True,
    )


@pytest.mark.django_db
def test_create_pending_challenge(user):
    c = MfaChallenge.objects.create(
        user=user, purpose="LOGIN",
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    assert c.status == "PENDING"


@pytest.mark.django_db
def test_is_expired_helper(user):
    past = MfaChallenge.objects.create(
        user=user, purpose="LOGIN",
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    future = MfaChallenge.objects.create(
        user=user, purpose="LOGIN",
        expires_at=timezone.now() + timedelta(minutes=1),
    )
    assert past.is_expired is True
    assert future.is_expired is False


@pytest.mark.django_db
def test_purpose_choices(user):
    valid = ["LOGIN", "EXPORT", "FINAL_APPROVE", "ROLE_ASSIGN"]
    for p in valid:
        MfaChallenge.objects.create(
            user=user, purpose=p,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
    assert MfaChallenge.objects.count() == len(valid)
