# Phase 2 Sprint 2 — 预算闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通"HR_ADMIN 设置公司总预算 → 分配到部门 → DEPT_HEAD 看到自己部门可用预算 → DEPT_HEAD 做薪酬分配 → 实时扣减"的完整闭环；并对 Phase 1 残留页面做中文化和菜单归属调整。

**Architecture:**
- 在现有 `AdjustmentBudgetCell` 和 `LTIBudgetCell` 上添加 `department` 外键（指向 `iam.OrgUnit`，`null=True` 表示"公司总"层）。**单一数据源**，避免重复模型。
- HR_ADMIN 的"预算管理"页拆成两 Tab：① 公司总预算（现有 4 格 / 2 格）② 部门分配（选部门 + 4 格 / 2 格）。每次保存校验：各部门之和 ≤ 公司总。
- DEPT_HEAD 的"本部门可用预算"通过 `request.user.employee.org_unit` 反查自己的部门行，展示已分配 / 已使用 / 剩余。
- 审批菜单：HR_ADMIN 保留全局视角；DEPT_HEAD 加"我的审批"入口（同一路由，按 `request.user` 过滤）。

**Tech Stack:** Django 5 + DRF + PostgreSQL（后端）；Vue 3 + Element Plus + Pinia + Vite（前端）。Pytest 跑后端测试，前端靠 `npm run build` + 浏览器手测（沿用 Sprint 1 方式，无前端自动化）。

---

## File Structure

**后端（新建 / 修改）：**
- Modify: `backend/apps/compensation_plan/models.py` — `AdjustmentBudgetCell` 加 `department` FK
- Create: `backend/apps/compensation_plan/migrations/0XXX_adjustmentbudgetcell_department.py`
- Modify: `backend/apps/compensation_plan/serializers.py` — `AdjustmentBudgetCellSerializer` 加 `department_id` / `department_name`
- Modify: `backend/apps/compensation_plan/views.py` — `AdjustmentBudgetView` 支持 `?department_id=` 查询，PUT 校验之和
- Modify: `backend/apps/lti/models.py` — `LTIBudgetCell` 加 `department` FK
- Create: `backend/apps/lti/migrations/0XXX_ltibudgetcell_department.py`
- Modify: `backend/apps/lti/serializers.py` — 加 `department_id` / `department_name`
- Modify: `backend/apps/lti/views.py` — `LTIBudgetView` 支持部门维度
- Create: `backend/apps/reward_cycle/views_dept.py` — DEPT_HEAD `AvailableBudgetView`
- Modify: `backend/apps/reward_cycle/urls.py` — 新增 `/api/dept/available-budget/<cycle_id>/`
- Create: `backend/apps/compensation_plan/tests/test_budget_dept.py` — 后端 TDD
- Create: `backend/apps/lti/tests/test_lti_budget_dept.py`
- Create: `backend/apps/reward_cycle/tests/test_available_budget.py`

**前端（修改）：**
- Modify: `frontend/admin/src/views/budgets/AdjustmentBudgetView.vue` — 加 Tab
- Modify: `frontend/admin/src/views/budgets/LtiBudgetView.vue` — 加 Tab
- Modify: `frontend/admin/src/views/dept/AvailableBudgetView.vue` — 占位改实现
- Modify: `frontend/admin/src/views/ApprovalView.vue` — 中文化
- Modify: `frontend/admin/src/views/ExecuteView.vue` — 中文化
- Modify: `frontend/admin/src/App.vue` — DEPT_HEAD 加"我的审批"菜单项
- Modify: `frontend/admin/src/router/index.ts` — `/approval` meta 放宽（HR_ADMIN ∪ DEPT_HEAD）

---

## Task 1: 后端 — AdjustmentBudgetCell 加 department 外键 + 迁移

**Files:**
- Modify: `backend/apps/compensation_plan/models.py:25-43`
- Create: `backend/apps/compensation_plan/migrations/0XXX_adjustmentbudgetcell_department.py`
- Test: `backend/apps/compensation_plan/tests/test_budget_dept.py`

- [ ] **Step 1: 写 model 失败测试**

Create `backend/apps/compensation_plan/tests/test_budget_dept.py`:

```python
import pytest
from decimal import Decimal
from apps.iam.models import OrgUnit
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentBudgetCell


@pytest.mark.django_db
def test_budget_cell_can_attach_department():
    cycle = RewardCycle.objects.create(code="C2026", name="2026", period="2026", status="DRAFT")
    dept = OrgUnit.objects.create(code="D-ENG", name="工程部", type="DEPT")
    cell = AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=dept, budget_amount_cny=Decimal("100000"),
    )
    assert cell.department_id == dept.id


@pytest.mark.django_db
def test_budget_cell_company_total_has_null_department():
    cycle = RewardCycle.objects.create(code="C2026B", name="2026", period="2026", status="DRAFT")
    cell = AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=None, budget_amount_cny=Decimal("500000"),
    )
    assert cell.department is None


@pytest.mark.django_db
def test_unique_together_includes_department():
    cycle = RewardCycle.objects.create(code="C2026C", name="2026", period="2026", status="DRAFT")
    dept = OrgUnit.objects.create(code="D-FIN", name="财务部", type="DEPT")
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=dept, budget_amount_cny=Decimal("100"),
    )
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=None, budget_amount_cny=Decimal("100"),
    )
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/compensation_plan/tests/test_budget_dept.py -v
```

Expected: 3 个测试 FAIL（`department` 字段不存在）。

- [ ] **Step 3: 改 model**

Modify `backend/apps/compensation_plan/models.py` 25-43 行：

```python
class AdjustmentBudgetCell(models.Model):
    ADJ_TYPE = [("ANNUAL", "年度调薪"), ("PROMOTION", "晋升调薪")]
    CAT1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]

    reward_cycle = models.ForeignKey(
        "reward_cycle.RewardCycle", on_delete=models.CASCADE, related_name="adjustment_budget_cells",
    )
    adjustment_type = models.CharField(max_length=16, choices=ADJ_TYPE)
    employee_category_1 = models.CharField(max_length=16, choices=CAT1)
    department = models.ForeignKey(
        "iam.OrgUnit", null=True, blank=True, on_delete=models.PROTECT,
        related_name="adjustment_budget_cells",
        help_text="NULL = 公司总预算层；非 NULL = 该部门分配额",
    )
    budget_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    allocated_amount_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        db_table = "comp_adjustment_budget_cell"
        unique_together = [("reward_cycle", "adjustment_type", "employee_category_1", "department")]

    @property
    def remaining_amount_cny(self):
        return self.budget_amount_cny - self.allocated_amount_cny
```

- [ ] **Step 4: 生成 migration**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe manage.py makemigrations compensation_plan
```

预期：生成 `0XXX_adjustmentbudgetcell_department.py`（新增 department 字段 + 改 unique_together）。**老数据自动落到 department=NULL，符合"公司总"语义。**

- [ ] **Step 5: 跑迁移 + 测试**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe manage.py migrate
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/compensation_plan/tests/test_budget_dept.py -v
```

Expected: 3 个测试 PASS。

- [ ] **Step 6: Commit**

```bash
cd C:/Users/yalanyuan/hr-sys
git add backend/apps/compensation_plan/models.py backend/apps/compensation_plan/migrations/ backend/apps/compensation_plan/tests/test_budget_dept.py
git commit -m "feat(budget): add department dimension to AdjustmentBudgetCell"
```

---

## Task 2: 后端 — LTIBudgetCell 加 department 外键 + 迁移

**Files:**
- Modify: `backend/apps/lti/models.py:25-36`
- Create: `backend/apps/lti/migrations/0XXX_ltibudgetcell_department.py`
- Test: `backend/apps/lti/tests/test_lti_budget_dept.py`

- [ ] **Step 1: 写 model 失败测试**

Create `backend/apps/lti/tests/test_lti_budget_dept.py`:

```python
import pytest
from datetime import date
from decimal import Decimal
from apps.iam.models import OrgUnit
from apps.lti.models import LTIPlan, LTIBudgetCell


@pytest.mark.django_db
def test_lti_budget_cell_can_attach_department():
    plan = LTIPlan.objects.create(
        code="LTI2026", name="2026", grant_date=date(2026, 6, 1),
        unit_price_at_grant=Decimal("100"),
    )
    dept = OrgUnit.objects.create(code="D-ENG", name="工程部", type="DEPT")
    cell = LTIBudgetCell.objects.create(
        plan=plan, employee_category_1="STAFF", department=dept,
        headcount_quota=10, shares_quota_ads=5000,
    )
    assert cell.department_id == dept.id


@pytest.mark.django_db
def test_lti_budget_cell_company_total_null_dept():
    plan = LTIPlan.objects.create(
        code="LTI2026B", name="2026", grant_date=date(2026, 6, 1),
        unit_price_at_grant=Decimal("100"),
    )
    cell = LTIBudgetCell.objects.create(
        plan=plan, employee_category_1="STAFF", department=None,
        headcount_quota=100, shares_quota_ads=50000,
    )
    assert cell.department is None
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/lti/tests/test_lti_budget_dept.py -v
```

Expected: FAIL（department 字段不存在）。

- [ ] **Step 3: 改 model**

Modify `backend/apps/lti/models.py` 25-36 行：

```python
class LTIBudgetCell(models.Model):
    CAT1 = [("MANAGEMENT", "管理干部"), ("STAFF", "员工")]
    plan = models.ForeignKey(LTIPlan, on_delete=models.CASCADE, related_name="budget_cells")
    employee_category_1 = models.CharField(max_length=16, choices=CAT1)
    department = models.ForeignKey(
        "iam.OrgUnit", null=True, blank=True, on_delete=models.PROTECT,
        related_name="lti_budget_cells",
        help_text="NULL = 公司总；非 NULL = 部门分配",
    )
    headcount_quota = models.IntegerField(default=0)
    shares_quota_ads = models.BigIntegerField(default=0)
    headcount_used = models.IntegerField(default=0)
    shares_used_ads = models.BigIntegerField(default=0)

    class Meta:
        db_table = "lti_budget_cell"
        unique_together = [("plan", "employee_category_1", "department")]
```

- [ ] **Step 4: 生成 migration + 跑迁移 + 测试**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe manage.py makemigrations lti
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe manage.py migrate
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/lti/tests/test_lti_budget_dept.py -v
```

Expected: 2 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/apps/lti/models.py backend/apps/lti/migrations/ backend/apps/lti/tests/test_lti_budget_dept.py
git commit -m "feat(budget): add department dimension to LTIBudgetCell"
```

---

## Task 3: 后端 — AdjustmentBudgetView 部门维度 + 校验

**Files:**
- Modify: `backend/apps/compensation_plan/serializers.py` — `AdjustmentBudgetCellSerializer` 加 department 字段
- Modify: `backend/apps/compensation_plan/views.py:53-101` — `AdjustmentBudgetView` 支持 `?department_id=`，PUT 校验之和
- Test: 追加到 `backend/apps/compensation_plan/tests/test_budget_dept.py`

- [ ] **Step 1: 写 API 失败测试**

追加到 `apps/compensation_plan/tests/test_budget_dept.py`：

```python
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.iam.models import Role, UserRole, Employee


def _make_hr_admin():
    User = get_user_model()
    user = User.objects.create_user(username="hr_test", email="hr_test@x.com", password="x")
    role, _ = Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "HR管理员"})
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.mark.django_db
def test_get_budget_company_total_default():
    cycle = RewardCycle.objects.create(code="C-API", name="x", period="2026", status="DRAFT")
    user = _make_hr_admin()
    client = APIClient()
    client.force_authenticate(user)
    resp = client.get(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 4
    for r in rows:
        assert r["department_id"] is None


@pytest.mark.django_db
def test_get_budget_by_department():
    cycle = RewardCycle.objects.create(code="C-API2", name="x", period="2026", status="DRAFT")
    dept = OrgUnit.objects.create(code="D1", name="部门1", type="DEPT")
    user = _make_hr_admin()
    client = APIClient()
    client.force_authenticate(user)
    resp = client.get(f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/?department_id={dept.id}")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 4
    assert all(r["department_id"] == dept.id for r in rows)


@pytest.mark.django_db
def test_put_department_sum_exceeds_company_total_rejected():
    cycle = RewardCycle.objects.create(code="C-API3", name="x", period="2026", status="DRAFT")
    dept = OrgUnit.objects.create(code="D1", name="部门1", type="DEPT")
    AdjustmentBudgetCell.objects.create(
        reward_cycle=cycle, adjustment_type="ANNUAL", employee_category_1="STAFF",
        department=None, budget_amount_cny=Decimal("100"),
    )
    user = _make_hr_admin()
    client = APIClient()
    client.force_authenticate(user)
    resp = client.put(
        f"/api/admin/reward-cycles/{cycle.id}/adjustment-budget/?department_id={dept.id}",
        {"rows": [{"adjustment_type": "ANNUAL", "employee_category_1": "STAFF", "budget_amount_cny": "200"}]},
        format="json",
    )
    assert resp.status_code == 400
    assert "exceeds" in resp.json().get("error", "").lower() or "超过" in resp.json().get("error", "")
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/compensation_plan/tests/test_budget_dept.py -v
```

Expected: 新增的 3 个 API 测试 FAIL（serializer 没有 department_id 字段、view 不识别 department_id 参数、没有校验）。

- [ ] **Step 3: 改 serializer**

Modify `backend/apps/compensation_plan/serializers.py`，给 `AdjustmentBudgetCellSerializer` 加字段：

```python
class AdjustmentBudgetCellSerializer(serializers.ModelSerializer):
    department_id = serializers.IntegerField(source="department_id", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    remaining_amount_cny = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = AdjustmentBudgetCell
        fields = [
            "id", "adjustment_type", "employee_category_1",
            "department_id", "department_name",
            "budget_amount_cny", "allocated_amount_cny", "remaining_amount_cny",
        ]
```

（保留原有字段；如已有 remaining 字段就不要重复加。）

- [ ] **Step 4: 改 view**

Replace `backend/apps/compensation_plan/views.py:53-101`：

```python
class AdjustmentBudgetView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def _get_dept(self, request):
        dept_id = request.query_params.get("department_id") or request.GET.get("department_id")
        if dept_id in (None, "", "null"):
            return None
        from apps.iam.models import OrgUnit
        return get_object_or_404(OrgUnit, id=dept_id, type="DEPT")

    def _ensure_cells(self, cycle, department):
        for adj in ADJ_TYPES:
            for cat in CATEGORIES:
                AdjustmentBudgetCell.objects.get_or_create(
                    reward_cycle=cycle, adjustment_type=adj,
                    employee_category_1=cat, department=department,
                    defaults={"budget_amount_cny": 0, "allocated_amount_cny": 0},
                )

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        department = self._get_dept(request)
        self._ensure_cells(cycle, department)
        cells = AdjustmentBudgetCell.objects.filter(
            reward_cycle=cycle, department=department,
        ).order_by("adjustment_type", "employee_category_1")
        return Response({"rows": AdjustmentBudgetCellSerializer(cells, many=True).data})

    def put(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        department = self._get_dept(request)
        self._ensure_cells(cycle, department)
        rows = request.data.get("rows", [])
        for row in rows:
            adj = row.get("adjustment_type")
            cat = row.get("employee_category_1")
            if adj not in ADJ_TYPES or cat not in CATEGORIES:
                return Response(
                    {"error": f"invalid adjustment_type/category: {adj}/{cat}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            new_amount = Decimal(str(row.get("budget_amount_cny", 0)))
            if department is not None:
                company_cell = AdjustmentBudgetCell.objects.filter(
                    reward_cycle=cycle, adjustment_type=adj,
                    employee_category_1=cat, department=None,
                ).first()
                company_total = company_cell.budget_amount_cny if company_cell else Decimal("0")
                other_dept_sum = AdjustmentBudgetCell.objects.filter(
                    reward_cycle=cycle, adjustment_type=adj, employee_category_1=cat,
                ).exclude(department=None).exclude(department=department).aggregate(
                    s=models.Sum("budget_amount_cny"),
                )["s"] or Decimal("0")
                if other_dept_sum + new_amount > company_total:
                    return Response(
                        {"error": f"部门预算之和 {other_dept_sum + new_amount} 超过公司总 {company_total} ({adj}/{cat})"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            cell = AdjustmentBudgetCell.objects.get(
                reward_cycle=cycle, adjustment_type=adj,
                employee_category_1=cat, department=department,
            )
            cell.budget_amount_cny = new_amount
            cell.save(update_fields=["budget_amount_cny"])
        log_action(
            event="UPDATE", actor=request.user,
            resource_type="AdjustmentBudget", resource_id=cycle.id,
            before={}, after={"department_id": department.id if department else None, "rows": rows},
        )
        all_cells = AdjustmentBudgetCell.objects.filter(
            reward_cycle=cycle, department=department,
        ).order_by("adjustment_type", "employee_category_1")
        return Response({"rows": AdjustmentBudgetCellSerializer(all_cells, many=True).data})
```

文件顶部加 `from django.db import models`（如果未引入）。

- [ ] **Step 5: 跑测试**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/compensation_plan/tests/test_budget_dept.py -v
```

Expected: 全部 PASS。

- [ ] **Step 6: 跑全量回归**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/compensation_plan -v
```

Expected: 所有原有测试仍 PASS（公司总层 GET/PUT 行为不变，老用例不受影响）。

- [ ] **Step 7: Commit**

```bash
git add backend/apps/compensation_plan/
git commit -m "feat(budget): department-scoped adjustment budget API with sum validation"
```

---

## Task 4: 后端 — LTIBudgetView 部门维度

**Files:**
- Modify: `backend/apps/lti/serializers.py`
- Modify: `backend/apps/lti/views.py`（`LTIBudgetView`）
- Test: 追加到 `apps/lti/tests/test_lti_budget_dept.py`

- [ ] **Step 1: 写失败测试**

追加到 `apps/lti/tests/test_lti_budget_dept.py`：

```python
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.iam.models import Role, UserRole


def _make_hr_admin():
    User = get_user_model()
    user = User.objects.create_user(username="hr_lti", email="hr_lti@x.com", password="x")
    role, _ = Role.objects.get_or_create(code="HR_ADMIN", defaults={"name": "HR管理员"})
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.mark.django_db
def test_lti_get_company_total_default():
    plan = LTIPlan.objects.create(code="L1", name="x", grant_date=date(2026, 6, 1), unit_price_at_grant=Decimal("100"))
    user = _make_hr_admin()
    client = APIClient(); client.force_authenticate(user)
    resp = client.get(f"/api/admin/lti-plans/{plan.id}/budget/")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 2
    assert all(r["department_id"] is None for r in rows)


@pytest.mark.django_db
def test_lti_put_department_shares_exceed_total_rejected():
    plan = LTIPlan.objects.create(code="L2", name="x", grant_date=date(2026, 6, 1), unit_price_at_grant=Decimal("100"))
    dept = OrgUnit.objects.create(code="D-LTI", name="部门LTI", type="DEPT")
    LTIBudgetCell.objects.create(plan=plan, employee_category_1="STAFF", department=None,
                                  headcount_quota=10, shares_quota_ads=1000)
    user = _make_hr_admin()
    client = APIClient(); client.force_authenticate(user)
    resp = client.put(
        f"/api/admin/lti-plans/{plan.id}/budget/?department_id={dept.id}",
        {"rows": [{"employee_category_1": "STAFF", "headcount_quota": 5, "shares_quota_ads": 2000}]},
        format="json",
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/lti/tests/test_lti_budget_dept.py -v
```

Expected: 新增 2 个 FAIL。

- [ ] **Step 3: 改 serializer**

Modify `apps/lti/serializers.py` 中的 `LTIBudgetCellSerializer`，加：

```python
department_id = serializers.IntegerField(source="department_id", read_only=True, allow_null=True)
department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
```

并把 `department_id` / `department_name` 加进 `Meta.fields`。

- [ ] **Step 4: 改 view**

Modify `apps/lti/views.py` 的 `LTIBudgetView`：

```python
class LTIBudgetView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def _get_dept(self, request):
        dept_id = request.query_params.get("department_id")
        if dept_id in (None, "", "null"):
            return None
        from apps.iam.models import OrgUnit
        return get_object_or_404(OrgUnit, id=dept_id, type="DEPT")

    def _ensure_cells(self, plan, department):
        for cat in ["MANAGEMENT", "STAFF"]:
            LTIBudgetCell.objects.get_or_create(
                plan=plan, employee_category_1=cat, department=department,
                defaults={"headcount_quota": 0, "shares_quota_ads": 0},
            )

    def get(self, request, plan_id):
        plan = get_object_or_404(LTIPlan, id=plan_id)
        dept = self._get_dept(request)
        self._ensure_cells(plan, dept)
        cells = LTIBudgetCell.objects.filter(plan=plan, department=dept).order_by("employee_category_1")
        return Response({"rows": LTIBudgetCellSerializer(cells, many=True).data})

    def put(self, request, plan_id):
        plan = get_object_or_404(LTIPlan, id=plan_id)
        dept = self._get_dept(request)
        self._ensure_cells(plan, dept)
        rows = request.data.get("rows", [])
        for row in rows:
            cat = row.get("employee_category_1")
            new_shares = int(row.get("shares_quota_ads", 0))
            new_hc = int(row.get("headcount_quota", 0))
            if dept is not None:
                company = LTIBudgetCell.objects.filter(plan=plan, employee_category_1=cat, department=None).first()
                comp_shares = company.shares_quota_ads if company else 0
                comp_hc = company.headcount_quota if company else 0
                others = LTIBudgetCell.objects.filter(
                    plan=plan, employee_category_1=cat,
                ).exclude(department=None).exclude(department=dept).aggregate(
                    s=models.Sum("shares_quota_ads"), h=models.Sum("headcount_quota"),
                )
                other_shares = others["s"] or 0
                other_hc = others["h"] or 0
                if other_shares + new_shares > comp_shares:
                    return Response({"error": f"部门股数之和超过公司总 ({cat})"}, status=400)
                if other_hc + new_hc > comp_hc:
                    return Response({"error": f"部门人数之和超过公司总 ({cat})"}, status=400)
            cell = LTIBudgetCell.objects.get(plan=plan, employee_category_1=cat, department=dept)
            cell.headcount_quota = new_hc
            cell.shares_quota_ads = new_shares
            cell.save(update_fields=["headcount_quota", "shares_quota_ads"])
        all_cells = LTIBudgetCell.objects.filter(plan=plan, department=dept).order_by("employee_category_1")
        return Response({"rows": LTIBudgetCellSerializer(all_cells, many=True).data})
```

顶部加 `from django.db import models` 如未引入。

- [ ] **Step 5: 跑测试 + 回归**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/lti -v
```

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/apps/lti/
git commit -m "feat(budget): department-scoped LTI budget API with sum validation"
```

---

## Task 5: 后端 — DEPT_HEAD "本部门可用预算" 接口

**Files:**
- Create: `backend/apps/reward_cycle/views_dept.py`
- Modify: `backend/apps/reward_cycle/urls.py`
- Test: `backend/apps/reward_cycle/tests/test_available_budget.py`

- [ ] **Step 1: 写失败测试**

Create `backend/apps/reward_cycle/tests/test_available_budget.py`:

```python
import pytest
from datetime import date
from decimal import Decimal
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.iam.models import OrgUnit, Role, UserRole
from apps.hr_master.models import Employee
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentBudgetCell, AdjustmentPlan
from apps.lti.models import LTIPlan, LTIBudgetCell


def _make_dept_head(dept):
    User = get_user_model()
    user = User.objects.create_user(username="dh_test", email="dh_test@x.com", password="x")
    role, _ = Role.objects.get_or_create(code="DEPT_HEAD", defaults={"name": "部门负责人"})
    UserRole.objects.create(user=user, role=role)
    Employee.objects.create(
        employee_no="E001", name_cn="头", user=user, org_unit=dept,
        dept_name=dept.name, status="ACTIVE",
    )
    return user


@pytest.mark.django_db
def test_dept_head_sees_only_own_dept_budget():
    cycle = RewardCycle.objects.create(code="C-DH", name="x", period="2026", status="ALLOCATING")
    dept_a = OrgUnit.objects.create(code="DA", name="A部", type="DEPT")
    dept_b = OrgUnit.objects.create(code="DB", name="B部", type="DEPT")
    AdjustmentBudgetCell.objects.create(reward_cycle=cycle, adjustment_type="ANNUAL",
                                         employee_category_1="STAFF", department=dept_a,
                                         budget_amount_cny=Decimal("500"))
    AdjustmentBudgetCell.objects.create(reward_cycle=cycle, adjustment_type="ANNUAL",
                                         employee_category_1="STAFF", department=dept_b,
                                         budget_amount_cny=Decimal("999"))
    user = _make_dept_head(dept_a)
    client = APIClient(); client.force_authenticate(user)
    resp = client.get(f"/api/dept/available-budget/{cycle.id}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["department"]["id"] == dept_a.id
    rows = body["adjustment_rows"]
    matching = [r for r in rows if r["adjustment_type"] == "ANNUAL" and r["employee_category_1"] == "STAFF"]
    assert len(matching) == 1
    assert Decimal(matching[0]["budget_amount_cny"]) == Decimal("500")


@pytest.mark.django_db
def test_dept_head_no_employee_returns_404():
    cycle = RewardCycle.objects.create(code="C-DH2", name="x", period="2026", status="ALLOCATING")
    User = get_user_model()
    user = User.objects.create_user(username="orphan", email="o@x.com", password="x")
    role, _ = Role.objects.get_or_create(code="DEPT_HEAD", defaults={"name": "部门负责人"})
    UserRole.objects.create(user=user, role=role)
    client = APIClient(); client.force_authenticate(user)
    resp = client.get(f"/api/dept/available-budget/{cycle.id}/")
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/reward_cycle/tests/test_available_budget.py -v
```

Expected: 2 个 FAIL（路由不存在）。

- [ ] **Step 3: 写 view**

Create `backend/apps/reward_cycle/views_dept.py`:

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from apps.reward_cycle.models import RewardCycle
from apps.compensation_plan.models import AdjustmentBudgetCell
from apps.lti.models import LTIBudgetCell, LTIPlan


class AvailableBudgetView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_id):
        cycle = get_object_or_404(RewardCycle, id=cycle_id)
        emp = getattr(request.user, "employee_set", None)
        emp = request.user.employee_set.first() if hasattr(request.user, "employee_set") else None
        if emp is None or emp.org_unit_id is None:
            return Response({"error": "用户未关联员工或部门"}, status=status.HTTP_404_NOT_FOUND)
        dept = emp.org_unit
        adj_rows = AdjustmentBudgetCell.objects.filter(
            reward_cycle=cycle, department=dept,
        ).order_by("adjustment_type", "employee_category_1")
        adj_data = [{
            "adjustment_type": c.adjustment_type,
            "employee_category_1": c.employee_category_1,
            "budget_amount_cny": str(c.budget_amount_cny),
            "allocated_amount_cny": str(c.allocated_amount_cny),
            "remaining_amount_cny": str(c.remaining_amount_cny),
        } for c in adj_rows]
        lti_plan = LTIPlan.objects.filter(reward_cycle=cycle).order_by("-id").first()
        lti_data = []
        if lti_plan:
            lti_cells = LTIBudgetCell.objects.filter(plan=lti_plan, department=dept).order_by("employee_category_1")
            lti_data = [{
                "employee_category_1": c.employee_category_1,
                "headcount_quota": c.headcount_quota,
                "headcount_used": c.headcount_used,
                "shares_quota_ads": c.shares_quota_ads,
                "shares_used_ads": c.shares_used_ads,
            } for c in lti_cells]
        return Response({
            "cycle": {"id": cycle.id, "code": cycle.code, "status": cycle.status},
            "department": {"id": dept.id, "code": dept.code, "name": dept.name},
            "adjustment_rows": adj_data,
            "lti_rows": lti_data,
        })
```

注：`Employee` 模型的反向关系名取决于 `user` 字段定义。如果 Employee 上 `user = ForeignKey(User, ...)` 没设 related_name，那默认是 `employee_set`。**实际跑测试前先 grep 确认。** 如果是 OneToOne 或 related_name 不同，就改为 `request.user.employee` 或对应名称。

- [ ] **Step 4: 接路由**

Modify `backend/apps/reward_cycle/urls.py` 加：

```python
from apps.reward_cycle.views_dept import AvailableBudgetView
# ... 在 urlpatterns 加：
# path("dept/available-budget/<int:cycle_id>/", AvailableBudgetView.as_view()),
```

如果项目顶层 `urls.py` 把 `apps.reward_cycle.urls` 挂在 `/api/`，则路由会变成 `/api/dept/available-budget/<id>/`，与测试一致。**先确认顶层挂载点；不一致则改测试或路由。**

- [ ] **Step 5: 跑测试**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest apps/reward_cycle/tests/test_available_budget.py -v
```

Expected: 2 个 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/apps/reward_cycle/views_dept.py backend/apps/reward_cycle/urls.py backend/apps/reward_cycle/tests/test_available_budget.py
git commit -m "feat(dept): available-budget endpoint for department heads"
```

---

## Task 6: 前端 — AdjustmentBudgetView 加 Tab（公司总 / 部门分配）

**Files:**
- Modify: `frontend/admin/src/views/budgets/AdjustmentBudgetView.vue`

- [ ] **Step 1: 改造为 Tab 布局**

Replace 整个文件模板为两 Tab 结构：

```vue
<template>
  <el-container direction="vertical" style="padding: 16px">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>调薪预算管理</span>
          <el-select v-model="cycleId" placeholder="选择周期" style="width: 220px" @change="loadAll">
            <el-option v-for="c in cycles" :key="c.id" :label="c.code" :value="c.id" />
          </el-select>
        </div>
      </template>
      <el-tabs v-model="activeTab" @tab-change="loadAll">
        <el-tab-pane label="公司总预算" name="company">
          <BudgetGrid :rows="companyRows" :editable="true" @save="saveCompany" />
        </el-tab-pane>
        <el-tab-pane label="部门分配" name="dept">
          <el-form inline style="margin-bottom: 12px">
            <el-form-item label="部门">
              <el-select v-model="deptId" placeholder="选部门" style="width: 240px" @change="loadDept">
                <el-option v-for="d in depts" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <BudgetGrid v-if="deptId" :rows="deptRows" :editable="true" @save="saveDept" />
          <el-empty v-else description="请先选择部门" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { ElMessage } from "element-plus"
import api from "@/api/client"
import BudgetGrid from "./BudgetGrid.vue"

const cycles = ref<any[]>([])
const cycleId = ref<number | null>(null)
const depts = ref<any[]>([])
const deptId = ref<number | null>(null)
const companyRows = ref<any[]>([])
const deptRows = ref<any[]>([])
const activeTab = ref("company")

async function loadCycles() {
  const r = await api.get("/reward-cycle/")
  cycles.value = r.data.results || r.data
  if (cycles.value.length) cycleId.value = cycles.value[0].id
}
async function loadDepts() {
  const r = await api.get("/admin/org-units/?type=DEPT")
  depts.value = r.data.results || r.data
}
async function loadCompany() {
  if (!cycleId.value) return
  const r = await api.get(`/admin/reward-cycles/${cycleId.value}/adjustment-budget/`)
  companyRows.value = r.data.rows
}
async function loadDept() {
  if (!cycleId.value || !deptId.value) return
  const r = await api.get(`/admin/reward-cycles/${cycleId.value}/adjustment-budget/?department_id=${deptId.value}`)
  deptRows.value = r.data.rows
}
async function loadAll() {
  await loadCompany()
  if (activeTab.value === "dept") await loadDept()
}
async function saveCompany(rows: any[]) {
  await api.put(`/admin/reward-cycles/${cycleId.value}/adjustment-budget/`, { rows })
  ElMessage.success("公司总预算已保存")
  await loadCompany()
}
async function saveDept(rows: any[]) {
  try {
    await api.put(`/admin/reward-cycles/${cycleId.value}/adjustment-budget/?department_id=${deptId.value}`, { rows })
    ElMessage.success("部门预算已保存")
    await loadDept()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || "保存失败")
  }
}
onMounted(async () => {
  await loadDepts()
  await loadCycles()
  await loadCompany()
})
</script>
```

- [ ] **Step 2: 抽出 BudgetGrid 子组件**

Create `frontend/admin/src/views/budgets/BudgetGrid.vue`，把现有 4 格 UI 搬过来。组件 props: `rows: array`, `editable: boolean`；emits: `save(rows)`。从原 AdjustmentBudgetView 直接搬运现有的 ElTable + ElInputNumber + 保存按钮 + 进度条逻辑。

如果当前 `AdjustmentBudgetView.vue` 已有 BudgetCell 内嵌组件，直接把整段表格 + 保存按钮提到新文件即可。

- [ ] **Step 3: 确认有 `/admin/org-units/?type=DEPT` 接口**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -c "from django.urls import get_resolver; \
    [print(p) for p in get_resolver().reverse_dict.keys() if isinstance(p, str) and 'org' in p.lower()]"
```

如果不存在，**插入一个最小的只读 list 接口**到 `apps/iam/views.py`：

```python
class OrgUnitListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from apps.iam.models import OrgUnit
        t = request.query_params.get("type")
        qs = OrgUnit.objects.all()
        if t:
            qs = qs.filter(type=t)
        return Response({"results": [
            {"id": o.id, "code": o.code, "name": o.name, "type": o.type} for o in qs
        ]})
```

并在 `apps/iam/admin_urls.py`（或对应 admin 路由文件）加 `path("org-units/", OrgUnitListView.as_view())`。**先 grep 路由文件看现状再决定挂载位置。**

- [ ] **Step 4: 编译验证**

```bash
cd frontend/admin
npm run build
```

Expected: 编译通过，无 TS 报错。

- [ ] **Step 5: 浏览器手测（短）**

启动前后端，hr@demo.com 登录 → 预算管理 → 调薪预算：
1. "公司总预算" Tab：能看到 4 格、改数字、点保存提示成功
2. "部门分配" Tab：选部门 → 4 格显示该部门的；填超过公司总的数字保存 → 出错提示包含"超过公司总"

如果都通过，记一笔；不过则修。

- [ ] **Step 6: Commit**

```bash
git add frontend/admin/src/views/budgets/
git commit -m "feat(admin-fe): two-tab budget UI for company total + department allocation"
```

---

## Task 7: 前端 — LtiBudgetView 同样加 Tab

**Files:**
- Modify: `frontend/admin/src/views/budgets/LtiBudgetView.vue`

- [ ] **Step 1: 套用 Task 6 模式改造**

参照 Task 6 的 AdjustmentBudgetView 改造方式，把 `LtiBudgetView.vue` 改为两 Tab：
- 公司总预算（2 格 MANAGEMENT/STAFF，含 headcount + shares）
- 部门分配（选部门 + 同 2 格）

API 前缀改为 `/admin/lti-plans/${planId}/budget/`，参数 `?department_id=`。Plan 选择类似 cycle 选择。

抽 `LtiBudgetGrid.vue` 子组件复用。

- [ ] **Step 2: 编译 + 手测**

```bash
cd frontend/admin
npm run build
```

浏览器：hr@demo.com → 预算管理 → RSU 预算 → 两 Tab 各能 GET/PUT，超额校验生效。

- [ ] **Step 3: Commit**

```bash
git add frontend/admin/src/views/budgets/
git commit -m "feat(admin-fe): two-tab LTI budget UI"
```

---

## Task 8: 前端 — DEPT_HEAD AvailableBudgetView 实现

**Files:**
- Modify: `frontend/admin/src/views/dept/AvailableBudgetView.vue`

- [ ] **Step 1: 替换占位为真实页面**

Replace 整个文件：

```vue
<template>
  <el-container direction="vertical" style="padding: 16px">
    <el-card v-if="data">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>本部门可用预算 — {{ data.department.name }}</span>
          <el-select v-model="cycleId" style="width: 220px" @change="load">
            <el-option v-for="c in cycles" :key="c.id" :label="c.code" :value="c.id" />
          </el-select>
        </div>
      </template>

      <h4 style="margin: 8px 0">调薪预算（部门额）</h4>
      <el-table :data="data.adjustment_rows" border stripe size="small">
        <el-table-column label="调薪类型" prop="adjustment_type">
          <template #default="{ row }">{{ adjLabel(row.adjustment_type) }}</template>
        </el-table-column>
        <el-table-column label="人员类别" prop="employee_category_1">
          <template #default="{ row }">{{ catLabel(row.employee_category_1) }}</template>
        </el-table-column>
        <el-table-column label="预算（CNY）" prop="budget_amount_cny" />
        <el-table-column label="已分配（CNY）" prop="allocated_amount_cny" />
        <el-table-column label="剩余（CNY）" prop="remaining_amount_cny">
          <template #default="{ row }">
            <el-tag :type="Number(row.remaining_amount_cny) < 0 ? 'danger' : 'success'">
              {{ row.remaining_amount_cny }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="使用率">
          <template #default="{ row }">
            <el-progress :percentage="usagePct(row)" />
          </template>
        </el-table-column>
      </el-table>

      <h4 style="margin: 16px 0 8px">RSU 预算（部门额）</h4>
      <el-table :data="data.lti_rows" border stripe size="small">
        <el-table-column label="人员类别" prop="employee_category_1">
          <template #default="{ row }">{{ catLabel(row.employee_category_1) }}</template>
        </el-table-column>
        <el-table-column label="人数限额" prop="headcount_quota" />
        <el-table-column label="人数已用" prop="headcount_used" />
        <el-table-column label="股数限额(ADS)" prop="shares_quota_ads" />
        <el-table-column label="股数已用(ADS)" prop="shares_used_ads" />
      </el-table>
    </el-card>
    <el-empty v-else-if="error" :description="error" />
    <el-empty v-else description="加载中..." />
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api/client"

const cycles = ref<any[]>([])
const cycleId = ref<number | null>(null)
const data = ref<any>(null)
const error = ref<string>("")

function adjLabel(t: string) {
  return t === "ANNUAL" ? "年度调薪" : t === "PROMOTION" ? "晋升调薪" : t
}
function catLabel(c: string) {
  return c === "MANAGEMENT" ? "管理干部" : c === "STAFF" ? "员工" : c
}
function usagePct(row: any) {
  const total = Number(row.budget_amount_cny || 0)
  const used = Number(row.allocated_amount_cny || 0)
  if (!total) return 0
  return Math.min(100, Math.round((used / total) * 100))
}

async function loadCycles() {
  const r = await api.get("/reward-cycle/")
  cycles.value = r.data.results || r.data
  if (cycles.value.length) cycleId.value = cycles.value[0].id
}

async function load() {
  if (!cycleId.value) return
  try {
    const r = await api.get(`/dept/available-budget/${cycleId.value}/`)
    data.value = r.data
    error.value = ""
  } catch (e: any) {
    error.value = e?.response?.data?.error || "加载失败"
    data.value = null
  }
}

onMounted(async () => {
  await loadCycles()
  await load()
})
</script>
```

- [ ] **Step 2: 编译 + 手测**

```bash
cd frontend/admin
npm run build
```

浏览器：depthead@demo.com 登录 → 本部门预算 → 应看到自己部门的 4 格调薪 + 2 格 RSU。

- [ ] **Step 3: Commit**

```bash
git add frontend/admin/src/views/dept/AvailableBudgetView.vue
git commit -m "feat(dept-fe): real available-budget view replacing placeholder"
```

---

## Task 9: 前端 — ApprovalView 中文化

**Files:**
- Modify: `frontend/admin/src/views/ApprovalView.vue`

- [ ] **Step 1: 把英文文案逐项改成中文**

替换：
- `"My Pending Approvals"` → `"我的待审批"`
- 列标题 `"Scenario"` → `"场景"`，`"Target"` → `"对象"`，`"Target ID"` → `"对象ID"`，`"Step"` → `"步骤"`，`"Over Budget"` → `"超预算"`，`"Actions"` → `"操作"`
- 标签 `"YES"` → `"是"`，类似 `"NO"` → `"否"`
- 按钮 `"Approve"` → `"通过"`，`"Reject"` → `"驳回"`
- 输入框 `placeholder="comment"` → `placeholder="审批意见"`
- 任何 `ElMessage.success("Approved")` 类提示同步中文化

- [ ] **Step 2: 编译 + 看一眼**

```bash
cd frontend/admin
npm run build
```

浏览器：hr@demo.com → 审批 → 审批列表，确认全中文。

- [ ] **Step 3: Commit**

```bash
git add frontend/admin/src/views/ApprovalView.vue
git commit -m "i18n: localize ApprovalView to Chinese"
```

---

## Task 10: 前端 — ExecuteView 中文化

**Files:**
- Modify: `frontend/admin/src/views/ExecuteView.vue`

- [ ] **Step 1: 把英文文案改为中文**

替换：
- `"Execute Reward Cycle"` → `"执行下发"`
- `"Code"` → `"周期编码"`，`"Status"` → `"状态"`
- `"MFA Code"` → `"MFA 验证码"`
- `"Execute"` 按钮 → `"执行"`
- `"Executed at"` → `"执行时间"`
- 任何提示文案同步中文

- [ ] **Step 2: 编译 + 看一眼**

```bash
cd frontend/admin
npm run build
```

浏览器：hr@demo.com → 审批 → 执行下发，确认全中文。

- [ ] **Step 3: Commit**

```bash
git add frontend/admin/src/views/ExecuteView.vue
git commit -m "i18n: localize ExecuteView to Chinese"
```

---

## Task 11: 前端 — DEPT_HEAD 加"我的审批"菜单 + 路由放宽

**Files:**
- Modify: `frontend/admin/src/router/index.ts`
- Modify: `frontend/admin/src/App.vue`
- Modify: `frontend/admin/src/views/ApprovalView.vue`（角色判定决定接口过滤）

- [ ] **Step 1: 路由 meta 放宽**

Modify `router/index.ts`：把 `/approval` 路由的 `meta.requiresAdmin` 改为同时允许 DEPT_HEAD：

```ts
{ path: "/approval", component: () => import("@/views/ApprovalView.vue"),
  meta: { requiresAuth: true, allowedRoles: ["HR_ADMIN", "DEPT_HEAD"] } },
```

并修改路由守卫，把对 `requiresAdmin` 的判断改为对 `allowedRoles` 的判断（兼容老的 `requiresAdmin` 用例：把它折算为 `allowedRoles=["HR_ADMIN"]`）。

如果 `/execute` 当前 requiresAdmin，**保持** HR_ADMIN-only。

- [ ] **Step 2: App.vue 菜单**

Modify `App.vue`：在 DEPT_HEAD 菜单段加 `<el-menu-item index="/approval">我的审批</el-menu-item>`：

```vue
<template v-if="isDeptHead">
  <el-menu-item index="/dept/available-budget">本部门预算</el-menu-item>
  <el-menu-item index="/allocation">薪酬分配</el-menu-item>
  <el-menu-item index="/approval">我的审批</el-menu-item>
  <el-menu-item index="/dept/analysis">分配分析</el-menu-item>
</template>
```

HR_ADMIN 的"审批"子菜单保持原样。

- [ ] **Step 3: ApprovalView 后端过滤已生效（确认）**

ApprovalView 的接口（`/api/approvals/?assignee_id=me` 或类似）应该已经按 `request.user` 过滤"待我审批的"。**先 grep 确认**；如果是 HR_ADMIN 看全局 vs DEPT_HEAD 看自己的，由后端按 role 区分（HR_ADMIN 看所有 pending，DEPT_HEAD 只看自己 assignee 的）。

如果当前没区分，加一个 query：DEPT_HEAD 总是只返回 `assignee_user=request.user`。

- [ ] **Step 4: 编译 + 手测**

```bash
cd frontend/admin
npm run build
```

浏览器：
1. hr@demo.com → 审批 → 审批列表 + 执行下发 都能进
2. depthead@demo.com → 我的审批 能进，看到的应是分配给自己的；不该看到 /execute 入口

- [ ] **Step 5: Commit**

```bash
git add frontend/admin/src/router/index.ts frontend/admin/src/App.vue frontend/admin/src/views/ApprovalView.vue
git commit -m "feat(approval): DEPT_HEAD menu entry for my-approvals"
```

---

## Task 12: 端到端冒烟测试（手动）

**Files:** 无代码改动；手动验证。

- [ ] **Step 1: 全后端测试通过**

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_DB=hrsys POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_PORT=5432 \
  .venv/Scripts/python.exe -m pytest -v
```

Expected: 全绿（>= Sprint 1 的 19 个 + 本 Sprint 新增的 ≈ 8 个 = 27 左右）。

- [ ] **Step 2: 前端编译通过**

```bash
cd frontend/admin
npm run build
```

Expected: 0 error。

- [ ] **Step 3: 启动 dev 环境**

按用户日常方式启动 backend + frontend dev server。

- [ ] **Step 4: HR_ADMIN 闭环走一遍**

hr@demo.com 登录：
1. 方案设计 / 调薪方案 → 创建或选已存周期
2. 预算管理 / 调薪预算 → 公司总 Tab 设值（如 ANNUAL/STAFF=1,000,000）
3. 切到部门分配 Tab → 选某部门 → 给该部门分配 600,000；保存成功
4. 再选另一部门 → 试着分配 500,000（合计 1,100,000 > 1,000,000）→ 应被拒绝并显示错误
5. 改为 400,000 → 保存成功
6. RSU 预算同样走一遍

- [ ] **Step 5: DEPT_HEAD 视角验证**

depthead@demo.com 登录：
1. 本部门预算 → 应看到 HR_ADMIN 给自己分的 600,000（如果该 dept 头是该部门）
2. 薪酬分配 → AllocationView 正常
3. 我的审批 → 列表正常

- [ ] **Step 6: 总结收尾**

更新 memory 文件 `project_hrsys_phase2_sprint1.md`：把 Sprint 2 完成情况追加到末尾，或新建 `project_hrsys_phase2_sprint2.md`，记录：
- Sprint 2 完成的 task 列表
- 关键 commit hash
- 已知遗留（如 #2 组织管理、#3 薪酬区间、#5 分析、#5b ESS 仍未做，留 Sprint 3）

---

## 完成标志

- 全部测试绿
- HR_ADMIN 能在 UI 设公司总 + 分到部门，超额被拒
- DEPT_HEAD 能看到自己部门的预算，不看到别部门
- ApprovalView / ExecuteView 全中文
- DEPT_HEAD 菜单有"我的审批"，HR_ADMIN 菜单不动
- 全部改动落到 master，至少 4-5 个 commit（按上面逐 task commit 最终聚合 ≈ 10 个 commit）
