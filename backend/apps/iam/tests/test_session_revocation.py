"""SessionRevocation JWT 黑名单：写入 / 查询 / 过期回收语义。"""
import pytest
from datetime import timedelta
from django.utils import timezone

from apps.iam.models import SessionRevocation, User


@pytest.mark.django_db
def test_revoke_jti_blocks_token():
    u = User.objects.create_user(email="r@x.com", employee_no="R1", password="x")
    SessionRevocation.objects.create(
        user=u, jti="abc-123",
        expires_at=timezone.now() + timedelta(hours=1),
        reason="LOGOUT",
    )
    assert SessionRevocation.is_revoked("abc-123") is True
    assert SessionRevocation.is_revoked("other-jti") is False


@pytest.mark.django_db
def test_expired_revocation_does_not_block():
    """JWT 自然过期后，revocation 记录应被视为已无效。"""
    u = User.objects.create_user(email="r2@x.com", employee_no="R2", password="x")
    SessionRevocation.objects.create(
        user=u, jti="old-jti",
        expires_at=timezone.now() - timedelta(seconds=1),
        reason="LOGOUT",
    )
    assert SessionRevocation.is_revoked("old-jti") is False
