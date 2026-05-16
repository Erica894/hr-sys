# 分析模块 (6 维) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付分析模块 v1，支撑 HR/管理者按 6 项已锁定口径查看薪酬分布、年度对比、涨幅分桶 — 硬截止 2026-06-10。

**Architecture:**
- 新增 `analytics` app（只读分析层），独立于业务流转;不污染 `compensation_plan`/`lti`/`bonus_pool` 写路径。
- 引入 `EmployeeCompensationSnapshot` 年度快照表（员工 × 年 → 5 列总包值），由"周期执行"事件触发写入 Y/Y+1;**历史年 Y-1 通过 import 命令一次性落库**(不导 Y-2)。
- 5 列口径 = 年固薪 / 年奖金 / 年现金(=固+奖) / RSU 当年归属价值 / 年总包(=现金+RSU);Δ% 在每列上独立计算;**全部统一折 CNY**。
- 数据范围严格走 `iam.DataScopedQuerysetMixin`:DEPT_HEAD 仅本部门,跨部门完全脱敏(决策 D)。
- RSU 估值复用 `lti.StockPriceMonthly`(已有 `closing_price` + `locked_at` + HR 编辑入口);v1 把"3 月月均价"显式作为 month=`{vest_year}-03`,允许 HR 覆盖。
- **多币种汇率**:新增 `analytics.FxRateMonthly(quote_currency, target_currency, month, rate)` 单表两用 — 本地货币→CNY 折现金,USD→CNY 折 RSU;HR 月度维护,缺月报错不静默用上月。
- **多国月薪制**:`hr_master.LegalEntity.fixed_pay_months_per_year`(默认 12,香港 13,西班牙 14 等)+ `Employee.pay_months_per_year_override`(个别合同覆盖)。法定 13/14 月计入年固薪,绩效奖单算。
- **奖金列**:v1 不建 `BonusProposal` 模型;`import_historical_snapshots` 同时承担 Y-1 历史 + Y 当年实发奖金的 Excel 导入(Y+1 该列展示 "—",不预测奖金)。
- 市场分位(P50/P75/P90)v1 砍列,但保留 `MarketSalaryReference` 占位模型 + HR Excel 上传通道,v1.5 再开放展示。

**Tech Stack:** Django 5 + DRF + PostgreSQL 16(物化视图候选) + Vue 3 + Element Plus + ECharts(`vue-echarts`)。

---

## 已锁定口径(2026-05-16)

| # | 维度 | 决策 |
|---|------|------|
| 1 | 涨幅 Δ% 分母 | **5 列并列**:年固薪/年奖金/年现金/RSU 当年归属价值/年总包 |
| 2 | RSU 折算 | **归属当年 3 月月均股价**;HR 可手工覆盖(复用 `StockPriceMonthly.closing_price`) |
| 3 | 市场分位 | v1 砍列,模型 + 上传通道留位,HR 手工维护 |
| 4 | DEPT_HEAD 跨部门脱敏 | **D — 仅本部门可见**,跨部门完全脱敏(后端层 queryset 截断) |
| 5 | 历年对比窗口 | **Y-1 / Y / Y+1**(回顾 + 当期 + 预测);Y+1 来自当前 `RewardCycle` 已批准的 proposal/grant |
| 6 | 涨幅分桶 | **与 `AdjustmentMatrixCell` tier 对齐**:按 (category × perf_grade × pay_band) 的 coef 区间 + 实际 Δ% 落桶 |

---

## File Structure

### Backend(全部新建于 `backend/apps/analytics/`)

| 文件 | 责任 |
|------|------|
| `apps.py` | Django app 注册 |
| `models.py` | `EmployeeCompensationSnapshot`、`MarketSalaryReference`(占位)、`FxRateMonthly` |
| `migrations/0001_initial.py` | 初始迁移 |
| `services/snapshot_builder.py` | 从 `CompensationRecord` + `AdjustmentProposal` + `LTIGrant` 派生年度快照 |
| `services/rsu_valuation.py` | `value_rsu_for_year(grant, year)` — 当年归属股数 × 3 月股价 × USD→CNY 汇率 |
| `services/fx.py` | `convert(amount, quote_ccy, target_ccy, month)` — 查 `FxRateMonthly`,缺月抛 `MissingFxRate` |
| `services/delta.py` | `compute_5col_delta(emp_id, year_from, year_to)` — 返回 5 列 Δ% |
| `services/bucketing.py` | `bucket_by_matrix_tier(employee, delta_pct, cycle)` — 落桶 |
| `services/year_window.py` | `resolve_window(cycle)` → (Y-1, Y, Y+1) 年标签 |
| `views.py` | DRF 视图:`/api/analytics/overview/`、`/by-dept/`、`/distribution/`、`/employee/{id}/timeline/` |
| `serializers.py` | 输出序列化器 |
| `urls.py` | 路由 |
| `permissions.py` | `AnalyticsScopedPermission` — 复用 `DataScopedQuerysetMixin`,DEPT_HEAD 截断为 `manager_scope` |
| `management/commands/import_historical_snapshots.py` | Excel 导入 Y-1 历史 + Y 当年实发奖金数据 |
| `management/commands/import_fx_rates.py` | Excel 导入月度汇率(quote/target/month/rate) |
| `management/commands/build_current_snapshot.py` | 从当前 cycle 派生 Y 快照 |
| `tests/test_snapshot_builder.py` | 单测 |
| `tests/test_delta.py` | 单测 |
| `tests/test_bucketing.py` | 单测 |
| `tests/test_views_scope.py` | DEPT_HEAD 跨部门脱敏测试 |
| `tests/test_e2e_analytics.py` | e2e |

### 修改

| 文件 | 修改 |
|------|------|
| `backend/config/urls.py` | 挂 `path("api/analytics/", include("apps.analytics.urls"))` |
| `backend/config/settings/base.py` | `INSTALLED_APPS += ["apps.analytics"]` |
| `backend/apps/reward_cycle/views.py`(execute action) | 执行后调用 `build_current_snapshot` |
| `backend/apps/lti/admin_urls.py` 或新增 `views.py` 中股价编辑视图(若已存在则跳过) | 暴露 `StockPriceMonthly` 的 HR 编辑接口 |
| `backend/apps/hr_master/models.py` + 迁移 | `LegalEntity.fixed_pay_months_per_year` Decimal(4,2) default 12;`Employee.pay_months_per_year_override` Decimal(4,2) null=True |

### Frontend admin(新建于 `frontend/admin/src/views/analytics/`)

| 文件 | 责任 |
|------|------|
| `AnalyticsOverview.vue` | 入口:5 列总览 + 年份切换 Y-1/Y/Y+1 |
| `AnalyticsByDept.vue` | 部门维度对比(SYS_ADMIN/HR_ADMIN 全可见;DEPT_HEAD 仅本部门) |
| `AnalyticsDistribution.vue` | 涨幅分桶直方图(按 matrix tier) |
| `EmployeeTimeline.vue` | 单员工 3 年纵向卡片(钻取入口) |
| `StockPriceManager.vue` | HR 编辑 `StockPriceMonthly`(月度收盘价) |
| `FxRateManager.vue` | HR 月度维护 `FxRateMonthly`(quote × target 矩阵) |
| `MarketSalaryUpload.vue` | HR 上传市场分位 Excel(占位,v1 不展示数据) |
| `src/api/analytics.ts` | axios 封装 |
| `src/router/index.ts`(修改) | `/analytics`、`/analytics/dept`、`/analytics/distribution`、`/analytics/employee/:id` |

---

## 数据模型

### `EmployeeCompensationSnapshot`(新)

```python
class EmployeeCompensationSnapshot(models.Model):
    employee = models.ForeignKey("hr_master.Employee", on_delete=models.CASCADE,
                                 related_name="comp_snapshots")
    year = models.IntegerField()  # 自然年
    snapshot_kind = models.CharField(
        max_length=16,
        choices=[("ACTUAL", "已实发"), ("PROJECTED", "Y+1 预测")],
    )
    # 5 列口径(均 CNY)
    annual_fixed_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_bonus_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_cash_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_rsu_value_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_total_comp_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # 落桶辅助字段
    perf_grade_code = models.CharField(max_length=32, blank=True)
    pay_band = models.CharField(max_length=16, blank=True)  # BELOW_P50 / P50_P75 / ABOVE_P75
    employee_category_1_snapshot = models.CharField(max_length=16, blank=True)
    org_unit_snapshot_id = models.BigIntegerField(null=True)  # 防止部门变动后追溯失真
    # 来源
    source = models.CharField(max_length=16, default="DERIVED")  # DERIVED / IMPORT / MANUAL
    derived_from_cycle = models.ForeignKey("reward_cycle.RewardCycle",
                                           null=True, on_delete=models.SET_NULL)
    locked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_emp_comp_snapshot"
        unique_together = [("employee", "year", "snapshot_kind")]
        indexes = [
            models.Index(fields=["year", "snapshot_kind"]),
            models.Index(fields=["org_unit_snapshot_id", "year"]),
        ]
```

### `MarketSalaryReference`(新,占位)

```python
class MarketSalaryReference(models.Model):
    """v1 不展示,留 HR 上传通道,v1.5 接入分位线展示。"""
    job_level_code = models.CharField(max_length=32)
    region = models.CharField(max_length=64)
    year = models.IntegerField()
    p50_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    p75_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    p90_cny = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    source_note = models.CharField(max_length=200, blank=True)
    uploaded_by_id = models.BigIntegerField(null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_market_salary_ref"
        unique_together = [("job_level_code", "region", "year")]
```

### `FxRateMonthly`(新)

```python
class FxRateMonthly(models.Model):
    """月度汇率,单表两用:本地货币→CNY 折现金;USD→CNY 折 RSU。
    缺月查询抛 MissingFxRate,不静默用上月,避免数据失真。
    """
    quote_currency = models.CharField(max_length=8)   # 源币种 HKD/SGD/EUR/JPY/USD…
    target_currency = models.CharField(max_length=8)  # 目标 CNY 或 USD
    month = models.CharField(max_length=7)            # 2026-03
    rate = models.DecimalField(max_digits=14, decimal_places=6)  # 1 quote = N target
    source = models.CharField(max_length=16, default="MANUAL")
    locked_at = models.DateTimeField(null=True)
    locked_by_id = models.BigIntegerField(null=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_fx_rate_monthly"
        unique_together = [("quote_currency", "target_currency", "month")]
        indexes = [models.Index(fields=["target_currency", "month"])]
```

### `LegalEntity` / `Employee` 新增字段(改既有 hr_master)

```python
# LegalEntity 新增
fixed_pay_months_per_year = models.DecimalField(
    max_digits=4, decimal_places=2, default=12,
    help_text="法定固薪月数:中国大陆 12,香港 13,西班牙/希腊 14",
)

# Employee 新增
pay_months_per_year_override = models.DecimalField(
    max_digits=4, decimal_places=2, null=True, blank=True,
    help_text="个别合同覆盖法人主体默认值;NULL = 走 legal_entity",
)
```

---

## 实施分阶段

> **执行约定**:用户 5/13 锁定 — plan 批准后只 commit-by-commit 推进,不再问选项。每个 Phase 内部按 task 顺序提交。

### Phase A:数据模型 + 历史导入(预计 commit 6-7 个,~4 天)

#### Task A0:`hr_master` 多国月薪制字段迁移

**Files:**
- Modify: `backend/apps/hr_master/models.py`(+ `LegalEntity.fixed_pay_months_per_year`、`Employee.pay_months_per_year_override`)
- Test: `backend/apps/hr_master/tests/test_pay_months.py`

- [ ] Step 1 - 写测试:`employee.effective_pay_months_per_year` 优先 override → 否则 entity → 否则 12
- [ ] Step 2 - 加字段 + 加 `@property effective_pay_months_per_year` + `makemigrations hr_master`
- [ ] Step 3 - `set POSTGRES_HOST=localhost && pytest backend/apps/hr_master/tests/test_pay_months.py -v`
- [ ] Step 4 - commit `feat(hr_master): LegalEntity.fixed_pay_months_per_year + Employee.pay_months_per_year_override`

#### Task A1:新建 `analytics` app + 三模型 + migration

**Files:**
- Create: `backend/apps/analytics/__init__.py`、`apps.py`、`models.py`、`admin.py`(空)、`migrations/__init__.py`
- Modify: `backend/config/settings/base.py`(加 `apps.analytics`)
- Test: `backend/apps/analytics/tests/test_models.py`

- [ ] Step 1 - 写 model 字段唯一约束的失败测试(同 employee+year+kind 应抛 IntegrityError;同 quote+target+month 应抛 IntegrityError)
- [ ] Step 2 - 实现 `EmployeeCompensationSnapshot` + `MarketSalaryReference` + `FxRateMonthly` + `python manage.py makemigrations analytics`
- [ ] Step 3 - `set POSTGRES_HOST=localhost && pytest backend/apps/analytics/tests/test_models.py -v`
- [ ] Step 4 - commit `feat(analytics): Snapshot + MarketSalary + FxRate 三模型`

#### Task A2a:`fx.convert` 服务

**Files:**
- Create: `backend/apps/analytics/services/__init__.py`、`fx.py`
- Test: `backend/apps/analytics/tests/test_fx.py`

```python
class MissingFxRate(Exception):
    pass

def convert(amount: Decimal, quote_ccy: str, target_ccy: str, month: str) -> Decimal:
    """1 quote = N target;quote==target 时返回原值。缺月抛 MissingFxRate。"""
    if quote_ccy == target_ccy:
        return amount
    try:
        rate = FxRateMonthly.objects.get(
            quote_currency=quote_ccy, target_currency=target_ccy, month=month
        ).rate
    except FxRateMonthly.DoesNotExist:
        raise MissingFxRate(f"{quote_ccy}->{target_ccy} {month}")
    return (amount * rate).quantize(Decimal("0.01"))
```

- [ ] Step 1 - 写测试:HKD→CNY @0.92 缺月抛 + 命中正确折算 + quote==target 直通
- [ ] Step 2 - 实现 + commit `feat(analytics): fx.convert 月度汇率服务`

#### Task A2b:`build_current_snapshot` 派生服务

**Files:**
- Create: `backend/apps/analytics/services/snapshot_builder.py`
- Test: `backend/apps/analytics/tests/test_snapshot_builder.py`

派生规则:
- `months = emp.pay_months_per_year_override or emp.legal_entity.fixed_pay_months_per_year or 12`
- `annual_fixed_local = CompensationRecord(effective_date <= year-12-31, version 最新).monthly_salary × months`
- `annual_fixed_cny = fx.convert(annual_fixed_local, emp.pay_currency, "CNY", f"{year}-12")`
- `annual_bonus_cny` = 派生路径下置 0(`source=DERIVED`),由 import 命令补;**注释:Y/Y-1 实发奖金走 import,Y+1 不预测**
- `annual_cash_cny = annual_fixed_cny + annual_bonus_cny`
- `annual_rsu_value_cny = Σ( LTIGrant.pending_shares_by_year[year] × StockPriceMonthly[stock_code, f"{year}-03"].closing_price × fx.convert(1, price.currency, "CNY", f"{year}-03") )`
- `annual_total_comp_cny = annual_cash_cny + annual_rsu_value_cny`
- `perf_grade_code`、`pay_band`、`employee_category_1_snapshot`、`org_unit_snapshot_id` 一并冻结

- [ ] Step 1 - 写 fixture:中国员工(月薪 20k CNY,12 月) + LTIGrant(100 ADS,2026 vest 50) + StockPrice(2026-03=$10 USD) + FxRate(USD→CNY 2026-03=7.2) → 期望 `annual_fixed_cny=240000`、`annual_rsu_value_cny=3600`、`annual_total_comp_cny=243600`
- [ ] Step 2 - 写 fixture:香港员工(月薪 30k HKD,13 月) + FxRate(HKD→CNY 2026-12=0.92) → 期望 `annual_fixed_cny=358800`
- [ ] Step 3 - 实现 `build_snapshot_for_employee(employee, year, snapshot_kind, cycle=None)`
- [ ] Step 4 - 实现 `build_for_cycle(cycle)` 批量循环
- [ ] Step 5 - run 两个测试 → pass
- [ ] Step 6 - commit `feat(analytics): snapshot_builder 派生 5 列年度快照(多币种 + 多月薪制)`

#### Task A3:`build_current_snapshot` management command

**Files:**
- Create: `backend/apps/analytics/management/__init__.py`、`commands/__init__.py`、`commands/build_current_snapshot.py`

```python
class Command(BaseCommand):
    help = "Build EmployeeCompensationSnapshot for a given cycle/year."

    def add_arguments(self, parser):
        parser.add_argument("--cycle-id", type=int, required=True)
        parser.add_argument("--kind", choices=["ACTUAL", "PROJECTED"], default="ACTUAL")

    def handle(self, *, cycle_id, kind, **opts):
        cycle = RewardCycle.objects.get(pk=cycle_id)
        year = cycle.period_year + (1 if kind == "PROJECTED" else 0)
        n = build_for_cycle(cycle, year=year, snapshot_kind=kind)
        self.stdout.write(self.style.SUCCESS(f"built {n} snapshots for {year}/{kind}"))
```

- [ ] Step 1 - 写命令 + 简单 smoke 测试
- [ ] Step 2 - commit `feat(analytics): build_current_snapshot 命令`

#### Task A4:`import_historical_snapshots` Excel 导入(Y-1 历史 + Y 当年实发奖金)

**Files:**
- Create: `backend/apps/analytics/management/commands/import_historical_snapshots.py`

格式:`employee_no, year, annual_fixed_cny, annual_bonus_cny, annual_rsu_value_cny, perf_grade_code, pay_band`(`annual_cash_cny`/`annual_total_comp_cny` 后端算)。
- 用途 1(历史回填):导入 Y-1 全部 5 列,`source=IMPORT`、`snapshot_kind=ACTUAL`、`derived_from_cycle=NULL`
- 用途 2(当年奖金补录):对 Y 已存在的 DERIVED 行**仅更新 `annual_bonus_cny` 列并重算 cash/total**,`source=DERIVED+MANUAL_BONUS`(避免覆盖派生固薪/RSU);其它列空白则跳过

- [ ] Step 1 - 写测试 1:导入 Y-1 两行 → 出现 2 条 ACTUAL snapshot
- [ ] Step 2 - 写测试 2:Y DERIVED 行已存在 → 导入只填 `annual_bonus_cny` 列 → 该行 bonus 被更新、cash/total 重算、固薪/RSU 不变
- [ ] Step 3 - 实现 + 错误行收集 stderr + dry-run 选项
- [ ] Step 4 - run 测试 → pass
- [ ] Step 5 - commit `feat(analytics): import_historical_snapshots 双用途命令`

#### Task A5:`import_fx_rates` Excel 导入

**Files:**
- Create: `backend/apps/analytics/management/commands/import_fx_rates.py`

格式:`quote_currency, target_currency, month, rate, note`。`source=IMPORT`。同 (quote, target, month) 重复 → upsert。

- [ ] Step 1 - 写测试:导入 2 行(USD→CNY 2026-03=7.2、HKD→CNY 2026-12=0.92) → 数据库 2 条
- [ ] Step 2 - 实现 + commit `feat(analytics): import_fx_rates 命令`

---

### Phase B:Δ% 计算 + 落桶 + 年窗(预计 3 个 commit,~1.5 天)

#### Task B1:`year_window.resolve_window(cycle)` → 三元组

- [ ] Step 1 - 测试:cycle.period_year=2026 → 返回 (2025, 2026, 2027)
- [ ] Step 2 - 实现 + commit `feat(analytics): year_window 解析`

#### Task B2:`compute_5col_delta(emp_id, year_from, year_to)`

返回 dict:`{fixed: %, bonus: %, cash: %, rsu: %, total: %}`;分母为 0 时该列返回 None(前端展示 "—")。

- [ ] Step 1 - 测试 5 种边界(全 0 / 部分 0 / 正常 / Y+1 用 PROJECTED)
- [ ] Step 2 - 实现 + commit `feat(analytics): compute_5col_delta`

#### Task B3:`bucket_by_matrix_tier`

**口径**:取员工当期 (category, perf_grade, pay_band) 对应的 `AdjustmentMatrixCell.coef_low / coef_high` × `RegionalAdjustmentRule.base_pct × EmployeeCategoryFactor.factor` 形成 [low, high];根据实际 `total` Δ% 落入 LOW/IN_RANGE/HIGH 三档。

- [ ] Step 1 - 测试:base=5%,factor=1.0,coef [0.8,1.2] → 区间 [4%, 6%];输入 3% → LOW、5% → IN_RANGE、7% → HIGH
- [ ] Step 2 - 实现 + commit `feat(analytics): bucket_by_matrix_tier`

---

### Phase C:API 视图 + 数据范围(预计 4 个 commit,~2 天)

#### Task C1:`AnalyticsScopedPermission` + queryset 截断

复用 `iam.scoping.resolve_user_org_scope`;DEPT_HEAD/CENTER_HEAD 取并集 → snapshot 用 `org_unit_snapshot_id__in` 过滤。SYS_ADMIN/HR_ADMIN 全量。员工自身仅能看 `employee.user == request.user` 的 timeline。

- [ ] Step 1 - 测试:dept_head A 调 list 不含 dept B 数据
- [ ] Step 2 - 实现 mixin + commit

#### Task C2:`/api/analytics/overview/?year=2026` — 5 列均值/中位数 + 头数

#### Task C3:`/api/analytics/by-dept/?year=2026&compare_year=2025` — 部门 × 5 列 + Δ%

#### Task C4:`/api/analytics/distribution/?cycle_id=N` — 桶分布(LOW/IN_RANGE/HIGH × category)

#### Task C5:`/api/analytics/employee/{id}/timeline/` — Y-1/Y/Y+1 三列总包

每个 task 都按"测试 → 实现 → 跑通 → commit"四步走。

---

### Phase D:HR 后台 — 股价 + 汇率 + 市场分位上传(预计 3 个 commit,~1.5 天)

#### Task D1:`StockPriceMonthly` 增删改查暴露(若 admin_urls 已有则跳过)

- [ ] 检查 `backend/apps/lti/admin_urls.py` 是否已有 ViewSet;若无则加一个 `StockPriceMonthlyViewSet(ModelViewSet)`,permission 限 `HR_ADMIN`/`SYS_ADMIN`,`PATCH closing_price` 时自动盖 `locked_at`/`locked_by_id`
- [ ] commit

#### Task D2:`FxRateMonthly` ViewSet

- [ ] `FxRateMonthlyViewSet(ModelViewSet)` 路径 `/api/admin/analytics/fx-rates/`,permission 限 `HR_ADMIN`/`SYS_ADMIN`;PATCH 时盖 `locked_at`/`locked_by_id`
- [ ] 列表过滤参数:`?target_currency=CNY&month=2026-03`
- [ ] commit `feat(analytics): FxRateMonthly admin ViewSet`

#### Task D3:`MarketSalaryReference` Excel 上传(占位)

- [ ] `POST /api/admin/analytics/market-salary/upload/` 接 xlsx,DRY-run 校验;v1 仅入库,**不展示在分析视图**
- [ ] commit

---

### Phase E:Frontend AnalyticsView(预计 5 个 commit,~3 天)

#### Task E1:`src/api/analytics.ts` + 路由 + 顶级菜单项

- [ ] commit

#### Task E2:`AnalyticsOverview.vue` — 5 列大数 + 年份切换 + ECharts 折线(3 年趋势)

- [ ] 依赖 `vue-echarts`;若 package.json 无则 `npm i vue-echarts echarts`
- [ ] commit

#### Task E3:`AnalyticsByDept.vue` — 部门表 + Δ% 高亮

#### Task E4:`AnalyticsDistribution.vue` — 桶直方图(按 category 分组堆叠)

#### Task E5:`EmployeeTimeline.vue` — 钻取页(timeline 卡片)

每个 task 用浏览器手动 smoke,`npm run build` 通过后 commit。

---

### Phase F:HR 后台 UI — 股价 + 市场分位(预计 2 个 commit,~1 天)

#### Task F1:`StockPriceManager.vue` — 月度表格内联编辑

#### Task F2:`MarketSalaryUpload.vue` — 文件上传 + 校验结果展示

---

### Phase G:e2e + 文档 + 验收(预计 2 个 commit,~1 天)

#### Task G1:`tests/e2e/test_analytics_flow.py`

场景:
1. seed 1 cycle + 5 员工 + Y-1 import + StockPrice
2. 走 distribute → submit → approve → execute(已有 e2e)
3. 调 `build_current_snapshot --cycle-id=...`
4. 调 `/api/analytics/overview/?year=2026` → 校验 5 列总和
5. 切换 dept_head 身份 → 校验 by-dept 仅 1 个部门
6. `/distribution/` → 校验三档桶非零

- [ ] Step 1 - 写测试 → fail
- [ ] Step 2 - 修补缺失逻辑 → pass
- [ ] Step 3 - commit `test(analytics): e2e 6 维口径打通`

#### Task G2:`docs/superpowers/specs/2026-05-16-analytics-dimensions.md` — 把 6 项口径 + snapshot 派生公式写成正式 spec

- [ ] commit

---

## 时间表(对齐 2026-06-10 截止)

| Phase | 内容 | 起 | 止 |
|-------|------|----|-----|
| A | 模型 + 历史导入 | 2026-05-17 | 2026-05-19 |
| B | Δ%/桶/年窗 | 2026-05-20 | 2026-05-21 |
| C | API + 数据范围 | 2026-05-22 | 2026-05-25 |
| D | HR 后端接口 | 2026-05-26 | 2026-05-26 |
| E | 前端图表 | 2026-05-27 | 2026-05-30 |
| F | 前端 HR 后台 | 2026-06-01 | 2026-06-02 |
| G | e2e + spec 入库 | 2026-06-03 | 2026-06-04 |
| Buffer | 修缺/性能/UI 微调 | 2026-06-05 | 2026-06-09 |
| **截止** | | | **2026-06-10** |

---

## 风险与未决

1. **`annual_bonus_cny` 当前为 0**:bonus 模型 v1 还没人头 proposal,只有总池。Phase A 先占位,**写明 TODO**;若 6/10 前 BonusProposal 也没建,则前端"年奖金"列展示"未启用,见 v1.5"。**建议确认**:这条妥协可接受吗?
2. **`StockPriceMonthly.closing_price` 单位是 USD,需汇率**:v1 用一个常量 `USD_CNY_RATE` 配置在 `settings.base`(默认 7.2);**若要支持月度汇率**,加个 `FxRateMonthly` 模型 — v1 不做。
3. **物化视图**:`overview/by-dept` 在 ~2000 员工 × 3 年规模下普通查询足够(<200ms);若上线后慢,Phase G buffer 期改 `MATERIALIZED VIEW`。
4. **DEPT_HEAD 多管辖部门**:`ScopeOfCharge` 取并集后过滤,与已有逻辑一致 — 无新增风险。

---

## Self-Review

- [x] 6 项口径 → A1/A2(模型)、B2(Δ%)、B3(桶)、C1(脱敏)、C5(年窗 timeline)逐项有 task 实现
- [x] 无 TBD/TODO 占位步骤(`annual_bonus_cny=0` 是显式妥协,不是占位)
- [x] 类型一致性:`compute_5col_delta` 返回 dict 5 keys,所有调用方一致
- [x] 路径 + 命令明确,可独立执行
