"""目标集校验、子树成员、归属解析。"""
import pytest

from apps.iam.models import OrgUnit
from apps.hr_master.models import Employee
from apps.compensation_plan.services.org_targets import (
    validate_target_set,
    descendant_ids,
    members_under,
    resolve_owning_target,
)


@pytest.fixture
def tree(db):
    company = OrgUnit.objects.create(code="HQ", name="HQ", type="COMPANY")
    dept_a = OrgUnit.objects.create(code="DA", name="部门A", type="DEPT", parent=company)
    dept_b = OrgUnit.objects.create(code="DB", name="部门B", type="DEPT", parent=company)
    center_a1 = OrgUnit.objects.create(code="CA1", name="A中心1", type="CENTER", parent=dept_a)
    center_a2 = OrgUnit.objects.create(code="CA2", name="A中心2", type="CENTER", parent=dept_a)
    return {
        "company": company, "dept_a": dept_a, "dept_b": dept_b,
        "center_a1": center_a1, "center_a2": center_a2,
    }


@pytest.mark.django_db
def test_disjoint_set_passes(tree):
    validate_target_set([tree["dept_a"].id, tree["dept_b"].id])
    validate_target_set([tree["center_a1"].id, tree["center_a2"].id, tree["dept_b"].id])


@pytest.mark.django_db
def test_ancestor_descendant_overlap_rejected(tree):
    with pytest.raises(ValueError):
        validate_target_set([tree["dept_a"].id, tree["center_a1"].id])


@pytest.mark.django_db
def test_descendant_ids_includes_self_and_subtree(tree):
    ids = descendant_ids(tree["dept_a"].id)
    assert tree["dept_a"].id in ids
    assert tree["center_a1"].id in ids
    assert tree["center_a2"].id in ids
    assert tree["dept_b"].id not in ids


@pytest.mark.django_db
def test_members_under_includes_subtree(tree):
    e1 = Employee.objects.create(employee_no="E1", name_cn="e1", org_unit=tree["dept_a"])
    e2 = Employee.objects.create(employee_no="E2", name_cn="e2", org_unit=tree["center_a1"])
    Employee.objects.create(employee_no="E3", name_cn="e3", org_unit=tree["dept_b"])
    ids = set(members_under(tree["dept_a"].id).values_list("id", flat=True))
    assert ids == {e1.id, e2.id}


@pytest.mark.django_db
def test_resolve_owning_target_walks_up(tree):
    e_in_center = Employee.objects.create(
        employee_no="E10", name_cn="e10", org_unit=tree["center_a1"]
    )
    targets = {tree["dept_a"].id, tree["dept_b"].id}
    assert resolve_owning_target(e_in_center, targets) == tree["dept_a"].id

    targets_center = {tree["center_a1"].id, tree["center_a2"].id}
    assert resolve_owning_target(e_in_center, targets_center) == tree["center_a1"].id


@pytest.mark.django_db
def test_resolve_owning_target_returns_none_when_no_match(tree):
    e = Employee.objects.create(employee_no="E20", name_cn="e20", org_unit=tree["dept_b"])
    assert resolve_owning_target(e, {tree["dept_a"].id}) is None
