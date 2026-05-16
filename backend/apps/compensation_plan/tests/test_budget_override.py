"""BudgetOverride 批量导入 + 派生覆盖测试。"""
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook
from rest_framework.test import APIClient
from django.core.management import call_command

from apps.iam.models import OrgUnit, User
from apps.reward_cycle.models import RewardCycle
from apps.hr_master.models import (
    CategoryScheme,
    EmployeeCategory,
    EmployeeCategoryAssignment,
    Employee,
)
from apps.compensation_plan.models import (
    BudgetOverride,
    EmployeeCategoryFactor,
    RegionalAdjustmentRule,
)
from apps.compensation_plan.services.budget_derivation import derive_budget
from apps.compensation_plan.services.budget_override_import import (
    ImportError as OverrideImportError,
    import_overrides,
)


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")
    cycle = RewardCycle.objects.get(code="RC-2026-01")
    if cycle.category_scheme is None:
        scheme, _ = CategoryScheme.objects.get_or_create(
            code="2026-default",
            defaults={"name": "2026 默认方案", "status": "ACTIVE"},
        )
        EmployeeCategory.objects.get_or_create(
            scheme=scheme, code="MGMT",
            defaults={"name": "管理干部", "sort_order": 0},
        )
        EmployeeCategory.objects.get_or_create(
            scheme=scheme, code="STAFF",
            defaults={"name": "员工", "sort_order": 1},
        )
        cycle.category_scheme = scheme
        cycle.save(update_fields=["category_scheme"])


@pytest.fixture
def cycle(seeded):
    return RewardCycle.objects.get(code="RC-2026-01")


@pytest.fixture
def scheme(cycle):
    return cycle.category_scheme


@pytest.fixture
def cat_mgmt(scheme):
    return scheme.categories.get(code="MGMT")


@pytest.fixture
def cat_staff(scheme):
    return scheme.categories.get(code="STAFF")


@pytest.fixture
def hr(seeded):
    c = APIClient()
    c.force_authenticate(User.objects.get(email="hr@demo.com"))
    return c


@pytest.fixture
def alice(seeded):
    c = APIClient()
    c.force_authenticate(User.objects.get(email="alice@demo.com"))
    return c


@pytest.fixture
def hr_user(seeded):
    return User.objects.get(email="hr@demo.com")


def _xlsx(rows: list[list]) -> bytes:
    """生成 xlsx bytes; rows[0] 是表头。"""
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


HEADER = ["department_code", "department_name", "adjustment_type", "override_amount_cny"]


# ============ Service: import golden + reject ============

def test_import_golden_creates_override(cycle, hr_user):
    content = _xlsx([HEADER, ["ENG", "Engineering", "ANNUAL", 9999.99]])
    result = import_overrides(cycle, content, hr_user)
    assert result == {"created": 1, "updated": 0, "total_rows": 1}
    eng = OrgUnit.objects.get(code="ENG")
    ov = BudgetOverride.objects.get(reward_cycle=cycle, department=eng, adjustment_type="ANNUAL")
    assert ov.override_amount_cny == Decimal("9999.99")
    assert ov.source == "IMPORTED"
    assert ov.uploaded_by == hr_user


def test_import_unknown_dept_rejects_whole_batch(cycle, hr_user):
    content = _xlsx([
        HEADER,
        ["ENG", "Engineering", "ANNUAL", 5000],
        ["NOPE", "Nope", "ANNUAL", 5000],
    ])
    with pytest.raises(OverrideImportError) as ei:
        import_overrides(cycle, content, hr_user)
    msgs = [e["msg"] for e in ei.value.errors]
    assert any("找不到" in m for m in msgs)
    # 整批拒绝, ENG 也不应该写入
    assert not BudgetOverride.objects.filter(reward_cycle=cycle).exists()


def test_import_invalid_adj_type_rejected(cycle, hr_user):
    content = _xlsx([HEADER, ["ENG", "Engineering", "BONUS", 5000]])
    with pytest.raises(OverrideImportError) as ei:
        import_overrides(cycle, content, hr_user)
    assert "ANNUAL" in ei.value.errors[0]["msg"]


def test_import_negative_amount_rejected(cycle, hr_user):
    content = _xlsx([HEADER, ["ENG", "Engineering", "ANNUAL", -100]])
    with pytest.raises(OverrideImportError) as ei:
        import_overrides(cycle, content, hr_user)
    assert "≥ 0" in ei.value.errors[0]["msg"]


def test_import_update_existing_keeps_unique(cycle, hr_user):
    eng = OrgUnit.objects.get(code="ENG")
    BudgetOverride.objects.create(
        reward_cycle=cycle, department=eng, adjustment_type="ANNUAL",
        override_amount_cny=Decimal("1000.00"), source="IMPORTED",
    )
    content = _xlsx([HEADER, ["ENG", "Engineering", "ANNUAL", 7777]])
    result = import_overrides(cycle, content, hr_user)
    assert result == {"created": 0, "updated": 1, "total_rows": 1}
    ov = BudgetOverride.objects.get(reward_cycle=cycle, department=eng, adjustment_type="ANNUAL")
    assert ov.override_amount_cny == Decimal("7777.00")


# ============ Service: derive_budget 应用 override ============

def test_override_replaces_derived_in_pool(cycle, scheme, cat_mgmt, hr_user):
    """E001 alice MGMT in ENG, derived ANNUAL = 50000×0.05×1.2 = 3000. Override → 8000."""
    EmployeeCategoryAssignment.objects.update_or_create(
        employee=Employee.objects.get(employee_no="E001"),
        scheme=scheme, defaults={"category": cat_mgmt},
    )
    RegionalAdjustmentRule.objects.update_or_create(
        reward_cycle=cycle, country="CN", adjustment_type="ANNUAL",
        defaults={"base_pct": Decimal("0.0500")},
    )
    EmployeeCategoryFactor.objects.update_or_create(
        reward_cycle=cycle, category=cat_mgmt, adjustment_type="ANNUAL",
        defaults={"factor": Decimal("1.2000")},
    )
    eng = OrgUnit.objects.get(code="ENG")
    BudgetOverride.objects.create(
        reward_cycle=cycle, department=eng, adjustment_type="ANNUAL",
        override_amount_cny=Decimal("8000.00"), source="IMPORTED",
        uploaded_by=hr_user,
    )

    result = derive_budget(cycle)
    eng_dept = next(d for d in result["departments"] if d["department_name"] == "Engineering")
    assert eng_dept["derived_annual_cny"] == Decimal("3000.00")
    assert eng_dept["override_annual_cny"] == Decimal("8000.00")
    assert eng_dept["effective_annual_cny"] == Decimal("8000.00")
    assert eng_dept["annual_source"] == "IMPORTED"
    # PROMOTION 没 override 仍是派生
    assert eng_dept["promotion_source"] == "DERIVED"


# ============ View: 权限 + 模板 + 上传 ============

def test_template_download_requires_hr(alice, cycle):
    r = alice.get(f"/api/admin/reward-cycles/{cycle.id}/budget-overrides/template/")
    assert r.status_code == 403


def test_template_download_returns_xlsx(hr, cycle):
    r = hr.get(f"/api/admin/reward-cycles/{cycle.id}/budget-overrides/template/")
    assert r.status_code == 200
    assert "spreadsheetml" in r["Content-Type"]
    assert b"PK" == r.content[:2]  # xlsx = zip


def test_import_endpoint_anonymous_401(cycle):
    c = APIClient()
    r = c.post(f"/api/admin/reward-cycles/{cycle.id}/budget-overrides/import/")
    assert r.status_code == 401


def test_import_endpoint_non_hr_403(alice, cycle):
    r = alice.post(f"/api/admin/reward-cycles/{cycle.id}/budget-overrides/import/")
    assert r.status_code == 403


def test_import_endpoint_missing_file_400(hr, cycle):
    r = hr.post(f"/api/admin/reward-cycles/{cycle.id}/budget-overrides/import/")
    assert r.status_code == 400


def test_import_endpoint_validation_errors_in_response(hr, cycle):
    content = _xlsx([HEADER, ["NOPE", "x", "ANNUAL", 100]])
    r = hr.post(
        f"/api/admin/reward-cycles/{cycle.id}/budget-overrides/import/",
        {"file": _file("import.xlsx", content)},
    )
    assert r.status_code == 400
    assert "errors" in r.data
    assert r.data["errors"][0]["row"] == 2


def test_import_endpoint_golden(hr, cycle):
    content = _xlsx([HEADER, ["ENG", "Engineering", "ANNUAL", 5500]])
    r = hr.post(
        f"/api/admin/reward-cycles/{cycle.id}/budget-overrides/import/",
        {"file": _file("import.xlsx", content)},
    )
    assert r.status_code == 200, r.data
    assert r.data["created"] == 1


def test_clear_endpoint_removes_override(hr, cycle, hr_user):
    eng = OrgUnit.objects.get(code="ENG")
    BudgetOverride.objects.create(
        reward_cycle=cycle, department=eng, adjustment_type="ANNUAL",
        override_amount_cny=Decimal("5000"), source="IMPORTED",
    )
    r = hr.delete(
        f"/api/admin/reward-cycles/{cycle.id}/budget-overrides/clear/"
        f"?department_id={eng.id}&adjustment_type=ANNUAL"
    )
    assert r.status_code == 200
    assert r.data["deleted"] == 1
    assert not BudgetOverride.objects.filter(department=eng).exists()


# ============ helpers ============

def _file(name: str, content: bytes):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(
        name, content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
