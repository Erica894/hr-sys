import pytest
from apps.iam.models import User, Role
from apps.audit.models import AuditLog


@pytest.fixture
def hr_user(db):
    user = User.objects.create_user(email="hr@test.com", employee_no="HR001", password="pass")
    Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "HR"})
    return user


@pytest.mark.django_db
def test_write_request_creates_audit_log(hr_user):
    from apps.audit.services import log_action
    log_action(
        event="TEST_EVENT",
        actor=hr_user,
        resource_type="TestModel",
        resource_id=1,
        before={},
        after={"field": "value"},
        ip="127.0.0.1",
        request_id="test-req-1",
    )
    assert AuditLog.objects.filter(action="TEST_EVENT", actor_id=hr_user.id).exists()
