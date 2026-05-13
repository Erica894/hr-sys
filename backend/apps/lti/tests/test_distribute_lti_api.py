"""LTI 预算下发 API：HEADCOUNT / dry_run / 重叠拒 / 非 DEPT|CENTER 拒 / GET targets。"""
import pytest
from rest_framework.test import APIClient
from datetime import date
from decimal import Decimal

from apps.iam.models import User, OrgUnit, Role, UserRole
from apps.hr_master.models import Employee
from apps.lti.models import LTIPlan, LTIBudgetCell


@pytest.fixture
def hr(db):
    user = User.objects.create_user(email="hr_lti_dist@x.com", employee_no="HRLD", password="x")
    role, _ = Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "HR"})
    UserRole.objects.create(user=user, role=role)
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def plan(db):
    return LTIPlan.objects.create(
        code="LTI_DIST", name="lti dist", grant_date=date(2026, 1, 1),
        total_shares=10000, unit_price_at_grant=Decimal("10.0"),
    )


@pytest.fixture
def two_depts(db):
    a = OrgUnit.objects.create(code="LDA", name="A", type="DEPT")
    b = OrgUnit.objects.create(code="LDB", name="B", type="DEPT")
    Employee.objects.create(employee_no="LA1", name_cn="la1", org_unit=a, employee_category_1="STAFF", status="ACTIVE")
    Employee.objects.create(employee_no="LA2", name_cn="la2", org_unit=a, employee_category_1="STAFF", status="ACTIVE")
    Employee.objects.create(employee_no="LB1", name_cn="lb1", org_unit=b, employee_category_1="STAFF", status="ACTIVE")
    return a, b


@pytest.mark.django_db
def test_lti_distribute_headcount_creates_target_cells(hr, plan, two_depts):
    a, b = two_depts
    hr.put(f"/api/admin/lti-plans/{plan.id}/budget/", {
        "rows": [{"employee_category_1": "STAFF", "headcount_quota": 3, "shares_quota_ads": 6000}],
    }, format="json")
    r = hr.post(
        f"/api/admin/lti-plans/{plan.id}/budget/distribute/",
        {
            "employee_category_1": "STAFF", "mode": "HEADCOUNT",
            "target_org_unit_ids": [a.id, b.id],
        }, format="json",
    )
    assert r.status_code == 200, r.json()
    by_ou = {
        c.target_org_unit_id: int(c.shares_quota_ads)
        for c in LTIBudgetCell.objects.filter(plan=plan, target_org_unit__isnull=False)
    }
    assert by_ou[a.id] == 4000
    assert by_ou[b.id] == 2000
    company = LTIBudgetCell.objects.get(plan=plan, employee_category_1="STAFF", target_org_unit__isnull=True)
    assert company.distribution_rule == "HEADCOUNT"


@pytest.mark.django_db
def test_lti_distribute_dry_run_does_not_persist(hr, plan, two_depts):
    a, b = two_depts
    hr.put(f"/api/admin/lti-plans/{plan.id}/budget/", {
        "rows": [{"employee_category_1": "STAFF", "headcount_quota": 3, "shares_quota_ads": 1500}],
    }, format="json")
    r = hr.post(
        f"/api/admin/lti-plans/{plan.id}/budget/distribute/",
        {
            "employee_category_1": "STAFF", "mode": "HEADCOUNT",
            "target_org_unit_ids": [a.id, b.id], "dry_run": True,
        }, format="json",
    )
    assert r.status_code == 200
    assert r.json()["dry_run"] is True
    assert LTIBudgetCell.objects.filter(plan=plan, target_org_unit__isnull=False).count() == 0


@pytest.mark.django_db
def test_lti_distribute_overlap_rejected(hr, plan):
    parent = OrgUnit.objects.create(code="LP", name="LP", type="DEPT")
    child = OrgUnit.objects.create(code="LC", name="LC", type="CENTER", parent=parent)
    hr.put(f"/api/admin/lti-plans/{plan.id}/budget/", {
        "rows": [{"employee_category_1": "STAFF", "headcount_quota": 1, "shares_quota_ads": 1000}],
    }, format="json")
    r = hr.post(
        f"/api/admin/lti-plans/{plan.id}/budget/distribute/",
        {
            "employee_category_1": "STAFF", "mode": "MANUAL",
            "target_org_unit_ids": [parent.id, child.id],
            "manual_amounts": {parent.id: 500, child.id: 500},
        }, format="json",
    )
    assert r.status_code == 400
    assert r.json()["error"] == "TARGETS_OVERLAP"


@pytest.mark.django_db
def test_lti_distribute_rejects_non_dept_center(hr, plan):
    team = OrgUnit.objects.create(code="LT1", name="LT1", type="TEAM")
    hr.put(f"/api/admin/lti-plans/{plan.id}/budget/", {
        "rows": [{"employee_category_1": "STAFF", "headcount_quota": 1, "shares_quota_ads": 100}],
    }, format="json")
    r = hr.post(
        f"/api/admin/lti-plans/{plan.id}/budget/distribute/",
        {
            "employee_category_1": "STAFF", "mode": "MANUAL",
            "target_org_unit_ids": [team.id],
            "manual_amounts": {team.id: 100},
        }, format="json",
    )
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_TARGET_TYPE"


@pytest.mark.django_db
def test_lti_get_returns_targets_section(hr, plan, two_depts):
    a, b = two_depts
    hr.put(f"/api/admin/lti-plans/{plan.id}/budget/", {
        "rows": [{"employee_category_1": "STAFF", "headcount_quota": 3, "shares_quota_ads": 3000}],
    }, format="json")
    hr.post(
        f"/api/admin/lti-plans/{plan.id}/budget/distribute/",
        {
            "employee_category_1": "STAFF", "mode": "MANUAL",
            "target_org_unit_ids": [a.id, b.id],
            "manual_amounts": {a.id: 2000, b.id: 1000},
        }, format="json",
    )
    r = hr.get(f"/api/admin/lti-plans/{plan.id}/budget/")
    body = r.json()
    assert "company" in body and "targets" in body
    by = {t["target_org_unit_id"]: t for t in body["targets"]}
    assert int(by[a.id]["shares_quota_ads"]) == 2000
    assert int(by[b.id]["shares_quota_ads"]) == 1000
