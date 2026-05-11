# Sprint 1 · iam + hr_master 决策落地实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 spec 修订（2026-05-11）的决策 4（CENTER_HEAD 常驻角色 + FieldPermissionGrant）、决策 5（5 级灵活组织树 + 兼任表）落到 iam / hr_master 两个 app；同时补 8 条已挂 Sprint 1 的漏项（EmployeeFreeze、LevelBand、PositionGrade、MfaChallenge、SessionRevocation、OrgUnit.code unique 复核、Role.base_field_set、EMPLOYEE_LEAF unit_type）。

**Architecture:** 全部走 Django ORM + 数据迁移；新模型只加表，不改既有表的 destructive 列；在 iam/hr_master 内分别建 `tests/test_*.py` 配 pytest-django；不写 view/serializer（留给 Sprint 2 起接入分配页时再加）。**关键铁则**：现有 5 commit / 27 测试 / 10 app 骨架不能被破坏，所有变更通过新增/扩展实现。

**Tech Stack:** Django 5.0.6 + DRF 3.15.2 + psycopg 3 + pytest 8 + pytest-django 4.8 + factory-boy 3.3。

---

## 0. Spec → 任务映射

| Spec 修订条 | 对应 Task |
|------|------|
| §2.1 Role 加 GROUP_LEAD/FINANCE/AUDITOR + base_field_set | Task 1 |
| §2.1 RSU_FIELD_GROUP 白名单 | Task 2 |
| §2.1 新增 FieldPermissionGrant | Task 3 |
| §2.1 删除 PermissionDelegation | Task 4（确认未建，留 grep 守护测试） |
| §2.1 新增 OrgUnitManager + §2.2 OrgUnit 加 EMPLOYEE_LEAF | Task 5 |
| §5 数据范围硬约束 DataScopedQuerysetMixin（基础版） | Task 6 |
| §5 漏项 MfaChallenge | Task 7 |
| §5 漏项 SessionRevocation | Task 8 |
| §5 漏项 LevelBand + PositionGrade | Task 9 |
| §5 漏项 EmployeeFreeze | Task 10 |
| §5 Audit 关联 field_grant_id | 推迟到 Sprint 3（audit 重写） |

---

## 1. 文件结构（Sprint 1 范围）

**iam 新增 / 修改：**

- Modify: `backend/apps/iam/models.py`（增 `RSU_FIELD_GROUP` 常量、`FieldPermissionGrant`、`OrgUnitManager`、`MfaChallenge`、`SessionRevocation`；扩 `Role.ROLE_CHOICES` + `Role.base_field_set` 字段；扩 `OrgUnit.TYPE_CHOICES`）
- Create: `backend/apps/iam/constants.py`（集中常量：角色基线字段集、RSU 字段集）
- Create: `backend/apps/iam/migrations/0002_sprint1_baseline.py`（schema 迁移）
- Create: `backend/apps/iam/migrations/0003_seed_system_roles.py`（数据迁移：插入 7 常驻 Role 行 + 写入 base_field_set）
- Create: `backend/apps/iam/scoping.py`（`DataScopedQuerysetMixin` + `resolve_user_org_scope` 工具函数）
- Modify: `backend/apps/iam/tests/test_models.py`（新增/扩展用例）
- Create: `backend/apps/iam/tests/test_field_permission_grant.py`
- Create: `backend/apps/iam/tests/test_org_unit_manager.py`
- Create: `backend/apps/iam/tests/test_scoping.py`
- Create: `backend/apps/iam/tests/test_no_permission_delegation.py`（守护：永远不会出现 PermissionDelegation 字符串）

**hr_master 新增 / 修改：**

- Modify: `backend/apps/hr_master/models.py`（增 `LevelBand`、`PositionGrade`、`EmployeeFreeze`）
- Create: `backend/apps/hr_master/migrations/0002_dictionaries_and_freeze.py`
- Create: `backend/apps/hr_master/tests/test_dictionaries.py`
- Create: `backend/apps/hr_master/tests/test_employee_freeze.py`

**约束：** 不改已存在的表结构（不动 `User`、`Employee`、`OrgUnit.code/parent` 等列）；只加字段、加表、加约束。

---

## 2. 任务

### Task 1: Role 扩常驻角色 + base_field_set 字段

**Files:**
- Create: `backend/apps/iam/constants.py`
- Modify: `backend/apps/iam/models.py:29-44`
- Create: `backend/apps/iam/migrations/0002_sprint1_baseline.py`
- Create: `backend/apps/iam/migrations/0003_seed_system_roles.py`
- Modify: `backend/apps/iam/tests/test_models.py`

- [ ] **Step 1: 写失败测试 — 验证 7 个常驻角色都存在并带有 base_field_set**

修改 `backend/apps/iam/tests/test_models.py`，在文件末尾追加：

```python
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
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd backend && pytest apps/iam/tests/test_models.py::test_seven_system_roles_seeded -v
```
Expected: FAIL（`Role` 没有 `base_field_set` 字段，且 4 个新角色未插入）

- [ ] **Step 3: 创建 `backend/apps/iam/constants.py`**

```python
"""IAM 共享常量：字段集白名单 + 角色基线字段集。

修改这些常量需要同步加迁移（Role.base_field_set 是数据库列）。
"""

# RSU 相关字段：默认对 CENTER_HEAD 不可见，可通过 FieldPermissionGrant 扩展
RSU_FIELD_GROUP = [
    "rsu_grant_amount",
    "rsu_vesting_schedule",
    "rsu_unvested_value",
    "rsu_strike_price",
    "rsu_grant_date",
]

# 现金分配相关字段：CENTER_HEAD 默认可见
CASH_FIELD_GROUP = [
    "base_salary",
    "monthly_salary",
    "annual_bonus_amount",
    "salary_adjustment_amount",
    "salary_adjustment_pct",
    "performance_rating",
    "level_band",
    "position_grade",
]

# 部门负责人字段集 = 现金 + RSU + 部门管理字段
DEPT_HEAD_EXTRA = [
    "rsu_grant_amount",
    "rsu_vesting_schedule",
    "rsu_unvested_value",
    "rsu_strike_price",
    "rsu_grant_date",
    "promotion_category",
    "department_budget_total",
    "department_budget_reserve",
]

# 7 常驻角色基线字段集
ROLE_BASE_FIELD_SETS = {
    "HR_ADMIN": CASH_FIELD_GROUP + DEPT_HEAD_EXTRA + ["audit_log", "all_company_view"],
    "DEPT_HEAD": CASH_FIELD_GROUP + DEPT_HEAD_EXTRA,
    "CENTER_HEAD": list(CASH_FIELD_GROUP),  # 默认不含 RSU
    "GROUP_LEAD": ["base_salary", "performance_rating", "level_band", "position_grade"],
    "EMPLOYEE": ["base_salary", "performance_rating", "annual_bonus_amount"],
    "FINANCE": CASH_FIELD_GROUP + ["payroll_export", "tax_breakdown"],
    "AUDITOR": CASH_FIELD_GROUP + DEPT_HEAD_EXTRA + ["audit_log_full"],
}
```

- [ ] **Step 4: 修改 `backend/apps/iam/models.py` 中的 Role**

把第 29-44 行 Role 类替换为：

```python
class Role(models.Model):
    ROLE_CHOICES = [
        ("HR_ADMIN", "薪酬 HR"),
        ("DEPT_HEAD", "部门负责人"),
        ("CENTER_HEAD", "中心负责人"),
        ("GROUP_LEAD", "组长"),
        ("EMPLOYEE", "员工"),
        ("FINANCE", "财务"),
        ("AUDITOR", "审计员"),
        ("HRBP", "HRBP"),         # 兼容已存在的 fixture/测试
        ("EXEC", "高管"),          # 兼容
        ("SYS_ADMIN", "系统管理员"),  # 兼容
    ]
    code = models.CharField(max_length=32, unique=True, choices=ROLE_CHOICES)
    name = models.CharField(max_length=64)
    base_field_set = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "iam_role"
```

- [ ] **Step 5: 生成 schema 迁移**

```bash
cd backend && python manage.py makemigrations iam --name sprint1_baseline
```
Expected: 生成 `0002_sprint1_baseline.py`，diff 包含 `Role.base_field_set` 字段。

- [ ] **Step 6: 写数据迁移 `0003_seed_system_roles.py`**

```python
from django.db import migrations


SEVEN_ROLES = [
    ("HR_ADMIN", "薪酬 HR"),
    ("DEPT_HEAD", "部门负责人"),
    ("CENTER_HEAD", "中心负责人"),
    ("GROUP_LEAD", "组长"),
    ("EMPLOYEE", "员工"),
    ("FINANCE", "财务"),
    ("AUDITOR", "审计员"),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("iam", "Role")
    from apps.iam.constants import ROLE_BASE_FIELD_SETS

    for code, name in SEVEN_ROLES:
        Role.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "base_field_set": ROLE_BASE_FIELD_SETS[code],
            },
        )


def revert(apps, schema_editor):
    Role = apps.get_model("iam", "Role")
    Role.objects.filter(code__in=[c for c, _ in SEVEN_ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [("iam", "0002_sprint1_baseline")]
    operations = [migrations.RunPython(seed_roles, revert)]
```

- [ ] **Step 7: 跑迁移 + 测试**

```bash
cd backend && python manage.py migrate iam && pytest apps/iam/tests/test_models.py -v
```
Expected: 所有 iam test_models.py 用例 PASS（含 3 个新增）。

- [ ] **Step 8: Commit**

```bash
git add backend/apps/iam/constants.py backend/apps/iam/models.py backend/apps/iam/migrations/0002_sprint1_baseline.py backend/apps/iam/migrations/0003_seed_system_roles.py backend/apps/iam/tests/test_models.py
git commit -m "feat(iam): seed 7 permanent system roles with base_field_set"
```

---

### Task 2: 验证 RSU_FIELD_GROUP 常量被前端可读

> RSU_FIELD_GROUP 已在 Task 1 的 `constants.py` 写入；本任务只加一条断言测试，确保后续改动不会无声漂移。

**Files:**
- Create: `backend/apps/iam/tests/test_constants.py`

- [ ] **Step 1: 写测试**

```python
from apps.iam import constants


def test_rsu_field_group_stable():
    """RSU_FIELD_GROUP is a contract with frontend RSU column hide rule.
    Adding/removing fields requires deliberate review."""
    assert constants.RSU_FIELD_GROUP == [
        "rsu_grant_amount",
        "rsu_vesting_schedule",
        "rsu_unvested_value",
        "rsu_strike_price",
        "rsu_grant_date",
    ]


def test_cash_and_rsu_groups_disjoint():
    """No field can simultaneously be cash + RSU."""
    cash = set(constants.CASH_FIELD_GROUP)
    rsu = set(constants.RSU_FIELD_GROUP)
    assert cash.isdisjoint(rsu)
```

- [ ] **Step 2: 跑测试**

```bash
cd backend && pytest apps/iam/tests/test_constants.py -v
```
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/apps/iam/tests/test_constants.py
git commit -m "test(iam): pin RSU_FIELD_GROUP and cash/rsu disjointness"
```

---

### Task 3: 新增 FieldPermissionGrant 模型

**Files:**
- Modify: `backend/apps/iam/models.py`（追加）
- Modify: `backend/apps/iam/migrations/0002_sprint1_baseline.py`（让此模型在 Task 1 的迁移中已生成；如果 Task 1 已 commit 则在本任务追加 0004 迁移）
- Create: `backend/apps/iam/tests/test_field_permission_grant.py`

> 实操路径：在 Task 1 的 `makemigrations` 步骤之**前**先把 `FieldPermissionGrant` 类也加入 `models.py`，让 `0002_sprint1_baseline.py` 一次性涵盖所有新表。如果 Task 1 已 commit，则本任务生成 `0004_field_permission_grant.py`。下面假设按"一次性合并"路径执行。**回到 Task 1 Step 4 之后、Step 5 之前**先做下面 Step 1。

- [ ] **Step 1: 在 `backend/apps/iam/models.py` 末尾追加 FieldPermissionGrant**

```python
class FieldPermissionGrant(models.Model):
    """部门负责人 → 中心负责人 的字段级权限扩展授予。

    硬约束：grant 只能扩字段，永远不能扩数据范围（grantee 永远只看自己中心）。
    """
    STATUS_CHOICES = [("ACTIVE", "Active"), ("REVOKED", "Revoked")]

    granter = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="grants_issued",
        help_text="部门负责人 user_id",
    )
    grantee = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="grants_received",
        help_text="中心负责人 user_id",
    )
    center = models.ForeignKey(
        OrgUnit, on_delete=models.PROTECT, related_name="field_grants",
        help_text="被授权范围限定为此中心",
    )
    extra_fields = models.JSONField(default=list, help_text="必须是 RSU_FIELD_GROUP 子集")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ACTIVE")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "iam_field_permission_grant"
        constraints = [
            models.UniqueConstraint(
                fields=["grantee", "center"],
                condition=models.Q(status="ACTIVE"),
                name="uniq_active_grant_per_grantee_center",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        from apps.iam.constants import RSU_FIELD_GROUP

        if not isinstance(self.extra_fields, list):
            raise ValidationError({"extra_fields": "must be a list"})
        invalid = set(self.extra_fields) - set(RSU_FIELD_GROUP)
        if invalid:
            raise ValidationError({"extra_fields": f"fields outside RSU whitelist: {invalid}"})
        if self.center.type != "CENTER":
            raise ValidationError({"center": "grant scope must be a CENTER unit"})
```

- [ ] **Step 2: 写失败测试**

`backend/apps/iam/tests/test_field_permission_grant.py`：

```python
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
        extra_fields=["base_salary"],  # not in whitelist
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
```

- [ ] **Step 3: 跑测试验证失败**

```bash
cd backend && pytest apps/iam/tests/test_field_permission_grant.py -v
```
Expected: FAIL with "no such table" 或 "FieldPermissionGrant has no attribute"。

- [ ] **Step 4: 跑迁移（合并到 Task 1 的 0002）后再测**

```bash
cd backend && python manage.py migrate iam
cd backend && pytest apps/iam/tests/test_field_permission_grant.py -v
```
Expected: 5/5 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/apps/iam/models.py backend/apps/iam/migrations/0002_sprint1_baseline.py backend/apps/iam/tests/test_field_permission_grant.py
git commit -m "feat(iam): add FieldPermissionGrant with RSU whitelist + center scope guard"
```

---

### Task 4: 守护测试 — 确认 PermissionDelegation 不存在

> 现状：spec 要求"删除 PermissionDelegation"，但代码里从未建过。本任务加守护测试防未来出现。

**Files:**
- Create: `backend/apps/iam/tests/test_no_permission_delegation.py`

- [ ] **Step 1: 写守护测试**

```python
import importlib
import inspect

from apps.iam import models as iam_models


def test_permission_delegation_class_does_not_exist():
    """spec 2026-05-11 §1.4 删除委托模型；这里防回归。"""
    assert not hasattr(iam_models, "PermissionDelegation"), \
        "PermissionDelegation must NOT be reintroduced; use FieldPermissionGrant instead"


def test_no_db_table_named_iam_permission_delegation():
    """如果有人重新建表，db_table 守护也会失败。"""
    for _, member in inspect.getmembers(iam_models, inspect.isclass):
        meta = getattr(member, "_meta", None)
        if meta is None:
            continue
        assert getattr(meta, "db_table", "") != "iam_permission_delegation"
```

- [ ] **Step 2: 跑测试**

```bash
cd backend && pytest apps/iam/tests/test_no_permission_delegation.py -v
```
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/apps/iam/tests/test_no_permission_delegation.py
git commit -m "test(iam): guard against reintroducing PermissionDelegation model"
```

---

### Task 5: OrgUnitManager + OrgUnit.TYPE_CHOICES 加 EMPLOYEE_LEAF

**Files:**
- Modify: `backend/apps/iam/models.py:46-61`
- Modify: `backend/apps/iam/models.py`（追加 OrgUnitManager 类）
- Modify: `backend/apps/iam/migrations/0002_sprint1_baseline.py`（一次性合并）
- Create: `backend/apps/iam/tests/test_org_unit_manager.py`

- [ ] **Step 1: 修改 OrgUnit.TYPE_CHOICES，追加 EMPLOYEE_LEAF**

替换 `models.py:46-61` 的 `TYPE_CHOICES`：

```python
class OrgUnit(models.Model):
    TYPE_CHOICES = [
        ("COMPANY", "集团"),
        ("SUBSIDIARY", "分公司"),
        ("DEPT", "部门"),
        ("CENTER", "中心"),
        ("TEAM", "组"),
        ("EMPLOYEE_LEAF", "员工节点"),
    ]
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    leader_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="主负责人；兼任与多负责人通过 OrgUnitManager 表达",
    )

    class Meta:
        db_table = "iam_org_unit"
```

- [ ] **Step 2: 在 `models.py` 末尾追加 OrgUnitManager**

```python
class OrgUnitManager(models.Model):
    """组织单元负责人多对多表，支持兼任。

    一个 unit 可有 1 个 is_primary=True + 多个 is_primary=False。
    一个 manager 可同时管多个 unit（兼任）。
    """
    ROLE_IN_UNIT_CHOICES = [
        ("DEPT_HEAD", "部门负责人"),
        ("CENTER_HEAD", "中心负责人"),
        ("GROUP_LEAD", "组长"),
    ]

    org_unit = models.ForeignKey(
        OrgUnit, on_delete=models.CASCADE, related_name="managers"
    )
    manager = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="managed_units"
    )
    role_in_unit = models.CharField(max_length=16, choices=ROLE_IN_UNIT_CHOICES)
    is_primary = models.BooleanField(default=False)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "iam_org_unit_manager"
        constraints = [
            models.UniqueConstraint(
                fields=["org_unit"],
                condition=models.Q(is_primary=True, effective_to__isnull=True),
                name="uniq_active_primary_per_unit",
            ),
        ]
```

- [ ] **Step 3: 写失败测试**

`backend/apps/iam/tests/test_org_unit_manager.py`：

```python
import pytest
from datetime import date
from django.db import IntegrityError
from apps.iam.models import User, OrgUnit, OrgUnitManager


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
```

- [ ] **Step 4: 生成迁移并执行**

```bash
cd backend && python manage.py makemigrations iam --name sprint1_baseline
```

> 如果 Task 1/3 已提交并产生了 `0002_sprint1_baseline.py`，让 makemigrations 自动新建 `0004_orgunitmanager.py` 即可——文件名变了不影响计划。

```bash
cd backend && python manage.py migrate iam
cd backend && pytest apps/iam/tests/test_org_unit_manager.py -v
```
Expected: 5/5 PASS。

- [ ] **Step 5: 顺手补一条 OrgUnit 既有用例**

修改 `backend/apps/iam/tests/test_models.py` 的 `test_org_unit_tree`，在末尾追加：

```python
@pytest.mark.django_db
def test_org_unit_5_levels_with_employee_leaf():
    company = OrgUnit.objects.create(code="HQ", name="集团", type="COMPANY")
    dept = OrgUnit.objects.create(code="D1", name="研发部", type="DEPT", parent=company)
    center = OrgUnit.objects.create(code="C1", name="AI 中心", type="CENTER", parent=dept)
    team = OrgUnit.objects.create(code="T1", name="算法组", type="TEAM", parent=center)
    leaf = OrgUnit.objects.create(code="L1", name="alice", type="EMPLOYEE_LEAF", parent=team)
    assert leaf.parent.parent.parent.parent == company  # 5 级链
```

- [ ] **Step 6: 跑全部 iam 测试确认无回归**

```bash
cd backend && pytest apps/iam/tests/ -v
```
Expected: 全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/apps/iam/models.py backend/apps/iam/migrations/ backend/apps/iam/tests/test_org_unit_manager.py backend/apps/iam/tests/test_models.py
git commit -m "feat(iam): add OrgUnitManager (concurrent posts) + EMPLOYEE_LEAF unit type"
```

---

### Task 6: DataScopedQuerysetMixin 基础版

> Sprint 1 不接 view 层；本 mixin 落到 `scoping.py`，提供"取 user 主管的所有 OrgUnit 子树并集"工具，供 Sprint 2 的查询层调用。

**Files:**
- Create: `backend/apps/iam/scoping.py`
- Create: `backend/apps/iam/tests/test_scoping.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from datetime import date
from apps.iam.models import User, OrgUnit, OrgUnitManager
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
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd backend && pytest apps/iam/tests/test_scoping.py -v
```
Expected: ImportError（`apps.iam.scoping` 不存在）。

- [ ] **Step 3: 实现 `backend/apps/iam/scoping.py`**

```python
"""数据范围解析：取用户主管单元的子树并集。

数据范围硬约束：任何外部 grant 都不能扩这个集合。
"""
from datetime import date as _date
from typing import Iterable, Optional

from django.db.models import Q

from apps.iam.models import OrgUnit, OrgUnitManager, User


def _descendant_ids(root_ids: Iterable[int]) -> set[int]:
    """BFS 收集子树所有 id（含自身）。"""
    collected = set(root_ids)
    frontier = list(root_ids)
    while frontier:
        children = OrgUnit.objects.filter(parent_id__in=frontier).values_list("id", flat=True)
        new = set(children) - collected
        if not new:
            break
        collected.update(new)
        frontier = list(new)
    return collected


def resolve_user_org_scope(user: User, as_of: Optional[_date] = None):
    """返回 user 在 as_of 日期下可见的所有 OrgUnit 的 QuerySet。

    规则：
    - 取 user 在 OrgUnitManager 中所有当前生效的任命（effective_from <= as_of < effective_to or effective_to is null）
    - 对每个任命的 org_unit，展开整个子树
    - 合并去重
    - 数据范围硬约束：任何 grant 都不能扩这个集合
    """
    if as_of is None:
        as_of = _date.today()

    active_assignments = OrgUnitManager.objects.filter(
        manager=user,
        effective_from__lte=as_of,
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gt=as_of)
    )
    root_ids = list(active_assignments.values_list("org_unit_id", flat=True))
    if not root_ids:
        return OrgUnit.objects.none()

    all_ids = _descendant_ids(root_ids)
    return OrgUnit.objects.filter(id__in=all_ids)


class DataScopedQuerysetMixin:
    """供业务 ViewSet 复用：在 get_queryset 中调用 self.scope_to_org(qs, user)。

    子类需指定 `org_unit_field`（外键字段名，默认 'org_unit'）。
    """

    org_unit_field = "org_unit"

    def scope_to_org(self, qs, user):
        if user.is_superuser:
            return qs
        scope = resolve_user_org_scope(user)
        return qs.filter(**{f"{self.org_unit_field}__in": scope})
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && pytest apps/iam/tests/test_scoping.py -v
```
Expected: 4/4 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/apps/iam/scoping.py backend/apps/iam/tests/test_scoping.py
git commit -m "feat(iam): add resolve_user_org_scope + DataScopedQuerysetMixin"
```

---

### Task 7: MfaChallenge 模型

**Files:**
- Modify: `backend/apps/iam/models.py`（追加）
- Modify: `backend/apps/iam/migrations/0002_sprint1_baseline.py`（合并）
- Create: `backend/apps/iam/tests/test_mfa_challenge.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from datetime import timedelta
from django.utils import timezone
from apps.iam.models import User, MfaChallenge


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="mfa@x.com", employee_no="MFA1", password="x", mfa_enabled=True,
    )


@pytest.mark.django_db
def test_create_pending_challenge(user):
    c = MfaChallenge.objects.create(
        user=user, purpose="LOGIN",
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    assert c.status == "PENDING"


@pytest.mark.django_db
def test_is_expired_helper(user):
    past = MfaChallenge.objects.create(
        user=user, purpose="LOGIN",
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    future = MfaChallenge.objects.create(
        user=user, purpose="LOGIN",
        expires_at=timezone.now() + timedelta(minutes=1),
    )
    assert past.is_expired is True
    assert future.is_expired is False


@pytest.mark.django_db
def test_purpose_choices(user):
    valid = ["LOGIN", "EXPORT", "FINAL_APPROVE", "ROLE_ASSIGN"]
    for p in valid:
        MfaChallenge.objects.create(
            user=user, purpose=p,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
    assert MfaChallenge.objects.count() == len(valid)
```

- [ ] **Step 2: 在 `backend/apps/iam/models.py` 末尾追加**

```python
class MfaChallenge(models.Model):
    PURPOSE_CHOICES = [
        ("LOGIN", "登录"),
        ("EXPORT", "导出敏感数据"),
        ("FINAL_APPROVE", "终审审批"),
        ("ROLE_ASSIGN", "角色变更"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "待验证"),
        ("VERIFIED", "已通过"),
        ("FAILED", "失败"),
        ("EXPIRED", "已过期"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_challenges")
    purpose = models.CharField(max_length=16, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=128, blank=True, help_text="TOTP 不存明文")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "iam_mfa_challenge"
        indexes = [models.Index(fields=["user", "status"])]

    @property
    def is_expired(self) -> bool:
        from django.utils import timezone
        return timezone.now() >= self.expires_at
```

- [ ] **Step 3: 跑迁移 + 测试**

```bash
cd backend && python manage.py makemigrations iam
cd backend && python manage.py migrate iam
cd backend && pytest apps/iam/tests/test_mfa_challenge.py -v
```
Expected: 3/3 PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/apps/iam/models.py backend/apps/iam/migrations/ backend/apps/iam/tests/test_mfa_challenge.py
git commit -m "feat(iam): add MfaChallenge model with PENDING/VERIFIED/FAILED/EXPIRED states"
```

---

### Task 8: SessionRevocation 模型（JWT 黑名单）

**Files:**
- Modify: `backend/apps/iam/models.py`（追加）
- Modify: `backend/apps/iam/migrations/0002_sprint1_baseline.py`（合并）
- Create: `backend/apps/iam/tests/test_session_revocation.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from datetime import timedelta
from django.utils import timezone
from apps.iam.models import User, SessionRevocation


@pytest.mark.django_db
def test_revoke_jti_blocks_token():
    u = User.objects.create_user(email="r@x.com", employee_no="R1", password="x")
    SessionRevocation.objects.create(
        user=u, jti="abc-123",
        expires_at=timezone.now() + timedelta(hours=1),
        reason="LOGOUT",
    )
    assert SessionRevocation.is_revoked("abc-123") is True
    assert SessionRevocation.is_revoked("other-jti") is False


@pytest.mark.django_db
def test_expired_revocation_does_not_block():
    """JWT 自然过期后，revocation 记录应可被 GC 视为已无效。"""
    u = User.objects.create_user(email="r2@x.com", employee_no="R2", password="x")
    SessionRevocation.objects.create(
        user=u, jti="old-jti",
        expires_at=timezone.now() - timedelta(seconds=1),
        reason="LOGOUT",
    )
    assert SessionRevocation.is_revoked("old-jti") is False
```

- [ ] **Step 2: 在 `backend/apps/iam/models.py` 末尾追加**

```python
class SessionRevocation(models.Model):
    """JWT 黑名单：登出 / 强制踢人 / MFA 失败连锁等场景写入。

    业务层在 JWT 校验后查 `is_revoked(jti)`；过了 expires_at 的记录可被定时清理。
    """
    REASON_CHOICES = [
        ("LOGOUT", "用户登出"),
        ("ADMIN_KICK", "管理员强制下线"),
        ("MFA_FAIL", "MFA 连续失败"),
        ("ROLE_CHANGE", "角色变更"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="revocations")
    jti = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    revoked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "iam_session_revocation"

    @classmethod
    def is_revoked(cls, jti: str) -> bool:
        from django.utils import timezone
        return cls.objects.filter(jti=jti, expires_at__gt=timezone.now()).exists()
```

- [ ] **Step 3: 跑迁移 + 测试**

```bash
cd backend && python manage.py makemigrations iam
cd backend && python manage.py migrate iam
cd backend && pytest apps/iam/tests/test_session_revocation.py -v
```
Expected: 2/2 PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/apps/iam/models.py backend/apps/iam/migrations/ backend/apps/iam/tests/test_session_revocation.py
git commit -m "feat(iam): add SessionRevocation JWT blacklist with expiry-aware lookup"
```

---

### Task 9: hr_master 字典：LevelBand + PositionGrade

> 现有 `JobGrade.level/band` 是平面字段，无法承载"层级 → band → 系数"的层级关系。新增两张字典表，与 JobGrade 并存（不破坏既有数据）。

**Files:**
- Modify: `backend/apps/hr_master/models.py`（追加）
- Create: `backend/apps/hr_master/migrations/0002_dictionaries_and_freeze.py`
- Create: `backend/apps/hr_master/tests/test_dictionaries.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from apps.hr_master.models import LevelBand, PositionGrade


@pytest.mark.django_db
def test_level_band_unique_code_and_ordering():
    LevelBand.objects.create(code="P5", name="P5 资深", order=5)
    LevelBand.objects.create(code="P6", name="P6 专家", order=6)
    bands = list(LevelBand.objects.order_by("order").values_list("code", flat=True))
    assert bands == ["P5", "P6"]


@pytest.mark.django_db
def test_level_band_code_unique():
    from django.db.utils import IntegrityError
    LevelBand.objects.create(code="P5", name="P5", order=5)
    with pytest.raises(IntegrityError):
        LevelBand.objects.create(code="P5", name="dup", order=5)


@pytest.mark.django_db
def test_position_grade_links_to_band():
    band = LevelBand.objects.create(code="M1", name="M1 经理", order=10)
    g = PositionGrade.objects.create(
        code="M1-A", name="M1 A 档", level_band=band, order=1,
    )
    assert g.level_band == band
    assert band.position_grades.count() == 1
```

- [ ] **Step 2: 在 `backend/apps/hr_master/models.py` 末尾追加**

```python
class LevelBand(models.Model):
    """职级带（P5、P6、M1、M2 ……）。"""
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=64)
    order = models.IntegerField(help_text="排序权重，小的在前")
    description = models.TextField(blank=True)

    class Meta:
        db_table = "hr_level_band"
        ordering = ["order"]


class PositionGrade(models.Model):
    """职位档（同一职级带内的细分档位）。"""
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    level_band = models.ForeignKey(
        LevelBand, on_delete=models.PROTECT, related_name="position_grades"
    )
    order = models.IntegerField(default=0)
    suggested_min_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    suggested_max_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "hr_position_grade"
        ordering = ["level_band__order", "order"]
```

- [ ] **Step 3: 生成迁移并跑测试**

```bash
cd backend && python manage.py makemigrations hr_master --name dictionaries_and_freeze
cd backend && python manage.py migrate hr_master
cd backend && pytest apps/hr_master/tests/test_dictionaries.py -v
```
Expected: 3/3 PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/apps/hr_master/models.py backend/apps/hr_master/migrations/0002_dictionaries_and_freeze.py backend/apps/hr_master/tests/test_dictionaries.py
git commit -m "feat(hr_master): add LevelBand and PositionGrade dictionaries"
```

---

### Task 10: hr_master · EmployeeFreeze

**Files:**
- Modify: `backend/apps/hr_master/models.py`（追加）
- Modify: `backend/apps/hr_master/migrations/0002_dictionaries_and_freeze.py`（合并；如果已 commit 则建 0003）
- Create: `backend/apps/hr_master/tests/test_employee_freeze.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from datetime import date
from apps.iam.models import OrgUnit
from apps.hr_master.models import Employee, EmployeeFreeze


@pytest.fixture
def emp(db):
    org = OrgUnit.objects.create(code="C1", name="AI 中心", type="CENTER")
    return Employee.objects.create(
        employee_no="E100", name_cn="alice", org_unit=org, hire_date=date(2026, 4, 1),
    )


@pytest.mark.django_db
def test_freeze_active_blocks_proposal(emp):
    f = EmployeeFreeze.objects.create(
        employee=emp, reason="PROBATION",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 7, 1),
        notes="试用期",
    )
    assert f.is_active(as_of=date(2026, 5, 11)) is True
    assert f.is_active(as_of=date(2026, 7, 2)) is False


@pytest.mark.django_db
def test_freeze_open_ended(emp):
    f = EmployeeFreeze.objects.create(
        employee=emp, reason="LEAVING",
        start_date=date(2026, 5, 1),
        end_date=None,
        notes="离职流转",
    )
    assert f.is_active(as_of=date(2026, 12, 31)) is True


@pytest.mark.django_db
def test_employee_has_active_freeze_helper(emp):
    EmployeeFreeze.objects.create(
        employee=emp, reason="PROBATION",
        start_date=date(2026, 4, 1), end_date=date(2026, 7, 1),
    )
    assert EmployeeFreeze.has_active(emp, as_of=date(2026, 5, 11)) is True
    assert EmployeeFreeze.has_active(emp, as_of=date(2026, 8, 1)) is False
```

- [ ] **Step 2: 在 `backend/apps/hr_master/models.py` 末尾追加**

```python
class EmployeeFreeze(models.Model):
    """员工冻结：试用期 / 离职流转期 / 法务调查等情况下不可参与调薪/年终奖。"""
    REASON_CHOICES = [
        ("PROBATION", "试用期"),
        ("LEAVING", "离职流转"),
        ("LEGAL_HOLD", "法务调查"),
        ("LONG_LEAVE", "长期休假"),
        ("OTHER", "其他"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="freezes"
    )
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="null 表示开口")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_employee_freeze"
        indexes = [models.Index(fields=["employee", "start_date"])]

    def is_active(self, as_of=None) -> bool:
        from datetime import date as _date
        if as_of is None:
            as_of = _date.today()
        if as_of < self.start_date:
            return False
        if self.end_date is not None and as_of > self.end_date:
            return False
        return True

    @classmethod
    def has_active(cls, employee, as_of=None) -> bool:
        return any(f.is_active(as_of) for f in cls.objects.filter(employee=employee))
```

- [ ] **Step 3: 生成迁移并跑测试**

```bash
cd backend && python manage.py makemigrations hr_master
cd backend && python manage.py migrate hr_master
cd backend && pytest apps/hr_master/tests/test_employee_freeze.py -v
```
Expected: 3/3 PASS。

- [ ] **Step 4: 跑全量回归**

```bash
cd backend && pytest -v
```
Expected: 27 个原测试 + 本 Sprint 1 新增（约 25 条）全部 PASS，无回归。

- [ ] **Step 5: Commit**

```bash
git add backend/apps/hr_master/models.py backend/apps/hr_master/migrations/ backend/apps/hr_master/tests/test_employee_freeze.py
git commit -m "feat(hr_master): add EmployeeFreeze model for probation/leaving holds"
```

---

## 3. Sprint 1 验收标准

完成全部 Task 后，应满足：

1. **新模型清单**：iam 加 5 张表（FieldPermissionGrant, OrgUnitManager, MfaChallenge, SessionRevocation；Role 加列），hr_master 加 3 张表（LevelBand, PositionGrade, EmployeeFreeze）。
2. **常驻角色**：`Role.objects.filter(code__in=[...]).count() == 7`，每行 `base_field_set` 非空。
3. **数据范围工具**：`resolve_user_org_scope(user)` 在测试集 4 用例下行为正确。
4. **回归**：原 27 测试 + 新增约 25 测试全部绿。
5. **守护**：`test_no_permission_delegation.py` 防回归。
6. **零破坏**：未删/改 既有列；`migrate` 在已存在数据库上幂等可跑。

---

## 4. 风险点与降险措施

| 风险 | 描述 | 降险 |
|------|------|------|
| 迁移合并冲突 | Task 1/3/5/7/8 都改 iam/models.py，多个 makemigrations 顺序运行可能产生 0002/0003/0004 多文件 | 接受多迁移文件；只要顺序对，效果等价 |
| 0002 迁移与 compensation_plan/0003 顺序 | 当前未提交的 compensation_plan/0003_add_department_dimension.py 与本 Sprint 无依赖 | Sprint 1 先 commit 现有 compensation_plan/0003，再开 Sprint 1，避免迁移图错乱 |
| 数据迁移失败回滚 | seed_roles 失败可能留半更新 | 已写 reverse `revert()`，迁移本身在事务内 |
| Role.code choices 与既有数据冲突 | 数据库中已有 HRBP/EXEC/SYS_ADMIN 行 | choices 列表保留兼容项，不删 |

---

## 5. 启动前必做

- [ ] **先把 `compensation_plan/0003_add_department_dimension.py` + `models.py` 改动 commit 掉**（决策 1 已在代码中、未提交）。本 Sprint 1 的迁移图依赖 compensation_plan 已稳定。
- [ ] 确认本地 PostgreSQL + Redis 已起来：`docker compose ps`。
- [ ] `cd backend && pytest -v` 跑一遍现有 27 测试，确认基线全绿。

---

## 6. Self-Review 备注

- **Spec coverage**：决策 4（FieldPermissionGrant + CENTER_HEAD）→ Task 1+2+3；决策 5（5 级树 + 兼任）→ Task 5；漏项 1/3/7/8/14/17 → Task 5/6/7/8/9/10；audit 关联 field_grant_id 推迟到 Sprint 3 已显式标注。
- **占位符扫描**：无 TBD/TODO；所有"实现"步都给出完整代码块。
- **类型一致性**：`FieldPermissionGrant.center` 在 Task 3 与 Task 6 的 `resolve_user_org_scope` 都基于 OrgUnit，类型一致；`OrgUnitManager.role_in_unit` 的枚举与 Role.ROLE_CHOICES 对齐（DEPT_HEAD/CENTER_HEAD/GROUP_LEAD）。
