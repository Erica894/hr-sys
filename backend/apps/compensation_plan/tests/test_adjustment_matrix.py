"""调薪矩阵 (AdjustmentMatrixCell) CRUD + 校验测试。"""
import pytest
from rest_framework.test import APIClient
from django.core.management import call_command

from apps.iam.models import User
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentPlan, AdjustmentMatrixCell
from apps.hr_master.models import EmployeeCategory, CategoryScheme


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")
    # 在测试 DB 中, hr_master 0005 数据迁移跑在 seed 之前, 此时 RC 尚不存在,
    # 所以这里手动确保 RC-2026-01 绑定上 default scheme.
    cycle = RewardCycle.objects.get(code="RC-2026-01")
    if cycle.category_scheme is None:
        scheme, _ = CategoryScheme.objects.get_or_create(
            code="2026-default",
            defaults={"name": "2026 默认方案 (干部 / 员工)", "status": "ACTIVE"},
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
def cycle(seeded):
    return RewardCycle.objects.get(code="RC-2026-01")


@pytest.fixture
def category(cycle):
    scheme = cycle.category_scheme
    assert scheme is not None, "seed 应已绑定 category_scheme"
    return scheme.categories.order_by("sort_order").first()


def _payload(cycle, category, perf_grade_code="STAR_5", pay_band="P50_P75",
             coef_low="1.0000", coef_high="1.5000"):
    return {
        "reward_cycle": cycle.id,
        "category": category.id,
        "perf_grade_code": perf_grade_code,
        "pay_band": pay_band,
        "coef_low": coef_low,
        "coef_high": coef_high,
    }


def test_anonymous_gets_401(seeded):
    c = APIClient()
    r = c.get("/api/admin/adjustment-matrix-cells/")
    assert r.status_code == 401


def test_non_hr_gets_403(alice):
    r = alice.get("/api/admin/adjustment-matrix-cells/")
    assert r.status_code == 403


def test_hr_can_create_cell(hr, cycle, category):
    r = hr.post("/api/admin/adjustment-matrix-cells/", _payload(cycle, category), format="json")
    assert r.status_code == 201, r.data
    assert AdjustmentMatrixCell.objects.filter(
        reward_cycle=cycle, category=category, perf_grade_code="STAR_5",
    ).exists()


def test_coef_high_lower_than_low_rejected(hr, cycle, category):
    r = hr.post(
        "/api/admin/adjustment-matrix-cells/",
        _payload(cycle, category, coef_low="1.5000", coef_high="1.0000"),
        format="json",
    )
    assert r.status_code == 400
    assert "coef_high" in r.data


def test_unknown_perf_grade_rejected(hr, cycle, category):
    r = hr.post(
        "/api/admin/adjustment-matrix-cells/",
        _payload(cycle, category, perf_grade_code="UNKNOWN_GRADE"),
        format="json",
    )
    assert r.status_code == 400
    assert "perf_grade_code" in r.data


def test_unique_together_rejects_duplicate(hr, cycle, category):
    hr.post("/api/admin/adjustment-matrix-cells/", _payload(cycle, category), format="json")
    r = hr.post("/api/admin/adjustment-matrix-cells/", _payload(cycle, category), format="json")
    assert r.status_code == 400


def test_filter_by_cycle_and_category(hr, cycle, category):
    hr.post("/api/admin/adjustment-matrix-cells/", _payload(cycle, category), format="json")
    r = hr.get(f"/api/admin/adjustment-matrix-cells/?cycle={cycle.id}&category={category.id}")
    assert r.status_code == 200
    rows = r.data if isinstance(r.data, list) else r.data.get("results", [])
    assert len(rows) >= 1
    for row in rows:
        assert row["reward_cycle"] == cycle.id
        assert row["category"] == category.id


def test_perf_grade_added_then_cell_creatable(hr, cycle, category):
    plan = AdjustmentPlan.objects.get(reward_cycle=cycle)
    plan.perf_grades = plan.perf_grades + [
        {"code": "S_TIER", "label": "S 档", "sort_order": 0},
    ]
    plan.save(update_fields=["perf_grades"])
    r = hr.post(
        "/api/admin/adjustment-matrix-cells/",
        _payload(cycle, category, perf_grade_code="S_TIER"),
        format="json",
    )
    assert r.status_code == 201, r.data


def test_plan_create_seeds_default_grades(hr):
    plan = AdjustmentPlan.objects.create(code="ADJ-NEW", name="N", period="2026")
    assert len(plan.perf_grades) == 5
    assert {g["code"] for g in plan.perf_grades} == {
        "STAR_5", "STAR_4", "STAR_3", "STAR_2", "STAR_1",
    }
