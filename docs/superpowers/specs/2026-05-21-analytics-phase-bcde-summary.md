# Analytics 模块 Phase B/C/E 交付摘要

**日期**: 2026-05-21
**作者**: Claude (HR-sys 架构)
**状态**: 已交付,待 HR 数据样本与 6 项业务口径

## 1. 已完成

### Phase B — 计算服务(纯函数)

| 模块 | 文件 | 作用 |
|---|---|---|
| 年窗解析 | `analytics/services/year_window.py` | `RewardCycle.period`(4 位年)→ `(Y-1, Y, Y+1)` |
| 5 列 Δ% | `analytics/services/delta.py` | 个人 5 列同比变化率,base=0 → None |
| 矩阵桶分 | `analytics/services/bucketing.py` | 按 `base_pct × factor × (coef_low, coef_high)` 区间分 LOW/IN_RANGE/HIGH |

### Phase C — 数据范围 + 4 个只读 API

| 端点 | 方法 | 输出 |
|---|---|---|
| `/api/analytics/overview/?year=Y` | GET | 单年 5 列均值/中位数 + headcount |
| `/api/analytics/by-dept/?year=Y&compare_year=Y'` | GET | 双年部门维度 5 列对比 + Δ% |
| `/api/analytics/distribution/?cycle_id=N` | GET | 周期内 LOW/IN_RANGE/HIGH/UNKNOWN × category 分布 |
| `/api/analytics/employee/<id>/timeline/?cycle_id=N` | GET | 单员工 Y-1/Y/Y+1 三年 5 列 |

**数据范围 (`permissions.scope_snapshot_qs`)**: HR_ADMIN/SYS_ADMIN 全可见;DEPT_HEAD 仅本部门子树(via `OrgUnitManager`);其它角色不可见。

### Phase E — 4 个 Vue 前端页面

`frontend/admin/src/views/analytics/`:
- `AnalyticsOverviewView.vue` — KPI 卡片
- `AnalyticsByDeptView.vue` — 多列嵌套表 + Δ% 着色
- `AnalyticsDistributionView.vue` — 类别 × 桶矩阵
- `EmployeeTimelineView.vue` — 三年 5 列时间线

API 客户端 `frontend/admin/src/api/analytics.ts`,路由 + HR_ADMIN 菜单"分析"二级。

### Phase G — e2e + 文档

- `backend/tests/e2e/test_analytics_flow.py` 串联 4 API
- 本文档

## 2. 测试覆盖

- 5 个 unit test 文件(year_window / delta / bucketing / views_scope / api_views)
- 1 个 e2e 文件
- 后端测试总数 218 全部通过(Phase B+C+G 共贡献 ~24 个新用例)

## 3. v1 简化项(留坑)

| 简化点 | 现状 | 真版本应做 |
|---|---|---|
| Distribution 的 `base_pct/factor` | 硬编码 5% / 1.0 | 从员工类别 + 矩阵规则推导 |
| 类别匹配 | `(None, perf_grade, pay_band)` 简化 key | 严格按 `(category, perf_grade, pay_band)` |
| 周期/员工 ID 输入 | `el-input-number` 手填 | 下拉选择 |
| 数字格式化 | `¥` + 千分位 | 单位降阶 (¥1.2M) |
| 可视化 | 仅表格 | 引入 echarts |

## 4. 阻塞 / 依赖

### 业务侧(关键路径)
- **6 项业务口径**: 2026-06-10 硬截止,需 HR 拍板分析维度定义
- **Y-1 历史薪酬 Excel 样本**: Phase A 的 `import_historical_snapshots` 导入命令已有,但缺真实样本验证字段映射

### 技术侧(非阻塞,可并行)
- **Phase D**: HR 后端 ViewSets — `StockPriceMonthly` / `FxRateMonthly` / `MarketSalaryReference` 上传 CRUD
- **Phase F**: 对应 HR 上传页(`StockPriceManager.vue` / `MarketSalaryUpload.vue`)

D/F 都依赖 HR Excel 样本结构,样本到位前不动。

## 5. 后续动作

1. 给 HR 发邮件:索取历史薪酬 Excel 样本 + 6 项口径决策清单
2. 样本到位后:Phase D(~20 分钟)+ Phase F(~半天)
3. 6 项口径明确后:重构 `bucketing.py` 让 `base_pct/factor` 走真实规则
