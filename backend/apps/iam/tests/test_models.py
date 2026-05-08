import pytest
from apps.iam.models import User, Role, UserRole, OrgUnit

@pytest.mark.django_db
def test_create_user_with_role():
    org = OrgUnit.objects.create(code="DEPT_ENG", name="Engineering", type="DEPT")
    user = User.objects.create_user(
        email="alice@example.com",
        employee_no="E001",
        password="pass123",
    )
    role = Role.objects.create(code="DEPT_HEAD", name="部门负责人")
    ur = UserRole.objects.create(user=user, role=role, scope_type="DEPT", scope_ref_id=org.id)
    assert user.email == "alice@example.com"
    assert ur.scope_type == "DEPT"

@pytest.mark.django_db
def test_org_unit_tree():
    company = OrgUnit.objects.create(code="HQ", name="总部", type="COMPANY")
    dept = OrgUnit.objects.create(code="ENG", name="Engineering", type="DEPT", parent=company)
    assert dept.parent == company
