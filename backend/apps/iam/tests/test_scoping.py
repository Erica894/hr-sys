"""resolve_user_org_scope 单元测试：覆盖单管多管 / 兼任 / 失效 / 无任命。"""
import pytest
from datetime import date

from apps.iam.models import OrgUnit, OrgUnitManager, User
from apps.iam.scoping import resolve_user_org_scope


@pytest.fixture
def org_tree(db):
    company = OrgUnit.objects.create(code="HQ", name="集团", type="COMPANY")
    d1 = OrgUnit.objects.create(code="D1", name="研发", type="DEPT", parent=company)
    d2 = OrgUnit.objects.create(code="D2", name="销售", type="DEPT", parent=company)
    c1 = OrgUnit.objects.create(code="C1", name="AI 中心", type="CENTER", parent=d1)
    c2 = OrgUnit.objects.create(code="C2", name="平台中心", type="CENTER", parent=d1)
    t1 = OrgUnit.objects.create(code="T1", name="算法组", type="TEAM", parent=c1)
    return {"company": company, "d1": d1, "d2": d2, "c1": c1, "c2": c2, "t1": t1}


@pytest.mark.django_db
def test_resolve_scope_for_dept_head_returns_subtree(org_tree):
    u = User.objects.create_user(email="dh@x.com", employee_no="DH1", password="x")
    OrgUnitManager.objects.create(
        org_unit=org_tree["d1"], manager=u, role_in_unit="DEPT_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    scope = resolve_user_org_scope(u)
    codes = {ou.code for ou in scope}
    assert codes == {"D1", "C1", "C2", "T1"}


@pytest.mark.django_db
def test_resolve_scope_for_concurrent_manager_unions_subtrees(org_tree):
    u = User.objects.create_user(email="ch@x.com", employee_no="CH1", password="x")
    OrgUnitManager.objects.create(
        org_unit=org_tree["c1"], manager=u, role_in_unit="CENTER_HEAD",
        is_primary=True, effective_from=date(2026, 1, 1),
    )
    OrgUnitManager.objects.create(
        org_unit=org_tree["c2"], manager=u, role_in_unit="CENTER_HEAD",
        is_primary=False, effective_from=date(2026, 1, 1),
    )
    scope = resolve_user_org_scope(u)
    codes = {ou.code for ou in scope}
    assert codes == {"C1", "C2", "T1"}


@pytest.mark.django_db
def test_resolve_scope_excludes_expired_assignments(org_tree):
    u = User.objects.create_user(email="x@x.com", employee_no="X1", password="x")
    OrgUnitManager.objects.create(
        org_unit=org_tree["c1"], manager=u, role_in_unit="CENTER_HEAD",
        is_primary=True,
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
    )
    scope = resolve_user_org_scope(u, as_of=date(2026, 5, 11))
    assert list(scope) == []


@pytest.mark.django_db
def test_resolve_scope_for_no_assignment_returns_empty(org_tree):
    u = User.objects.create_user(email="nobody@x.com", employee_no="NB1", password="x")
    assert list(resolve_user_org_scope(u)) == []
