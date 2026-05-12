"""OrgUnitManager 兼任表 + EMPLOYEE_LEAF 单元类型用例。"""
import pytest
from datetime import date
from django.db import IntegrityError

from apps.iam.models import OrgUnit, OrgUnitManager, User


@pytest.fixture
def units_and_users(db):
    u1 = User.objects.create_user(email="m1@x.com", employee_no="M001", password="x")
    u2 = User.objects.create_user(email="m2@x.com", employee_no="M002", password="x")
    dept = OrgUnit.objects.create(code="D1", name="部门 1", type="DEPT")
    center_a = OrgUnit.objects.create(code="C_A", name="中心 A", type="CENTER", parent=dept)
    center_b = OrgUnit.objects.create(code="C_B", name="中心 B", type="CENTER", parent=dept)
    return u1, u2, dept, center_a, center_b


@pytest.mark.django_db
def test_employee_leaf_unit_type_accepted():
    leaf = OrgUnit.objects.create(code="EMP_001", name="alice 员工节点", type="EMPLOYEE_LEAF")
    assert leaf.type == "EMPLOYEE_LEAF"


@pytest.mark.django_db
def test_one_manager_can_manage_multiple_units(units_and_users):
    u1, _, _, ca, cb = units_and_users
    OrgUnitManager.objects.create(
        org_unit=ca, manager=u1, role_in_unit="CENTER_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    OrgUnitManager.objects.create(
        org_unit=cb, manager=u1, role_in_unit="CENTER_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    assert u1.managed_units.count() == 2  # 兼任两个中心


@pytest.mark.django_db
def test_unit_can_have_multiple_concurrent_managers(units_and_users):
    u1, u2, _, ca, _ = units_and_users
    OrgUnitManager.objects.create(
        org_unit=ca, manager=u1, role_in_unit="CENTER_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    OrgUnitManager.objects.create(
        org_unit=ca, manager=u2, role_in_unit="CENTER_HEAD",
        is_primary=False, effective_from=date(2026, 1, 1),  # 副 / 兼任
    )
    assert ca.managers.count() == 2


@pytest.mark.django_db
def test_only_one_active_primary_per_unit(units_and_users):
    u1, u2, _, ca, _ = units_and_users
    OrgUnitManager.objects.create(
        org_unit=ca, manager=u1, role_in_unit="CENTER_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    with pytest.raises(IntegrityError):
        OrgUnitManager.objects.create(
            org_unit=ca, manager=u2, role_in_unit="CENTER_HEAD",
            is_primary=True, effective_from=date(2026, 1, 1),
        )


@pytest.mark.django_db
def test_expired_primary_releases_uniqueness(units_and_users):
    """primary effective_to 不为空 → 视为历史记录，不再占用唯一约束。"""
    u1, u2, _, ca, _ = units_and_users
    OrgUnitManager.objects.create(
        org_unit=ca, manager=u1, role_in_unit="CENTER_HEAD",
        is_primary=True, effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31),
    )
    OrgUnitManager.objects.create(
        org_unit=ca, manager=u2, role_in_unit="CENTER_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    assert ca.managers.count() == 2
