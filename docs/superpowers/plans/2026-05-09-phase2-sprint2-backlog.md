# Phase 2 Sprint 2 — Backlog（2026-05-09 拟稿）

> Sprint 1 收尾时用户反馈管理后台 IA 混乱，按角色重组菜单并补 4 个占位页。本文件记录 Sprint 2 要真正实现的内容。

## 背景

Sprint 1 交付后用户指出：
1. **菜单维度错乱**：Allocation/Approval/Execute（流程侧）与方案设计/预算池（管理侧）混在一栏
2. **中英文混用**
3. **IA 应按角色拆**：
   - HR_ADMIN：方案设计、预算管理（=预算分配）、组织及人员管理、薪酬区间管理、审批
   - DEPT_HEAD：本部门可用预算、薪酬分配、提交审批、分配结果分析

Sprint 1 当日已做的应急：
- 按角色分组菜单，全中文
- 4 个未实现模块上占位页（`OrgManagementView / SalaryBandView / AvailableBudgetView / AllocationAnalysisView`）
- LoginView 按角色跳 landing

## Sprint 2 真实模块

### 1. 预算模型两级分配（最高优先级，阻塞部门 Head 体验）

**业务语言：** 预算总额线下确定 → UI 先把总预算分配到部门 → 部门内按 4 维矩阵（ANNUAL/PROMOTION × MANAGEMENT/STAFF）拆分。

**后端改造：**
- `AdjustmentBudgetCell` 加 `department` ForeignKey（nullable = False for leaf cells，nullable = True 作为公司总层？—— 设计待定）
- 建议新模型 `AdjustmentBudgetAllocation`：`reward_cycle + department + adjustment_type + employee_category_1 → budget_amount_cny`
- 保留 `AdjustmentBudgetCell` 作为公司总预算（用 Sprint 1 现有 4 格），或迁移到新模型的 department=NULL 特殊行
- 分配校验：各部门预算之和 ≤ 公司总预算（按 4 格分别校验）
- LTI 同理：`LTIBudgetCell` 加 department 维度

**前端改造：**
- 「预算管理」页改为两视图 tab：① 公司总预算（Sprint 1 的 4 格）② 部门分配（树形表 / 下拉选部门 + 4 格矩阵）
- 显示分配到部门之和 / 总预算 的进度条

### 2. 组织及人员管理（HR_ADMIN）
- 部门树 CRUD（可能复用后端 `hr_master.Department` 模型；当前只有 Employee）
- 员工台账：列表 + 详情 + 编辑（字段包含岗位、职级、管理人员类别）
- 岗位/职级映射表维护

### 3. 薪酬区间管理（HR_ADMIN）
- Salary band 模型：`[job_level, position_family, min, mid, max, effective_year]`
- CRUD + 年度基准切换
- Compa-Ratio 计算口径配置

### 4. 本部门可用预算（DEPT_HEAD）
- 依赖 §1 完成后才能做
- 显示：选方案 → 本部门在该方案下的 4 格矩阵（只读） + 已分配 + 剩余 + 使用率
- 支持选 LTI 方案看 2 格矩阵

### 5. 分配结果分析（DEPT_HEAD）
- 调薪分布直方图（按幅度分位）
- RSU 授予分层饼图
- 与预算目标偏差
- 与公司/同级部门对比（需要脱敏逻辑）

### 5b. 员工自查 / ESS（EMPLOYEE，所有人可见）

**业务语言：** 员工登录后查看本人历年的薪酬变化，按周期看月薪 / 年度奖金 / RSU 授予 / 年度薪酬总包（TC），并能按年度看各类激励指标的变化趋势。

**前置数据缺口（Sprint 1 收尾时盘点）：**
- 月薪历史 — `Employee.current_monthly_salary` 仅当前值，需要版本化（建议：新模型 `EmployeeSalaryHistory(employee, effective_date, monthly_salary, source_proposal_id)`，每次调薪生效时插入快照）
- 奖金 — `BonusPlan` Sprint 1 只是占位；需要 `BonusGrant(plan, employee, amount_cny, year)` 实表 + 录入入口
- TC 计算口径 — 一处约定：TC = monthly × 12 + bonus + RSU 授予价值（按授予日单价折 CNY）；落到代码而非散在前端

**后端：**
- 新接口 `GET /api/me/compensation-history/` → 按员工本人聚合
  - 响应：`{employee: {...}, items: [{cycle_code, year, monthly_salary, annual_bonus, rsu_shares, rsu_value_cny, tc_cny}]}`
  - 数据来源：上述三类表 outer join 按 cycle / year 维度
- 权限：`IsAuthenticated`，强制 `request.user.employee_id`，不能传 query 看别人

**前端：**
- 替换占位页 `MyCompensationView.vue` 为正式实现
- 顶部当前月薪 / 当前 TC 大数字概览
- 历年趋势图：ECharts 多系列折线（月薪 / 奖金 / RSU value / TC）
- 历年明细表：每行一个年度

**风险：** 老员工历史数据可能没有 — 需要从导入或种子里补，否则首次上线只能看到从启用之日起的快照。

### 6. Phase 1 页面中文化
- `AllocationView / ApprovalView / ExecuteView` 页面内文案全部中文
- 包括 ElTable 列标题、按钮文字、ElMessage / ElMessageBox 文案

### 7. 审批/执行菜单重归属
- Sprint 1 把「审批 / 执行」放在 HR_ADMIN 下拉下，但部门 Head 也需要提交审批。
- 考虑：DEPT_HEAD 菜单加「我的审批」（自己发起 + 待自己处理），HR_ADMIN 的「审批」是全局视角。

## 非目标
- MFA 流程重做（保持现状）
- 外部 SSO 对接
- 移动端适配

## 风险
- 预算模型加 department 维度是破坏性改动，老数据需要 migration（建议：旧 cells 搬到 department=NULL 或专用"公司总"伪部门）
- 部门树如果嵌套深，"本部门预算"是否含下级部门预算需要和用户确认（当前假设：仅本部门直属，下级部门各自管）

## 验收
- hr@demo.com 和 depthead@demo.com 分别登录，各自看到自己那组菜单，每个菜单项点进去都有可用页面（不再出现"施工中"占位）
- 预算分配闭环：HR_ADMIN 分到部门 → DEPT_HEAD 可见自己的 → DEPT_HEAD 做薪酬分配时扣减 → DEPT_HEAD 的"可用预算"实时反映剩余
