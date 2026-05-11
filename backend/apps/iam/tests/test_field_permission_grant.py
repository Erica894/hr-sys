import pytest
from django.core.exceptions import ValidationError
from apps.iam.models import User, OrgUnit, FieldPermissionGrant


@pytest.fixture
def grant_actors(db):
    granter = User.objects.create_user(email="dept@x.com", employee_no="D001", password="x")
    grantee = User.objects.create_user(email="center@x.com", employee_no="C001", password="x")
    center = OrgUnit.objects.create(code="C_AI", name="AI 中心", type="CENTER")
    return granter, grantee, center


@pytest.mark.django_db
def test_grant_with_rsu_fields_is_valid(grant_actors):
    granter, grantee, center = grant_actors
    g = FieldPermissionGrant(
        granter=granter, grantee=grantee, center=center,
        extra_fields=["rsu_grant_amount", "rsu_vesting_schedule"],
    )
    g.full_clean()
    g.save()
    assert g.status == "ACTIVE"


@pytest.mark.django_db
def test_grant_rejects_non_rsu_field(grant_actors):
    granter, grantee, center = grant_actors
    g = FieldPermissionGrant(
        granter=granter, grantee=grantee, center=center,
        extra_fields=["base_salary"],
    )
    with pytest.raises(ValidationError):
        g.full_clean()


@pytest.mark.django_db
def test_grant_rejects_non_center_unit(grant_actors):
    granter, grantee, _ = grant_actors
    dept = OrgUnit.objects.create(code="D_BIZ", name="业务部", type="DEPT")
    g = FieldPermissionGrant(
        granter=granter, grantee=grantee, center=dept,
        extra_fields=["rsu_grant_amount"],
    )
    with pytest.raises(ValidationError):
        g.full_clean()


@pytest.mark.django_db
def test_only_one_active_grant_per_grantee_center(grant_actors):
    from django.db.utils import IntegrityError
    granter, grantee, center = grant_actors
    FieldPermissionGrant.objects.create(
        granter=granter, grantee=grantee, center=center,
        extra_fields=["rsu_grant_amount"],
    )
    with pytest.raises(IntegrityError):
        FieldPermissionGrant.objects.create(
            granter=granter, grantee=grantee, center=center,
            extra_fields=["rsu_vesting_schedule"],
        )


@pytest.mark.django_db
def test_revoked_grant_does_not_block_new_active(grant_actors):
    granter, grantee, center = grant_actors
    old = FieldPermissionGrant.objects.create(
        granter=granter, grantee=grantee, center=center,
        extra_fields=["rsu_grant_amount"], status="REVOKED",
    )
    new = FieldPermissionGrant.objects.create(
        granter=granter, grantee=grantee, center=center,
        extra_fields=["rsu_vesting_schedule"], status="ACTIVE",
    )
    assert new.id != old.id
