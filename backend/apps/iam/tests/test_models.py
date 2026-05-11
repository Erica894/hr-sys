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
    role, _ = Role.objects.get_or_create(code="DEPT_HEAD", defaults={"name": "部门负责人"})
    ur = UserRole.objects.create(user=user, role=role, scope_type="DEPT", scope_ref_id=org.id)
    assert user.email == "alice@example.com"
    assert ur.scope_type == "DEPT"

@pytest.mark.django_db
def test_org_unit_tree():
    company = OrgUnit.objects.create(code="HQ", name="总部", type="COMPANY")
    dept = OrgUnit.objects.create(code="ENG", name="Engineering", type="DEPT", parent=company)
    assert dept.parent == company


@pytest.mark.django_db
def test_seven_system_roles_seeded():
    """All 7 permanent roles must exist with non-empty base_field_set."""
    expected_codes = {
        "HR_ADMIN", "DEPT_HEAD", "CENTER_HEAD",
        "GROUP_LEAD", "EMPLOYEE", "FINANCE", "AUDITOR",
    }
    roles = {r.code: r for r in Role.objects.filter(code__in=expected_codes)}
    assert set(roles.keys()) == expected_codes
    for code, role in roles.items():
        assert isinstance(role.base_field_set, list)
        assert len(role.base_field_set) > 0, f"{code} base_field_set is empty"


@pytest.mark.django_db
def test_center_head_excludes_rsu_fields():
    """CENTER_HEAD default field set must NOT contain RSU fields."""
    role = Role.objects.get(code="CENTER_HEAD")
    rsu_fields = {"rsu_grant_amount", "rsu_vesting_schedule", "rsu_unvested_value"}
    assert rsu_fields.isdisjoint(set(role.base_field_set)), \
        "CENTER_HEAD must not see RSU fields by default"


@pytest.mark.django_db
def test_dept_head_includes_rsu_fields():
    """DEPT_HEAD default field set must contain RSU fields."""
    role = Role.objects.get(code="DEPT_HEAD")
    assert "rsu_grant_amount" in role.base_field_set
