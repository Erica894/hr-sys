# 2026-05-13 — 现金薪酬 + LTI 预算池二级分发

分支：`feature/budget-dept-center-distribution`
计划文件：`C:\Users\yalanyuan\.claude\plans\federated-shimmying-adleman.md`

## 目标

把"公司层 → 部门/中心"两级预算分发能力补齐：

1. HR 在公司层填好总额后，可按 MANUAL / HEADCOUNT / SALARY_TOTAL 三种规则切分到 DEPT 或 CENTER。
2. DEPT_HEAD / CENTER_HEAD 在 AllocationView 调员工 delta 时，超过自己单元的额度直接被服务端拒绝（不仅是公司层）。
3. EXECUTE 后把每个目标 cell 的 allocated / reclaim 固化，留给后续核算与回收报表。
4. LTI 与现金调薪共用同一个分发 / 聚合 service，Bonus 仅留 hook 不实施。

## 用户决策（已拍板）

- Q1 = C：手动 + 规则共存。
- Q2 = 自动回收，不做二次分配。
- 修订点 1：分发目标支持 DEPT 与 CENTER 两个 OrgUnit 类型。
- 修订点 2：LTI / Bonus 走同一套 distributor。Bonus 不在本 sprint 实施。

## Commit 列表（feature/budget-dept-center-distribution，按时间倒序）

| commit | 说明 | 对应任务 |
|---|---|---|
| `276e9f5` | e2e flow：distribute → cap reject → submit → approve → execute → reclaim | T14 |
| `0ec5124` | bonus_pool/models.py 留 distributor 接入 TODO | T13 |
| `cd33cc1` | AllocationView 顶部 "我的额度" 进度条 + BUDGET_EXCEEDED 提示 | T12 |
| `ac9fa4a` | 新建 MyBudgetView（DEPT_HEAD / CENTER_HEAD 自助查额度） | T11 |
| `4dba6cb` | LTI 预算视图：下发对话框 + 目标子表 | T10 |
| `ca3e533` | 调薪预算视图：下发对话框 + 目标子表 | T9 |
| `adf5983` | EXECUTE 末尾固化 allocated_amount_cny / reclaimed_amount_cny / shares_used_ads / reclaimed_shares_ads | T8 |
| `ca39a27` | LTI granted_ads 写入路径加 cap dry-run，超 400 BUDGET_EXCEEDED | T7 |
| `f42f3bd` | LTI distribute / GET-with-targets / my-lti-budget API | T6 |
| `5bedf6b` | LTIBudgetCell 加 target_org_unit + distribution_rule + reclaimed_shares_ads | T5 |
| `d271539` | SaveProposalsView 加目标层 cap dry-run，未下发回退公司层 | T4 |
| `5c4661d` | AdjustmentBudget distribute / my-adjustment 两条 API | T3 |
| `89e8f9c` | AdjustmentBudgetCell 加 distribution_rule + reclaimed_amount_cny | T2 |
| `833f295` | distributor + aggregator + org_targets 三个 service + 单测 | T1 |

T15（seed 增强 + 本文档）随本次 commit 落地。

## 关键设计决策

### 1. 不改 `AdjustmentBudgetCell.department` 列名

历史列名是 `department`，但本 sprint 后这个 FK 实际上既可指向 DEPT 也可指向 CENTER。改列名要写 alter + 数据迁移；改"语义层"只需要 serializer / FE 别名为 `target_org_unit`。代价低、回退路径清晰，因此保留列名。

### 2. allocated_amount_cny / shares_used_ads 不在保存路径里写

老路径里"已分配"是被 SaveProposalsView 直写的，结果常常和 AdjustmentProposal 实际汇总值漂移。本 sprint 改为：

- 保存路径：`cap_check.py` 用 on-the-fly `aggregate_*` 校验，不落已分配字段。
- 执行路径：`execute.py::_finalize_*` 在 EXECUTE 后一次性把汇总值固化进 cell（仅供报表读取）。

这样 cell 上的"已分配"始终是真值，且不再有"提前回滚 / 中途崩溃 → 字段失真"的隐患。

### 3. 分发目标互不重叠

`org_targets.validate_target_set` 在 distribute API 入口跑一次：任意两节点不能是祖先-后代关系。否则一个员工会被同时算到 DEPT-A 和 DEPT-A 下的 CENTER-A1，双重计数。LTI 同口径。

### 4. 舍入兜底

`compute_distribution._round_dict` 把 quantize 余数加到权重最大的目标上，确保 Σ targets == total（金额按 0.01 / ADS 按 1）。

### 5. Bonus 留 hook

`apps/bonus_pool/models.py` 顶部添了 TODO，写明未来 BonusBudgetCell + BonusProposal 的最小字段集 + 怎么挂 distributor / cap_check / finalize。本 sprint 不动 schema、不动接口。

## 验收

```
cd backend && \
POSTGRES_HOST=localhost POSTGRES_USER=hrsys POSTGRES_PASSWORD=hrsys_dev_pass POSTGRES_DB=hrsys \
.venv/Scripts/python.exe -m pytest -q apps/compensation_plan apps/lti apps/reward_cycle apps/approval
```

最近一次：69 passed。

`seed_phase1` 跑完后 RC-2026-01 的：

- 调薪 ANNUAL/PROMOTION × MANAGEMENT/STAFF 公司池都已按 HEADCOUNT 切到 ENG / PROD。
- LTI MANAGEMENT/STAFF 公司池都已按 HEADCOUNT 切到 ENG / PROD。

登录方式：

- HR Admin：`hr@demo.com / demo1234`
- 部门负责人：`depthead@demo.com / demo1234`
- 员工：`alice/bob/carol/david/eve@demo.com / demo1234`

## 不做（本 sprint 划清的边界）

- 不做 Bonus 全链路（仅留 hook）。
- 不做"预算审批"流程，下发动作直接落库 + audit log。
- 不改 `AdjustmentBudgetCell.department` 列名。
- 不做"reclaim 后再分配" UI。
- 不做 TEAM / SUBSIDIARY 级分发。
