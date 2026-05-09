# Phase 2 Sprint 1 — Admin 广度铺开

> **For agentic workers:** 按顺序执行每条任务的步骤；完成一步勾一个 `- [ ]`。所有 Bash 命令默认 cwd = `C:\Users\yalanyuan\hr-sys\backend`（除非另注）。

**Goal（约 2 周）：** 让 HR_ADMIN 在 admin 前端完成三类"方案设计"的 CRUD + 两类"预算池"的编辑，把 seed 命令从必需路径上拿掉。

**Non-goals：**
- 数据看板（留 Sprint 2）
- BonusPlan 完整工作流 / 年终奖分配页（留 Sprint 2）
- 权限审计报表（留 Sprint 2）

**Tech stack 不变：** Django 5 + DRF + Vue 3 + Element Plus + Pinia + Vite。

---

## 覆盖矩阵

| # | 功能 | 后端 API | 前端 Admin 路由 |
|---|---|---|---|
| 1 | 调薪方案 CRUD | `/api/admin/adjustment-plans/` | `/admin/plans/adjustment` |
| 2 | RSU 方案 CRUD | `/api/admin/lti-plans/` | `/admin/plans/lti` |
| 3 | 调薪预算池编辑 | `/api/admin/reward-cycles/{id}/adjustment-budget/` | `/admin/budgets/adjustment/{cycleId}` |
| 4 | RSU 预算池编辑 | `/api/admin/lti-plans/{id}/budget/` | `/admin/budgets/lti/{planId}` |
| 5 | 奖金池模型 + 占位页 | `/api/admin/bonus-plans/`（只读列表） | `/admin/plans/bonus` |
| 6 | HR_ADMIN 路由守卫 | `IsHRAdmin` permission | router meta + 菜单 |

---

## Task 1: 后端基础 — HR_ADMIN 权限类 + admin URL 前缀

**Files:**
- Create: `backend/apps/iam/permissions.py`
- Modify: `backend/config/urls.py`
- Create: `backend/apps/compensation_plan/admin_urls.py`
- Create: `backend/apps/lti/admin_urls.py`
- Create: `backend/apps/bonus_pool/admin_urls.py`

- [ ] **Step 1：实现 `IsHRAdmin` permission（检查 UserRole.role.code == "HR_ADMIN"，任意 scope）**
- [ ] **Step 2：`config/urls.py` 挂 `path("api/admin/", include([...]))`，汇总三个 admin_urls**
- [ ] **Step 3：三个空 admin_urls.py 占位（router = DefaultRouter()；urlpatterns = router.urls）**
- [ ] **Step 4：测试 — 匿名访问 `/api/admin/adjustment-plans/` 应 401（暂时空 router 会 404，只要不是 500 即可）**

---

## Task 2: AdjustmentPlan CRUD 后端

**Files:**
- Modify: `backend/apps/compensation_plan/serializers.py`（新增 `AdjustmentPlanSerializer`）
- Modify: `backend/apps/compensation_plan/views.py`（新增 `AdjustmentPlanViewSet`）
- Modify: `backend/apps/compensation_plan/admin_urls.py`
- Create: `backend/apps/compensation_plan/tests/test_admin_plans.py`

- [ ] **Step 1：Serializer 覆盖字段 `[id, code, name, period, status, budget_total_cny, scope, formula, rounding_rule, reward_cycle, created_at]`；`created_at` 只读**
- [ ] **Step 2：ViewSet 继承 `ModelViewSet`，permission_classes=[IsAuthenticated, IsHRAdmin]；create 时写 `created_by_id=request.user.id`**
- [ ] **Step 3：router.register("adjustment-plans", AdjustmentPlanViewSet)**
- [ ] **Step 4：单元测试覆盖 list/create/update/delete + 匿名 401 + 非 HR 角色 403**
- [ ] **Step 5：`cd backend && pytest apps/compensation_plan/tests/test_admin_plans.py -q` 全绿**

---

## Task 3: AdjustmentBudgetCell 矩阵编辑 API

**Files:**
- Modify: `backend/apps/compensation_plan/serializers.py`（新增 `AdjustmentBudgetCellSerializer`）
- Modify: `backend/apps/compensation_plan/views.py`（新增 `AdjustmentBudgetView` — GET 列出 4 格，PUT 批量 upsert）
- Modify: `backend/apps/compensation_plan/admin_urls.py`
- Modify: `backend/apps/compensation_plan/tests/test_admin_plans.py`

- [ ] **Step 1：GET `/api/admin/reward-cycles/{cycle_id}/adjustment-budget/` 返回 `{rows: [{adjustment_type, employee_category_1, budget_amount_cny, allocated_amount_cny, remaining_amount_cny}]}`；若不存在 4 格自动 `get_or_create`**
- [ ] **Step 2：PUT 接受 `{rows: [{adjustment_type, employee_category_1, budget_amount_cny}]}`，只更新 budget_amount_cny；allocated_amount_cny 不允许前端改**
- [ ] **Step 3：所有 4 格（ANNUAL×MANAGEMENT / ANNUAL×STAFF / PROMOTION×MANAGEMENT / PROMOTION×STAFF）必须出现在响应中，缺失自动补 0**
- [ ] **Step 4：测试 — seed 一个 cycle 后 GET 返回 4 行；PUT 某格后 remaining 重新计算正确**

---

## Task 4: LTIPlan CRUD + 预算池 API

**Files:**
- Modify: `backend/apps/lti/serializers.py`
- Modify: `backend/apps/lti/views.py`
- Modify: `backend/apps/lti/admin_urls.py`
- Create: `backend/apps/lti/tests/test_admin_plans.py`

- [ ] **Step 1：`LTIPlanSerializer` 覆盖 `[id, code, name, grant_date, total_shares, share_unit, unit_price_at_grant, vesting_schedule, cliff_months, stock_code, plan_doc_url, reward_cycle]`**
- [ ] **Step 2：`LTIPlanViewSet`（ModelViewSet + IsHRAdmin）**
- [ ] **Step 3：`LTIBudgetView` — GET/PUT `/api/admin/lti-plans/{plan_id}/budget/`，2 格（MANAGEMENT / STAFF），字段 `[headcount_quota, shares_quota_ads, headcount_used, shares_used_ads]`，PUT 只改 quota**
- [ ] **Step 4：router.register + extra urlpattern for budget endpoint**
- [ ] **Step 5：测试覆盖 CRUD + 预算 GET/PUT + 权限**

---

## Task 5: BonusPlan 最小模型

**Files:**
- Modify: `backend/apps/bonus_pool/models.py`
- Create: `backend/apps/bonus_pool/migrations/0001_initial.py`（通过 makemigrations 生成）
- Create: `backend/apps/bonus_pool/serializers.py`
- Create: `backend/apps/bonus_pool/views.py`
- Modify: `backend/apps/bonus_pool/admin_urls.py`

- [ ] **Step 1：定义 `BonusPlan` 模型：`[code, name, period, status, budget_total_cny, scope(JSON), formula(JSON), created_at]`，db_table = "bonus_plan"**
- [ ] **Step 2：`cd backend && python manage.py makemigrations bonus_pool && python manage.py migrate`**
- [ ] **Step 3：Serializer + ReadOnlyModelViewSet（本 Sprint 只读即可；占位为未来完整工作流）**
- [ ] **Step 4：router.register("bonus-plans", BonusPlanViewSet)**
- [ ] **Step 5：最小测试 — 匿名 401，HR_ADMIN list 返回 `[]`（空库）**

---

## Task 6: Admin 前端 — 全局路由守卫 + 菜单

**Files:**
- Modify: `frontend/admin/src/router/index.ts`
- Modify: `frontend/admin/src/App.vue`
- Modify: `frontend/admin/src/stores/auth.ts`（暴露 `hasRole("HR_ADMIN")`）

- [ ] **Step 1：login response 现已返回 roles（如未返回，先修后端 `LoginView`：登录成功时附加 `roles: [r.role.code for r in user.roles.all()]`）**
- [ ] **Step 2：`useAuth` store 存 roles，`hasRole(code)` helper**
- [ ] **Step 3：router meta 新增 `requiresAdmin: true`；beforeEach：未登录→/login，已登录但非 HR_ADMIN 访问 admin-only 页→提示+回上一页**
- [ ] **Step 4：`App.vue` 顶栏菜单新增"方案设计" / "预算池"两个下拉，只对 HR_ADMIN 显示**

---

## Task 7: AdjustmentPlan 列表 + 编辑页

**Files:**
- Create: `frontend/admin/src/views/plans/AdjustmentPlanListView.vue`
- Create: `frontend/admin/src/views/plans/AdjustmentPlanEditView.vue`
- Modify: `frontend/admin/src/router/index.ts`

- [ ] **Step 1：列表页 `ElTable` 显示 `code / name / period / status / budget_total_cny / created_at`；顶部"新建"按钮跳编辑页；每行"编辑 / 删除"操作**
- [ ] **Step 2：编辑页 ElForm — code、name、period（yyyy 选择器）、status（DRAFT/ACTIVE/CLOSED 下拉）、budget_total_cny（el-input-number）、rounding_rule 下拉；scope / formula 暂时用 JSON `<el-input type="textarea">`，前端做 JSON.parse 校验**
- [ ] **Step 3：路由 `/admin/plans/adjustment`、`/admin/plans/adjustment/new`、`/admin/plans/adjustment/:id`**
- [ ] **Step 4：delete 用 `ElMessageBox.confirm`**

---

## Task 8: LTIPlan 列表 + 编辑页

**Files:**
- Create: `frontend/admin/src/views/plans/LtiPlanListView.vue`
- Create: `frontend/admin/src/views/plans/LtiPlanEditView.vue`
- Modify: `frontend/admin/src/router/index.ts`

- [ ] **Step 1：列表字段 `code / name / grant_date / total_shares / unit_price_at_grant / stock_code`**
- [ ] **Step 2：编辑页 — 基础字段 + `vesting_schedule` 用 JSON textarea（Sprint 2 再做结构化编辑器）+ `cliff_months` 整数输入**
- [ ] **Step 3：保存时前端校验 vesting_schedule 为合法 JSON 对象**

---

## Task 9: 预算池编辑页（调薪 + RSU 合并进一个"预算池"节点）

**Files:**
- Create: `frontend/admin/src/views/budgets/AdjustmentBudgetView.vue`
- Create: `frontend/admin/src/views/budgets/LtiBudgetView.vue`
- Modify: `frontend/admin/src/router/index.ts`

- [ ] **Step 1：`AdjustmentBudgetView` — 顶部选 RewardCycle（下拉，调 `/api/reward-cycle/`）；下方 4 格矩阵表格：列=类型（年度/晋升），行=员工类别（管理干部/员工），单元格显示 `预算 / 已分配 / 剩余` 并允许编辑预算值**
- [ ] **Step 2：进度条用 `ElProgress` 显示 allocated/budget 百分比**
- [ ] **Step 3：保存按钮一次性 PUT 整个矩阵；成功后刷新**
- [ ] **Step 4：`LtiBudgetView` 类似 — 顶部选 LTIPlan，下方 2 行（管理干部 / 员工），每行 headcount 和 shares 两列**

---

## Task 10: BonusPlan 占位页 + 菜单接线

**Files:**
- Create: `frontend/admin/src/views/plans/BonusPlanListView.vue`
- Modify: `frontend/admin/src/router/index.ts`
- Modify: `frontend/admin/src/App.vue`

- [ ] **Step 1：只读列表页（当前数据会是空）+ 一条提示："年终奖完整工作流在 Sprint 2 交付"**
- [ ] **Step 2：菜单项"方案设计 → 年终奖方案"指向本页**

---

## Task 11: E2E 冒烟 — admin 启动可登录，五个页面可打开

**Files:**
- 无新增；人工验证

- [ ] **Step 1：`cd frontend/admin && npm run build` 零错误（含 vue-tsc）**
- [ ] **Step 2：`cd backend && python manage.py runserver 8000` + `cd frontend/admin && npm run dev`**
- [ ] **Step 3：用 `hr@demo.com` 登录 → 菜单出现"方案设计 / 预算池"**
- [ ] **Step 4：依次打开 5 个新页面（调薪方案列表 / RSU 方案列表 / 调薪预算池 / RSU 预算池 / 奖金方案列表），无红框错误**
- [ ] **Step 5：创建一个调薪方案，刷新页面仍存在；改预算池某格，刷新后数值正确**

---

## Task 12: 后端回归 — 全量 pytest

**Files:** 无

- [ ] **Step 1：`cd backend && pytest -q`，含 Phase 1 E2E 在内全绿**
- [ ] **Step 2：若 Phase 1 E2E 因 urls.py 改动失败，根因修复（而非改测试）**

---

## Task 13: 提交收尾

- [ ] **Step 1：git status 检查无漏文件**
- [ ] **Step 2：分小 commit（建议顺序：权限类 → 调薪后端 → 调薪前端 → RSU 后端 → RSU 前端 → 预算池 → BonusPlan → 菜单）**
- [ ] **Step 3：本文件改为已完成状态或归档**

---

## 风险 & 预留

- **权限模型简单化**：本 Sprint 只区分"HR_ADMIN / 其他"；分管范围（CHARGE scope）到 Sprint 2 真正执行分配时再生效
- **JSON 字段编辑体验差**：scope / formula / vesting_schedule 先用 textarea；Sprint 2 做结构化表单
- **审计日志**：本 Sprint 的 CRUD 操作是否入 audit_log？→ 建议在 Task 2/4/5 的 ViewSet.perform_create/update/destroy 里调 `log_action`，follow Phase 1 的约定
