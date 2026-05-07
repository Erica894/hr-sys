# 薪酬激励分配系统 · 设计文档

- **项目代号**:hr-sys
- **起草日期**:2026-05-07
- **状态**:草案 · 待评审
- **作者**:Claude(协作起草)+ 项目负责人

---

## 1. 概述

### 1.1 背景与目标

为公司搭建一套覆盖**年终奖**、**调薪**、**长期激励(RSU)**三大场景的薪酬激励分配系统,替代当前的 Excel + 邮件审批流程,实现:

- 分配过程结构化、可审计
- 可配置多级审批链自动流转(默认链 + HR 后台可灵活增减节点)
- 管理者在分配页上**实时测算调薪与 RSU 变动对员工 3 年总包的影响**
- 数据权限严格隔离,敏感操作全量留痕
- 支持 2000+ 员工规模,多事业部/多地区/多合同主体

### 1.2 范围

**本系统覆盖**:
- 年终奖方案定义、分层预算、分配、审批、执行、签收
- 调薪方案(**统一调薪 Plan,承载年度调薪 + 晋升调薪 + 个别特殊/保留性调薪**)定义、分配、审批、执行
  - 一个 RewardCycle 对应 1 个 AdjustmentPlan;该 Plan 的每条 Proposal 同时承载**晋升调薪**(固定比例)、**年度调薪**(suggested + manager_delta)与个别特殊情况标记(`is_special_case` + `market_benchmark_note` / `retention_reason`)
  - 预算侧仍按 `{晋升调薪, 年度调薪} × {管理干部, 员工}` 二维 Cell 分别追踪
- 长期激励(RSU)方案定义、授予、vesting 日历、签收
- 调薪与 RSU 合并场景:两种激励因子并列调整,实时总包测算
- 多级可配置审批链 + 两种打回粒度(整批 / 单人)
- HR 二次点击"执行"门控
- 数据权限(全局/**分管范围**/部门/中心/本人)+ 中心负责人授权工作流
  - **分管范围(ScopeOfCharge)**:组织架构无 BU 层,但管理层级有"分管"概念 —— 一个高管可同时分管多个部门/分公司。分管范围是一个由 HR 配置的、按 user 维度可挂多个 OrgUnit 的集合。
- 应用层审计日志(独立 schema)
- Excel 导入 + 外部 HR 系统 API 对接

**晋升决策 vs 晋升调薪**(划清边界):
- **晋升决策**(谁晋升、晋升到什么职级)在外部人才盘点/晋升评审系统完成,本系统**不提供**晋升发起、晋升评审、晋升审批功能
- **晋升结果**以静态字段形式进入员工档案:`job_level_promoted`(晋升后专业职级)+ `position_promoted`(晋升后职务)+ `is_promoted`(是否晋升)+ `promotion_category`(晋升类别),不单独作为流程资源,与其他基础信息字段等同
- **晋升调薪**活动**在本系统内**:与年度调薪 + RSU 在**同一个 RewardCycle** 内**合并分配、合并审批、合并执行**,不存在独立流程
  - `AdjustmentProposal` 同时承载该员工在本周期的 `promotion_*`(固定)+ `annual_*`(suggested + manager_delta)两部分
  - 管理者仅可调整 `annual_manager_delta_pct`;`promotion_adjustment_pct` 由系统按职级变更规则查表给出,不可调
  - 预算侧通过 `AdjustmentBudgetCell.adjustment_type ∈ {PROMOTION, ANNUAL}` 分别追踪盘口
  - 若某员工当期仅参与晋升调薪(不参与年调),则 `annual_*` 字段为 0;仍走同一条 RewardCycle 审批链
  - 场外批次晋升(非标准 RewardCycle 周期)需要处理时,HR 建一个 scope 仅覆盖晋升员工的临时 RewardCycle 即可,仍走 UNIFIED 链

**本系统不包括**(YAGNI):
- 雇主成本(CTC)口径计算
- 完全自由的图形化流程设计器(目前审批采用"默认链 + 条件节点 + HR 后台增删"方式,暂不做任意拓扑)
- 多租户 SaaS 化
- RSU 以外的长激工具(股票期权/虚拟股/递延奖金)
- 字段级加密(靠权限 + 审计保护)
- 销售提成自动计算
- 移动端原生 App

### 1.3 使用主体

- 员工(EMPLOYEE):查看本人数据、签收
- 部门负责人(DEPT_HEAD):下属分配(含年度调薪/晋升调薪/年终奖/RSU)、授权中心、下级审批(晋升决策不在本系统;特殊/保留性个别调薪通过在年度调薪中填 `special_note/retention_reason` 承载)
- 中心负责人(CENTER_HEAD):获授权后参与本中心分配
- HRBP:所辖分管范围(ManagementScope)内的方案配置与审批节点
- HR_ADMIN(薪酬 HR):全局方案、终审、执行、股价锁定
- 高管(EXEC):大额审批、全公司看板
- 系统管理员(SYS_ADMIN):账号/权限/组织/数据对接配置;**严格不可见业务数据**

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│ 员工端 Web (Vue3 + EP)      │     │ 管理后台 Web (Vue3 + EP)      │
│ /portal                     │     │ /admin                        │
│  - 薪酬概览 / RSU            │     │  - HR / 高管 / 系统管理员    │
│  - 经理评估入口              │     │  - 方案配置、审批、报表       │
│  - 部门负责人 / 中心长分配页  │     │                              │
└────────────┬────────────────┘     └──────────────┬───────────────┘
             │              HTTPS / JWT             │
             └──────────────────┬──────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Nginx(反代 + 静态)  │
                    └───────────┬───────────┘
                                │
         ┌──────────────────────▼──────────────────────┐
         │   Django + DRF 应用(Gunicorn)              │
         │   10 个业务模块(模块化单体)                │
         │   统一权限 Mixin / 应用层审计中间件         │
         └────┬─────────────────────┬──────────────────┘
              │                     │
              ▼                     ▼
     ┌────────────────┐    ┌──────────────────┐    ┌──────────────────┐
     │ PostgreSQL     │    │ Redis(缓存/队列) │    │ 对象存储(MinIO /  │
     │ 主库 + 只读副本│    │                  │    │ OSS)             │
     └────────────────┘    └──────────────────┘    └──────────────────┘
                                    │
                           ┌────────▼─────────┐
                           │  Celery Worker   │  批量算薪、导入、vesting
                           │  + Beat(调度)    │  生成、通知、报表预聚合
                           └──────────────────┘

                     ┌──────────────────────────────┐
                     │ 外部 HR 系统(飞书/北森/SAP)  │
                     │  ← data_integration 同步     │
                     └──────────────────────────────┘
```

### 2.2 技术栈

- **后端**:Python 3.12 + Django 5 + Django REST Framework + Celery 5
- **前端**:Vue 3 + Element Plus + Pinia + Vue Router + Vite
- **数据库**:PostgreSQL 16(JSONB、行级锁、窗口函数、只读副本)
- **队列/缓存**:Redis 7
- **对象存储**:S3 兼容(私有化 MinIO / 公有云 OSS,代码零差异)
- **部署**:Docker Compose(私有化)/ K8s + Helm(公有云)双套
- **认证**:JWT + TOTP(MFA)
- **基准币种**:**CNY(人民币)**——所有预算、汇总、跨地区对账以 CNY 为基准;员工明细保留 `local_currency`(当地币种),展示侧按场景切换

### 2.3 模块划分(模块化单体)

10 个 Django app:

1. **iam** — 账号、角色、组织架构、数据权限规则、授权(PermissionDelegation)
2. **hr_master** — 员工档案、职级带宽、薪酬档案、合同主体、地区币种映射、绩效数据
3. **data_integration** — Excel 导入、外部 HR 系统 API 同步
4. **compensation_plan** — 调薪方案(统一 Plan,内含年度调薪 + 晋升调薪 + 个别特殊调薪,全部在 RewardCycle 内合并审批)
5. **bonus_pool** — 年终奖池、分层预算、分配、提交
6. **lti** — RSU 授予、vesting 日历、股价参考与 HR 锁价
7. **reward_cycle** — **奖酬周期容器**:串联 compensation_plan + lti,承载合并分配页与实时测算
8. **approval** — 可配置多级审批链(默认链 + HR 后台灵活增减)+ 条件节点 + 两种打回
9. **audit** — 独立 schema 下的 `audit_log`、`sensitive_view_log`、`export_log`
10. **notification / report** — 站内消息 + 邮件通知、报表预聚合、高管看板

**模块间约束**:不直接跨 app 访问对方 ORM,统一经 `app.services` 暴露的函数接口;方便未来拆分。

### 2.4 关键横切设计

**应用层审计**:
- Django 中间件拦截所有写请求,业务关键动作 `audit.log(event, actor, target, before, after)` 显式埋点
- 写入独立 `audit` schema;应用 DB 账号对该 schema 仅 INSERT,读取由 DBA 账号或 SYS_ADMIN 后台(数值脱敏)完成

**快照与重算**:
- Proposal 提交时冻结 `calculation_basis_snapshot`(base_salary、perf_rating、股价、FX、职级带宽)
- 提供"按最新数据重算"按钮:手动触发后生成新的 TotalComp 快照和建议值,审批人看到最新参考;已完成审批节点不受影响
- 每次重算留 `audit_log`,可 diff

**执行门控**:
- 审批通过后状态为 `APPROVED_PENDING_EXECUTE`
- HR_ADMIN 在"待执行"页面勾选批量 → 二次 MFA 确认 → 写入 CompensationRecord / VestingEvent 激活

**数据明文 + 权限隔离**:
- 不做字段级加密
- DB 层面用 `DataScopedQuerysetMixin` 在 `get_queryset()` 附加 WHERE 过滤,跨范围不可见不是靠前端隐藏
- 敏感字段查看写 `sensitive_view_log`

---

## 3. 数据模型

### 3.1 iam(账号与组织)

- `User`: id, employee_no, email, password, status, mfa_enabled
- `Role`: id, code, name(HR_ADMIN / HRBP / DEPT_HEAD / CENTER_HEAD / EXEC / SYS_ADMIN / EMPLOYEE)
- `UserRole`: user_id, role_id, scope_type(GLOBAL/**CHARGE**/DEPT/CENTER/SELF), scope_ref_id
  - `scope_ref_id` 按 `scope_type` 指向不同表:CHARGE → `ManagementScope.id`;DEPT/CENTER → `OrgUnit.id`
- `OrgUnit`: id, parent_id, code, name, type(COMPANY/**SUBSIDIARY**(分公司)/DEPT/**CENTER**/TEAM), leader_user_id
  - 注:业务侧无 BU 层,组织树结构为 COMPANY → SUBSIDIARY?/DEPT → CENTER → TEAM
- `ManagementScope`(分管范围):id, code, name(如"张三分管范围"), owner_user_id(分管人), description, status(ACTIVE/ARCHIVED)
- `ManagementScopeMember`: scope_id, org_unit_id(部门或分公司,可多条),included_at
  - 分管范围 = 一位高管挂多个 OrgUnit 的集合,支持跨部门/跨分公司
  - HR 在管理后台维护;变更走审计
- `DataPermissionRule`: role_id, resource, scope_expr(JSONB)
- `PermissionDelegation`:
  - id, grantor_user_id, grantor_role, grantee_user_id, grantee_role
  - scope_type(CENTER), scope_org_unit_id
  - `resource_grants`(JSONB) — 见 §5.2
  - valid_from, valid_to, plan_binding(JSONB)
  - status(PENDING/ACTIVE/REVOKED/EXPIRED/SUSPENDED)
  - hrbp_ack_required=true(固定)、approval_instance_id
  - revoked_by, revoked_at

### 3.2 hr_master(员工与薪酬档案)

- `LegalEntity`: id, code, name, country, jurisdiction, default_currency, tax_id, address
- `LocationPayCurrency`: id, country, region, pay_currency, fx_to_base_ccy
- `Employee`:
  - 基础:id, user_id, employee_no, **name_cn**(中文名), **name_en**(英文名)
  - 组织:org_unit_id, manager_id, **dept_name**(冗余缓存:部门), **center_name**(中心), **team_name**(组)
  - 雇佣主体:legal_entity_id, work_location, **pay_country_region**(发薪国家/地区), pay_currency(=local_currency,按地区推导,可覆写)
  - 职级职务:**job_level_current**(当前专业职级), **job_level_promoted**(晋升后专业职级,静态字段), **position_current**(当前职务), **position_promoted**(晋升后职务,静态字段), job_family
  - 激励相关标记:
    - **is_promoted**(是否晋升:true/false)
    - **promotion_category**(晋升类别:如 VERTICAL/LATERAL/NONE)
    - **participates_annual_adjustment**(是否参与年调)
    - **employee_category_1**(人员类别 1,如管理干部 / 员工)
    - **employee_category_2**(人员类别 2,业务定义的第二维度分类)
  - 其它:hire_date, status
  - **字段来源**:`job_level_promoted` / `position_promoted` / `is_promoted` / `promotion_category` 均为**静态字段**,由员工主数据(Excel 导入或外部 HR 系统同步)提供;本系统不做晋升流程,只消费这些字段作为调薪分配的参考与 scope 过滤依据
  - **FX 基准**:`pay_currency` 为该员工的本地币种(`local_currency`);金额字段默认以 `local_currency` 存储和展示,对账/预算汇总以 CNY 为基准
- `JobGrade`: id, level, band, **p50, p75, p90**(月薪分位档位),min_salary, mid_salary, max_salary
- `CompensationRecord`: id, employee_id, effective_date, base_salary, monthly_salary, allowance, currency, source(MANUAL/IMPORT/API), version, superseded_by
- `PerformanceRating`: id, employee_id, period_year, period_half(H1/H2), rating, final_score, annual_rating_snapshot, source, locked_at

### 3.3 data_integration

- `ImportJob`: id, kind(EMPLOYEE/PERF/SALARY/STOCK_PRICE), file_url, status, progress, error_report_url, operator_id, created_at
- `ExternalSyncConfig`: id, source(FEISHU/BEISEN/SAP), endpoint, secret_ref, mapping(JSONB), schedule
- `SyncRun`: id, config_id, started_at, finished_at, stats(JSONB), status

### 3.4 compensation_plan(调薪)

- `AdjustmentPlan`: id, code, name, period, status(DRAFT/IN_PROGRESS/APPROVING/APPROVED_PENDING_EXECUTE/EXECUTED/FROZEN/CLOSED), **budget_total_cny**(CNY 基准), scope(JSONB), formula(JSONB), rounding_rule, created_by, reward_cycle_id(强制,所有 AdjustmentPlan 必须挂在一个 RewardCycle 下)
  - **无 `type` 字段**:一个 RewardCycle 对应 1 个 AdjustmentPlan,同时承载本周期全员的年度调薪 + 晋升调薪 + 个别特殊调薪
  - 对 `is_promoted=true` 员工,系统按职级变更查表填入 `promotion_adjustment_pct`;对参与年调员工按公式填入 `annual_suggested_pct`;两者在同一条 `AdjustmentProposal` 内独立字段承载
  - 预算侧仍按 `AdjustmentBudgetCell.adjustment_type ∈ {ANNUAL, PROMOTION}` 分别追踪

- `AdjustmentBudgetCell`(调薪预算二维分解,CNY 基准):一个 RewardCycle 下同时存在 ANNUAL 与 PROMOTION 两种 type 各自的预算盘
  - id, reward_cycle_id(所属周期), adjustment_type(**ANNUAL / PROMOTION**), employee_category_1(**MANAGEMENT / STAFF**), budget_amount_cny, allocated_amount_cny(实时汇总), remaining_amount_cny(派生 = budget - allocated)
  - 汇总口径:`合计` 行由前端按 `sum(employee_category_1)` 汇总,不落库
  - 预算表头对应:`{晋升调薪, 年度调薪} × {管理干部, 员工, 合计} × {可分配总盘, 已分配, 剩余}`
  - **预算约束(软约束 + HR 把关)**:
    - Cell 级(`adjustment_type × employee_category_1`):仅用于可视化与实时预警,**允许跨 category 混用**(管理干部池与员工池之间可挪用,由管理者自行权衡)
    - 年度调薪:总池约束为 `sum(annual_adjustment_amount_cny) ≤ Cell(ANNUAL, MGMT).budget + Cell(ANNUAL, STAFF).budget`
    - 晋升调薪:同上 sum 上限为 `Cell(PROMOTION, MGMT).budget + Cell(PROMOTION, STAFF).budget`
    - **所有超额均为软约束**:UI 实时高亮超额 Cell/总池 + 提交时弹出确认框"已超预算,是否仍然提交?",**允许带标记提交**,不做阻拦
    - 带标记提交后,审批节点 HR_ADMIN 终审时看到 `over_budget_flag = true` 及超额明细,HR 决定是否放行(最终把关)

- `AdjustmentProposal`:一条 proposal 同时承载该员工在本周期的**晋升调薪 + 年度调薪**两部分(如果同时参与)
  - id, plan_id, employee_id, local_currency, reason, status, proposer_id, approver_chain(JSONB), effective_date, calculation_basis_snapshot(JSONB)
  - 快照字段:
    - `current_salary`(当前月薪,当地币种)
    - `current_job_level_snapshot`
    - `job_level_promoted_snapshot`(快照自 Employee.job_level_promoted)
    - `promoted_level_band_bucket`(<P50 / P50-P75 / P75-P90 / >P90)
    - `participates_annual_snapshot`
  - **晋升调薪部分**(管理者不可调整,完全由系统按规则计算):
    - `promotion_adjustment_pct`(晋升调薪比例,**固定**,基于职级变更的系数查表得出;`is_promoted=false` 时为 0)
    - 无 manager_delta 字段 —— 该项比例不开放管理者调整;如需例外,HR 在管理后台直接修改员工主数据或规则表,不通过调薪分配页
  - **年度调薪部分**:
    - `annual_suggested_pct`(建议比例,系统按公式算出)
    - `annual_manager_delta_pct`(管理者调整增减量)
    - `annual_final_pct`(调整后比例 = suggested + manager_delta)
  - **总调薪派生**:
    - `total_adjustment_pct` = `promotion_adjustment_pct + annual_final_pct`
    - `proposed_salary` = `current_salary × (1 + total_adjustment_pct)`
    - `total_adjustment_amount_local` = `proposed_salary - current_salary`
    - `total_adjustment_amount_cny`(按当期 FX 换算,用于预算对账)
  - **按预算类别拆分的年化加薪成本**(用于 `AdjustmentBudgetCell` 汇总):
    - `promotion_adjustment_amount_cny` = `current_salary × promotion_adjustment_pct × 12 × fx_to_cny`
    - `annual_adjustment_amount_cny` = `current_salary × annual_final_pct × 12 × fx_to_cny`
    - `employee_category_1_snapshot`(快照自 Employee,避免后续人员类别变更导致预算对不上)

- `AdjustmentProposal` 附加可选字段(承载原"特别调薪"语义,不再单列模型):
  - `market_benchmark_note`(JSONB,可填外部对标数据、保留原因)
  - `retention_reason`(TEXT,保留性调薪说明)
  - `is_special_case`(布尔,标识该条年度调薪是否作为个别特殊处理,用于报表筛选与审批加签条件)
  - 条件审批:当 `is_special_case=true` 或 `annual_final_pct > threshold` 时,走额外审批节点

### 3.5 bonus_pool(年终奖)

- `BonusPlan`: id, period(如 2025FY), **company_pool_amount_cny**(CNY 基准), status, formula_config(JSONB), created_by
  - **`enabled_subtypes`**(JSONB 列表,默认 `["SERVICE", "PERF_BASE", "PERF_FLEX"]`):控制本方案启用哪些子类别池
    - 语义:业务决定是否设立某个池;UI 根据此配置**动态增删列**,后端对未启用 subtype 不生成 `BonusSubtypeBudget` 行、`BonusProposal` 对应字段为 `NULL`
    - 弹性奖金(PERF_FLEX)可能随年度业绩决定启停(如公司未超额完成 → 本年度无弹性池);启停无需 schema 变更,只改配置
    - 未来新增子类别 → 新增枚举值 + 配置 + 前端列渲染,不动原有字段

- `BonusSubtypeBudget`(子类别预算盘,CNY 基准,全公司口径)— 对应年终奖预算表头"类别/子类别/可分配总盘/已分配/机动盘":
  - id, plan_id, bonus_subtype(**SERVICE / PERF_BASE / PERF_FLEX / 可扩展**),仅对 `BonusPlan.enabled_subtypes` 中的值建行
  - `budget_amount_cny`(可分配总盘)
  - `allocated_amount_cny`(已分配,实时汇总自 BonusProposal 对应字段,本 subtype 全员 `final` 合计)
  - `reserve_amount_cny`(**机动盘,HR/管理者可调节盘**,每个 subtype 各自都有;允许非负)
  - **业务语义**(HR 配置时的心智):
    - SERVICE(年度服务奖):基于员工在职年限,规则固定,通常机动盘较小
    - PERF_BASE(基准奖金):公司业绩**基本达成预期**带来的奖金池,员工基于绩效系数分配
    - PERF_FLEX(弹性奖金):公司业绩**超额完成**带来的**增量**奖金池;未超额时该池可不启用
    - 两个绩效池**各自独立**维护 `可分配总盘 + 机动盘`,互不串用
  - **子类别小计**由前端派生:`年度绩效奖小计 = 启用中的 PERF_* 子类别逐列相加`(弹性未启用时小计 = 基准)
  - **约束**:`allocated_amount_cny + reserve_amount_cny ≤ budget_amount_cny`(机动盘不得吃掉已分配)

- `BonusBudget`(分层预算,部门/中心口径,用于下发到各级负责人可见额度): id, plan_id, org_unit_id, **budget_amount_cny**, **allocated_amount_cny**(实时汇总), lock_at_depth
  - 注:`BonusBudget` 是组织层级的下发额度,`BonusSubtypeBudget` 是子类别维度的盘口,两者正交;同一笔 Proposal 同时对两边计提。

- `BonusProposal`:一条 proposal 同时承载**所有启用子类别**的奖金分配
  - id, plan_id, employee_id, local_currency, status, proposer_id, approver_chain(JSONB), calculation_basis_snapshot(JSONB)
  - 基础计算快照:
    - `bonus_base`(奖金基数,通常为月薪或特定基准)
    - `tenure_factor`(在职时间系数)
    - `perf_factor`(个人绩效系数,来自绩效)
    - `perf_bonus_months`(绩效奖金月份数)
  - **每个启用的子类别都有独立的三元组字段**(未启用时为 `NULL`):
    - **年度服务奖(SERVICE)**:
      - `service_award_amount_local`(系统按在职年限计算,通常不开放管理者调整)
      - `service_award_amount_cny`(派生)
    - **基准奖金(PERF_BASE)**:
      - `perf_base_suggested_local`(建议分配额,按公式算出)
      - `perf_base_manager_adjust_local`(管理者从 PERF_BASE **机动盘**内调整,可正可负)
      - `perf_base_final_local` = suggested + manager_adjust(派生)
      - `perf_base_final_cny`(派生)
    - **弹性奖金(PERF_FLEX,可启停)**:
      - `perf_flex_suggested_local`(建议分配额,基于超额业绩系数,仅启用时有值)
      - `perf_flex_manager_adjust_local`(管理者从 PERF_FLEX **机动盘**内调整)
      - `perf_flex_final_local`(派生)
      - `perf_flex_final_cny`(派生)
  - **年度绩效奖合计**(UI 列"调整后金额"):
    - `performance_bonus_final_local` = `coalesce(perf_base_final_local, 0) + coalesce(perf_flex_final_local, 0)`
  - **奖金合计**:
    - `total_bonus_local` = `service_award + performance_bonus_final`
    - `total_bonus_cny`(派生)
  - **说明**:`note`(文字说明)

- **预算约束(软约束 + HR 把关)**:
  - 组织层:`sum(total_bonus_cny) in 部门 ≤ BonusBudget.budget_amount_cny`(软)
  - 子类别层(全公司,逐个启用的 subtype):`allocated_amount_cny ≤ budget_amount_cny - reserve_amount_cny`(软)
  - 机动盘独立:`PERF_BASE` 机动盘与 `PERF_FLEX` 机动盘**互不相通**(这是业务语义,而非超额强度问题 —— 两池的公司业绩来源不同,不可混用);该规则仍建议在 UI 上明确区分,若管理者调整使某 subtype 超出 `budget + reserve` 累计也允许提交,HR 终审把关
  - 任一维度超额均不阻拦,仅弹出"已超预算,是否仍然提交?"确认框 + 打 `over_budget_flag`,UI 提示具体超哪一盘

### 3.6 lti(长期激励 RSU)

- `LTIPlan`: id, code, name, grant_date, total_shares, **share_unit**(默认 `ADS`), unit_price_at_grant, vesting_schedule(JSONB,默认 **5 年归属**,可配比例), cliff_months, plan_doc_url, stock_code, reward_cycle_id(可空)

- `LTIBudgetCell`(RSU 预算二维分解,按人员类别追踪 人数+股数)— 对应 RSU 预算表头"类别/可分配(人数/股数)/已使用(人数/股数)/结余(人数/股数)":
  - id, plan_id, employee_category_1(**MANAGEMENT / STAFF**)
  - **可分配**:`headcount_quota`(人数配额), `shares_quota_ads`(股数配额 ADS)
  - **已使用**:`headcount_used`(= 已纳入 grant 的不同员工数;**一个员工一个周期内只授予一次,因此 `headcount_used = 授予人次 = count(LTIGrant)`**),`shares_used_ads`(实时汇总 `sum(granted_ads)`)
  - **结余**(派生):`headcount_remaining = quota - used`, `shares_remaining_ads = quota - used`
  - `合计`行前端派生,不落库
  - **预算约束(软约束 + HR 把关)**:
    - Cell 级:仅用于可视化与实时预警,**允许 MGMT / STAFF 池互相混用**
    - 总池约束:`sum(shares_used_ads) ≤ Cell(MGMT).shares_quota + Cell(STAFF).shares_quota`,人数同理
    - 超 Cell 或超总池均**不阻拦提交**,仅弹出"已超预算,是否仍然提交?"确认框 + 在 Proposal 批次打 `over_budget_flag`,HR 终审把关
    - **同周期唯一性硬校验**(此项是硬约束):一个员工在同一 LTIPlan 内最多一条 `LTIGrant`;DB 层 `UNIQUE (plan_id, employee_id)` 兜底

- `LTIGrant`: 新增 RSU 授予记录
  - id, plan_id, employee_id, status(PROPOSED/APPROVED/SIGNED/ACTIVE/CANCELED), reason, approver_chain(JSONB)
  - `is_eligible`(是否具资格,布尔,由资格规则计算)
  - `grant_tier`(授予档位,如 T1/T2/T3,按绩效 + 职级 + 人员类别决定)
  - `suggested_range_min_ads` / `suggested_range_max_ads`(系统建议 ADS 区间)
  - `granted_ads`(实际授予 ADS 数,由管理者在建议区间内决定)
  - `employee_category_1_snapshot`(快照人员类别,避免后续调整导致预算对不上)
  - `stock_code`, `unit_price_at_grant`
  - `pending_shares_by_year`(JSONB,按自然年映射的待归属 ADS 数,审批通过时冻结)
- `VestingEvent`: id, grant_id, scheduled_date, scheduled_shares(ADS), actual_date, actual_shares, status(PENDING/VESTED/FORFEITED)
- `StockPriceMonthly`: id, stock_code, month(YYYY-MM), closing_price, currency, **source(MARKET / HR_LOCKED)**, locked_by, locked_at, note
- `EmployeeAck`: id, subject_type(ADJUSTMENT/BONUS/GRANT), subject_id, employee_id, acked_at, signature_hash

**派生指标(用于分配页"参考信息-当前"列)**:
- `pending_ads_by_year[Y]`:员工在某年 Y 的待归属 ADS 数,由所有 ACTIVE LTIGrant 的 `pending_shares_by_year[Y]` 汇总
- `pending_ads_ratio_y`:某年待归属 ADS 占该员工截至该年累计已授予 ADS 的比例
- `rsu_attention_flag`:绩效为绩优(如 E+/O) 且某未来年度 RSU 待归属相比上一年减少 → true(用于"建议关注"列)

### 3.7 reward_cycle(奖酬周期)

- `RewardCycle`: id, code, name, period, status(DRAFT/IN_PROGRESS/APPROVING/EXECUTED/CLOSED), scope(JSONB)
- 关联:`linked_adjustment_plan_id`(→ AdjustmentPlan)、`linked_lti_plan_id`(→ LTIPlan,可空)
- `total_comp_config`(JSONB):本周期冻结的股价版本、FX、绩效系数映射
- **审批模式固定为 UNIFIED**:调薪 + RSU 必须同时分配完、在同一个 RewardCycle 批次内**一次性提交审批**,一条审批链上同时审两者;不支持拆分提交
  - 审批通过后,调薪与 RSU 同步进入 `APPROVED_PENDING_EXECUTE`;执行门控也统一由 HR_ADMIN 批量执行(调薪切 CompensationRecord + RSU 生成 VestingEvent 在同一事务触发)
  - 若某员工当期不授 RSU(非资格员工),则其 proposal 只承载调薪部分;仍走同一条 RewardCycle 审批链

### 3.8 approval(审批引擎)

- `ApprovalChainTemplate`: id, scenario(ADJUSTMENT/BONUS/LTI/REWARD_CYCLE/DELEGATION), name, status(ACTIVE/ARCHIVED), version, is_default, nodes(JSONB 有序数组), effective_from, effective_to
  - 一个 scenario 同时只允许一条 `is_default=true` 的 ACTIVE 模板;方案创建时若未指定模板则使用默认模板的当前 version
  - 模板采用版本化策略:修改模板 = 新建 version + 归档旧 version,历史 ApprovalInstance 继续按其创建时绑定的 version 运行,避免中途变链
  - node 结构:`{code, role, scope, condition?, n_of_m?, optional?, description?}`
    - `code`:节点唯一标识(如 `DEPT_HEAD`, `HR_ADMIN`, `EXEC_OVER_20PCT`),便于引用与打回定位
    - `role`:该节点需要的角色(如 HR_ADMIN)
    - `scope`:解析实际审批人的作用域表达式
    - `condition`:可选表达式(如 `max_adjustment_pct > 0.20` 或 `grant_ads_sum > 100000`);`true` 时节点生效,`false` 时**跳过**该节点
    - `n_of_m`:同级 m 个候选任意 n 个通过即节点通过(默认 `1/1`)
    - `optional`:可选,`true` 表示该节点人为可移除(HR 在后台配模板时勾选)
  - scope 表达式:`CHAIN_UP(n)` 发起人向上 n 级、`CENTER_OF(subject)`、`CHARGE_OF(subject)`(分管负责人)、`DEPT_HEAD_OF(subject)`、`GLOBAL`

**默认审批链**(各场景开箱即用,HR 可在后台增减节点):

| 场景 | 默认节点序列 | 说明 |
|---|---|---|
| ADJUSTMENT(单独调薪)/ REWARD_CYCLE(合并调薪+RSU)/ BONUS(年终奖)| `CENTER_HEAD`(仅当该员工通过授权由中心负责人分配时)→ `DEPT_HEAD 或 CHARGE_OF`(取决于发起人身份)→ `HR_ADMIN`(薪酬 HR,终审)→ `EXEC`(条件节点,仅当达到金额/幅度阈值时触发)| **HRBP 不在默认链上**;如需 HRBP 参与,HR 在后台手工增加节点 |
| DELEGATION(中心授权)| `HR_ADMIN` | 中心授权直接 HR 审批 |
| LTI(独立授予场景,罕用)| `DEPT_HEAD 或 CHARGE_OF` → `HR_ADMIN` → `EXEC`(条件) | 正常 RSU 走 REWARD_CYCLE 链 |

**灵活增减示意**(后台配模板页的操作):
- 增加节点:拖动一个新节点(如 `HRBP`, 某个 `EXEC_CFO`)到序列任意位置,配 role / scope / condition
- 删除节点:仅 `optional=true` 的节点可删;默认链中 `HR_ADMIN` 终审节点**不可删除**(业务红线)
- 调整顺序:拖拽重排
- 条件节点:对某节点加/改 `condition`,未命中时自动跳过(如 `EXEC_OVER_20PCT` 仅在调薪幅度 >20% 时生效)
- `ApprovalInstance`: id, template_id, subject_type, subject_id, current_node, status(RUNNING/APPROVED/REJECTED/WITHDRAWN)
  - `over_budget_flag`(布尔):批次提交时若任一预算维度超额,此批次此实例打标;HR_ADMIN 终审节点 UI 强提示
  - `over_budget_details`(JSONB):结构化记录超了哪些 Cell / 总池、各自超额金额/股数、提交者确认时间,方便 HR 判断
- `ApprovalStep`: id, instance_id, node_index, approver_user_id, action(APPROVE/REJECT_BATCH/REJECT_INDIVIDUAL/REJECT_WITH_COMMENT), comment, acted_at

### 3.9 audit(独立 schema,仅 INSERT)

- `audit_log`: id, occurred_at, actor_id, actor_role, action, resource_type, resource_id, before(JSONB), after(JSONB), ip, user_agent, request_id
- `sensitive_view_log`: id, viewer_id, subject_type, subject_id, fields_viewed, delegation_id(如适用), at
- `export_log`: id, exporter_id, kind, filter(JSONB), row_count, file_url, at

### 3.10 notification / report

- `Notification`: id, user_id, channel(SITE/EMAIL), template, payload(JSONB), status
- `ReportSnapshot`: id, kind, period, scope(JSONB), data(JSONB), generated_at

### 3.10-bis 派生指标补充:分位 / 指引

- `monthly_salary_bucket`(月薪水平):按 `JobGrade.p50/p75/p90` 计算员工现薪所在档位(<P50 / P50-P75 / P75-P90 / >P90)
- `total_comp_bucket_Y`(某年总包水平):按该职级总包对标带宽(如 HR 配置的 `TotalCompBand`)计算员工总包所在档位
- `suggested_annual_adjustment_range`(建议年度调薪范围,如 `[3%, 6%]`):按绩效 + 分位 + 方案公式给出的区间,用于提示管理者
- `rsu_share_guideline`(RSU 占比指引,如推荐 25%–40% 的阈值带,用于总包中长激占比的参考)

### 3.11 派生对象:TotalCompSnapshot

- id, employee_id
- trigger_type(ADJUSTMENT / BONUS / LTI_GRANT / REWARD_CYCLE / MANUAL_REFRESH / PRICE_UPDATE)
- trigger_id, triggered_at
- **year_offset(-1 / 0 / +1 / +2)**, calendar_year
- **currency**(员工 `local_currency`)+ **cny_fx_rate**(换算为 CNY 用)
- **现金薪酬分项**(与分配页"现金薪酬"子列一一对应):
  - `annual_base_local`(固薪,当地币种,单位**万**或**元**,存原始值即可,展示单位由前端格式化)
  - `annual_bonus_local`:
    - Y-1:`annual_bonus_actual`(历史实际发放,含年度服务奖 + 年度绩效奖)
    - Y / Y+1 / Y+2:`annual_bonus_target`(当期 proposal 的 total_bonus_local 或目标口径)
  - `annual_cash_subtotal_local` = base + bonus(现金薪酬小计)
- **长期激励分项**:
  - `annual_rsu_value_local`:
    - Y-1:已归属价值(`Σ VESTED VestingEvent 的 actual_shares × 归属月股价`)
    - Y / Y+1 / Y+2:待归属价值(`Σ PENDING VestingEvent 的 scheduled_shares × 对应月股价,优先 HR_LOCKED`)
  - `lti_status_label`:历史年用"已归属",未来年用"待归属"
- **合计与占比**:
  - `total_comp_local` = 现金小计 + RSU 价值
  - `lti_ratio` = RSU / total_comp(长期激励占比)
  - `rsu_guideline_band`(派生自 §3.10-bis `rsu_share_guideline`,用于 UI 提示色)
- **不含 RSU 口径**(无 RSU 权限用户视图):
  - `annual_cash_comp_local` = `annual_cash_subtotal_local`(列标题换为"现金薪酬年包")
- **CNY 对账值**:`total_comp_cny` 等同于 `total_comp_local × cny_fx_rate`,仅用于预算/汇总
- `assumption`(JSONB:股价版本、FX、绩效系数、奖金口径 actual/target、base_salary 快照来源)

**场景对时间窗的使用**:
- 年终奖分配场景:使用 Y-1、Y 两年(两年都含奖金;Y-1 为 actual,Y 为当前奖金 proposal 的 proposed 或 suggested)
- 调薪 & RSU 分配场景:使用 Y-1、Y、Y+1 三年(RSU cliff 后次年才有归属,必须看到 Y+1 才能观察 RSU 首次归属带来的总包变化)
- 展示层派生 YoY 涨幅:`Δcash%`、`Δrsu%`、`Δtotal%` 三项(分母年份为基准年)

**按年度的计算规则**:
- Y-1(历史):
  - `annual_base` = 过往 12 个月 CompensationRecord 加权平均 × 12(中途调薪按生效日加权)
  - `annual_bonus_actual` = 该年度已执行 BonusProposal 合计(`EXECUTED` 状态)
  - `annual_rsu_value` = 该年度 `VestingEvent.status=VESTED` 的 `actual_shares × 归属月实际或锁定股价`
- Y(当年):
  - `annual_base` = 当前 monthly_salary × 剩余月 + 拟调后 monthly_salary × 已过月(按 proposal 的 effective_date 切换)
  - `annual_bonus_target` = 当年奖金 proposal 的 `proposed_amount`(若在年终奖周期内)或 `base × months_factor × perf_factor`(目标口径)
  - `annual_rsu_value` = Σ 当年 `VestingEvent`(含当年即将授予且当年就归属的部分,cliff 下通常为 0)× 当月股价
- Y+1 / Y+2:
  - `annual_base` = 拟调后 monthly_salary × 12
  - `annual_bonus_target` = 拟调后 base × months_factor × perf_factor(使用快照绩效系数)
  - `annual_rsu_value` = Σ 该年 `VestingEvent.scheduled_shares × StockPriceMonthly[对应月,优先 HR_LOCKED]`

**RSU 估值公式(通用)**:`annual_rsu_value(Y) = Σ(VestingEvent in year Y).shares × StockPriceMonthly[对应月, source 优先 HR_LOCKED]`

**Y-1 快照的存储**:Y-1 数据为只读历史,系统按自然年切换时(每年 1 月 Celery Beat)固化写入;之后不随重算变更。

---

## 4. 业务流程

### 4.1 场景一:年终奖分配(独立场景)

```
[HR_ADMIN]
  1. 建 BonusPlan + 拆分层级预算(按分管范围 → 部门 → 中心 多层)
  2. 发起 → status=IN_PROGRESS,下推到各部门
                       │
                       ▼
[DEPT_HEAD / CENTER_HEAD(获授权)]
  3. 调整 proposed_amount,**超预算不阻拦**:UI 实时高亮超额单元,提交时弹出"已超预算,是否仍然提交?"确认框;带 `over_budget_flag` 提交后由 HR 终审把关
     - **页面顶部(表头)**:部门预算统一换算 CNY 展示
       (总预算 / 已分配 / 剩余,支持多币种下属门下换算汇总)
     - **明细表(每行)**:员工 proposed_amount 以 `local_currency` 显示
       + 悬浮提示显示 FX 及换算后的 CNY 对账值
  4. **分配页嵌入实时总包测算(Simulate)**:
     - 管理者编辑 `年度服务奖` / `年度绩效奖-管理者调整额` 等可编辑字段
     - 前端 debounce 300ms → `POST /api/bonus-plan/{id}/simulate`
       (与合并分配页的 `/api/reward-cycle/{id}/simulate` 同一套 TotalComp 计算引擎,无副作用)
     - 后端返回 Y-1(actual 奖金 + 已归属 RSU)/ Y(proposed 奖金 + 当年归属 RSU)两年 TotalCompSnapshot
     - 前端刷新该员工行的派生列:
        - 奖金合计 / 绩效奖金月份数
        - 25 年年化薪酬(现金:固薪/奖金/小计,长激-当年归属,全面薪酬合计)
        - 24 年年化薪酬(同结构)
        - 全面薪酬涨幅(25 vs 24):现金 / 长激 / 全面薪酬合计
     - 总包数值按员工**当地币种**展示,表头预算仍以 CNY 口径汇总
     - 无 RSU 权限时:接口剔除 `annual_rsu_value + total_comp`,前端列标题切换为"现金薪酬年包"(详见 §5.3)
  5. 一键提交审批
                       │
                       ▼
[审批引擎] 默认链:CenterHead(如授权)→ DeptHead(或 CHARGE_OF 分管负责人)→ HR_ADMIN(薪酬 HR)→ (EXEC 视金额)
  - HRBP **不在默认链上**;如需参与由 HR 在 `ApprovalChainTemplate` 加节点
  - 所有节点支持按方案/场景灵活增减,见 §3.8
  - 支持 REJECT_BATCH / REJECT_INDIVIDUAL / REJECT_WITH_COMMENT
                       │
                       ▼
[HR_ADMIN]
  6. 终审通过 → APPROVED_PENDING_EXECUTE
  7. "待执行"页勾选批量 → 二次 MFA → EXECUTED
  8. 触发:audit_log / TotalCompSnapshot 重算 / Notification
                       │
                       ▼
[员工端] 签收(EmployeeAck)→ 导出对接发薪系统
```

### 4.2 场景二:调薪 & RSU 合并分配(RewardCycle)

**核心创新**:两种激励因子在同一页面并列调整,实时显示员工 3 年总包变化。

```
[HR_ADMIN]
  1. 建 RewardCycle(含 linked_adjustment_plan + linked_lti_plan,可选)
  2. 锁定本周期股价版本、FX、绩效系数快照到 total_comp_config
  3. 系统批量生成 AdjustmentProposal + LTIGrant(suggested 值)
                       │
                       ▼
[DEPT_HEAD / CENTER_HEAD(获授权)]  ── 合并分配页
  ┌─ **页面顶部(表头)**:部门调薪预算 / RSU 股数池 统一 CNY 展示
  │   (总预算 / 已分配 / 剩余,跨地区多币种自动 FX 换算汇总)
  ├─ 员工明细表(每行,**金额均为当地币种**):
  │     员工 | 员工类型(管理干部/员工) | 是否晋升 | 晋升后职级 |
  │     现薪 | 调后月薪 | RSU 股数 | Y-1/Y/Y+1 总包 | 分位落点
  ├─ 点开单人 → 激励因子面板(滑块/输入)
  │   - 调薪幅度 / 目标月薪(当地币种)
  │   - RSU 股数
  │   - 绩效系数(只读)
  │   - 晋升后职级(只读,来自员工基础信息静态字段)+ P50/P75/P90 落点
  │   - 员工类型(只读,影响建议值公式与分位对标)
  │   - 前端 debounce 300ms 调用:
  │     POST /api/reward-cycle/{id}/simulate
  │     → 返回 **Y-1 / Y / Y+1 三年 TotalComp**(当地币种 + CNY 对账双值)
  │   - 显示年比年 Δ:Δcash% / Δrsu% / Δtotal%
  │   - 重点:**Y+1 反映当周期新授 RSU 在 cliff 后的首次归属价值**
  ├─ 部门预算 / RSU 额度实时约束(表头预算 CNY 口径 vs 明细汇总 CNY 口径)
  └─ **调薪 + RSU 全员处理完 → 一次性提交审批**(不支持仅提交调薪或仅提交 RSU;两者必须同批次)
                       │
                       ▼
[审批引擎] 一条 UNIFIED 审批链同时审调薪 + RSU
  - 默认节点序列:DeptHead(或 CHARGE_OF 分管负责人)→ HR_ADMIN(薪酬 HR,终审)→ EXEC(条件:晋升 >20% / RSU 股数 >N)
  - HRBP **不在默认链**;如需加入由 HR 在 `ApprovalChainTemplate` 插入节点(支持灵活增减,见 §3.8)
  - 打回粒度:REJECT_BATCH 整批退回管理者;REJECT_INDIVIDUAL 仅挑出问题员工退回,其余继续推进
                       │
                       ▼
[HR_ADMIN]
  执行门控(调薪 + RSU 原子执行,同事务):
    - 调薪:生效日切换 CompensationRecord 新版本(Celery 日终)
    - RSU:生成全部 VestingEvent + 冻结 pending_shares_by_year
    - 任一失败 → 整批回滚,记审计
  TotalCompSnapshot 重算 → 通知员工
                       │
                       ▼
[员工端] 查看调薪通知 + RSU 授予书 → 签收
```

**晋升调薪 / 年度调薪 / 个别特殊调薪 — 全部合入 RewardCycle 上方主流程**:
```
[员工基础信息]:job_level_promoted / position_promoted / is_promoted / promotion_category / participates_annual_adjustment
                均为员工主数据静态字段,由 Excel 导入或外部 HR 同步维护
                      │
                      ▼
[HR_ADMIN 建 RewardCycle 时]
  1. 系统按本周期 scope ∩ Employee 全量生成 AdjustmentProposal(每位员工一条)
  2. 针对 `is_promoted=true` 的员工:按职级变更查表,填入 `promotion_adjustment_pct`(固定值)
  3. 针对 `participates_annual_adjustment=true` 的员工:按公式填入 `annual_suggested_pct`
  4. 两者同时存在:在**同一条 AdjustmentProposal** 的 `promotion_*` 与 `annual_*` 字段中分别承载
  5. RSU LTIGrant 由具资格员工同周期并行生成
                      │
                      ▼
[合并分配页]
  · 管理者仅可编辑 `annual_manager_delta_pct`(年度调薪管理者调整)、`granted_ads`、`is_special_case` / `market_benchmark_note` / `retention_reason`
  · `promotion_adjustment_pct` 系统固定,只读
  · 一次性完成调薪(含晋升+年度+特殊)+ RSU 全部分配
                      │
                      ▼
[UNIFIED 审批链] 调薪 + RSU 同批次、一条链同时审
  · `is_special_case=true` 或 `annual_final_pct > 阈值` 或 `total_adjustment_pct > 20%` → 条件节点加签 EXEC
                      │
                      ▼
[HR_ADMIN 执行门控 · MFA · 原子执行]
  · 年度调薪:按 `annual_final_pct` 切 CompensationRecord
  · 晋升调薪:按 `promotion_adjustment_pct` 叠加切 CompensationRecord + 写回 Employee.job_level_current = job_level_promoted、position_current = position_promoted、is_promoted 置 false、promotion_category 清空
  · RSU:生成 VestingEvent + 冻结 pending_shares_by_year
  · 任一失败 → 整批回滚,记审计
```

**场外晋升批次处理**:某员工在标准 RewardCycle 周期外被晋升(如年中单独晋升)时,HR 建一个 scope 仅覆盖该员工的**临时 RewardCycle**(可不挂 LTIPlan),其 AdjustmentProposal 仅填 `promotion_*` 字段、`annual_*` 为 0;仍走 UNIFIED 审批链。不再有独立的晋升调薪审批流。

**个别特殊/保留性调薪**:不再单列流程。管理者在合并分配页勾选 `is_special_case=true` + 填 `market_benchmark_note` / `retention_reason`,与当条 proposal 的其他调薪合并提交,幅度超阈值或 `is_special_case=true` 自动加签 EXEC 条件节点。

### 4.3 权限授权流程(中心授权)

```
[DEPT_HEAD 员工端 → "授权中心负责人" 页]
  1. 选中心 + 选 CENTER_HEAD
  2. 勾 resource_grants 模板(基础档/完整档/自定义)
     - 含 RSU 权限开关(lti.view + lti.allocate + total_comp_snapshot.include_rsu_value)
  3. 绑定方案周期 valid_from/valid_to + plan_binding
  4. 提交 → PermissionDelegation.status=PENDING
                       │
                       ▼
[HR_ADMIN 审批] → 通过后 status=ACTIVE
                       │
                       ▼
[Celery Beat]
  - 每小时扫描过期 → EXPIRED
  - 授权人离职/转岗 → SUSPENDED + 通知 HRBP 重新指派
```

### 4.4 横切流程

所有数据改动 → 审计中间件写 `audit_log`(before/after + actor + IP + request_id)。
导出 / 敏感字段查看 / 股价锁定 / MFA 事件 → 对应日志表。
所有批量计算 → Celery 任务,幂等 key + 可重试。

### 4.5 分配页列规范(UI 事实源)

本节列出两大分配页的**全部列及其后端字段映射**,作为前后端实现的唯一事实源。下表以 2026 年为示例年(Y=2026,Y-1=2025,Y+1=2027)。

#### 4.5.1 年终奖分配页列规范(以 Y=2025 年终奖周期为例)

| 分组 | 列名 | 后端字段 / 来源 | 可编辑 | 单位/币种 |
|---|---|---|---|---|
| 基础信息 | 序号 | 行号(前端生成) | ❌ | - |
| | 英文名 | Employee.name_en | ❌ | - |
| | 中文名 | Employee.name_cn | ❌ | - |
| | 部门 | Employee.dept_name(OrgUnit 树推导) | ❌ | - |
| | 中心 | Employee.center_name | ❌ | - |
| | 组 | Employee.team_name | ❌ | - |
| | 岗位 | Employee.job_family | ❌ | - |
| | 专业职级 | Employee.job_level_current | ❌ | - |
| | 职务 | Employee.position_current | ❌ | - |
| | 入职日期 | Employee.hire_date | ❌ | - |
| | 发薪国家(地区) | Employee.pay_country_region | ❌ | - |
| | 发薪币种 | Employee.pay_currency | ❌ | - |
| 绩效 | Y 年中 | PerformanceRating(year=Y, half=H1).rating | ❌ | - |
| | Y 年底 | PerformanceRating(year=Y, half=H2).rating | ❌ | - |
| 奖金关联基数/系数 | 奖金基数 | BonusProposal.bonus_base | ❌(计算) | 当地币种 元 |
| | 在职时间系数 | BonusProposal.tenure_factor | ❌ | 数值 |
| | 个人绩效系数 | BonusProposal.perf_factor | ❌ | 数值 |
| 年度服务奖 · SERVICE(当地货币,元) | 金额 | BonusProposal.service_award_amount_local | ❌(按在职年限规则计算) | 当地币种 元 |
| 基准奖金 · PERF_BASE(当地货币,元,启用时显示) | 建议分配额 | BonusProposal.perf_base_suggested_local | ❌ | 当地币种 元 |
| | 部门管理者调整额(动用 PERF_BASE 机动盘) | BonusProposal.perf_base_manager_adjust_local | **✅** | 当地币种 元 |
| | 调整后金额 | BonusProposal.perf_base_final_local(派生) | ❌ | 当地币种 元 |
| 弹性奖金 · PERF_FLEX(当地货币,元,仅 `BonusPlan.enabled_subtypes` 含 `PERF_FLEX` 时显示) | 建议分配额 | BonusProposal.perf_flex_suggested_local | ❌ | 当地币种 元 |
| | 部门管理者调整额(动用 PERF_FLEX 机动盘) | BonusProposal.perf_flex_manager_adjust_local | **✅** | 当地币种 元 |
| | 调整后金额 | BonusProposal.perf_flex_final_local(派生) | ❌ | 当地币种 元 |
| 年度绩效奖合计 | 合计调整后金额 | performance_bonus_final_local = coalesce(base_final, 0) + coalesce(flex_final, 0) | ❌ | 当地币种 元 |
| 奖金合计(当地货币,元) | 合计 | BonusProposal.total_bonus_local(派生) | ❌ | 当地币种 元 |
| 通用 | 绩效奖金月份数 | BonusProposal.perf_bonus_months | ❌ | 数值 |
| | 说明 | BonusProposal.note | **✅** | 文本 |
| Y 年年化薪酬(当地货币,万) | 现金-固薪 | TotalCompSnapshot(Y).annual_base_local | ❌ | 当地币种 万 |
| | 现金-奖金 | TotalCompSnapshot(Y).annual_bonus_target_local | ❌(联动当期 proposal) | 当地币种 万 |
| | 现金-小计 | 固薪 + 奖金 | ❌ | 当地币种 万 |
| | 长期激励-Y 年归属 | TotalCompSnapshot(Y).annual_rsu_value_local(lti_status=待归属) | ❌ | 当地币种 万 |
| | 全面薪酬合计 | TotalCompSnapshot(Y).total_comp_local | ❌ | 当地币种 万 |
| Y-1 年年化薪酬(当地货币,万) | 现金-固薪 | TotalCompSnapshot(Y-1).annual_base_local | ❌ | 当地币种 万 |
| | 现金-奖金 | TotalCompSnapshot(Y-1).annual_bonus_actual | ❌ | 当地币种 万 |
| | 现金-小计 | 固薪 + 奖金 | ❌ | 当地币种 万 |
| | 长期激励-Y-1 年归属 | TotalCompSnapshot(Y-1).annual_rsu_value_local(lti_status=已归属) | ❌ | 当地币种 万 |
| | 全面薪酬合计 | TotalCompSnapshot(Y-1).total_comp_local | ❌ | 当地币种 万 |
| 全面薪酬涨幅(Y vs Y-1) | 现金薪酬 Δ% | 派生 | ❌ | 百分比 |
| | 长期激励 Δ% | 派生 | ❌ | 百分比 |
| | 全面薪酬合计 Δ% | 派生 | ❌ | 百分比 |

**页面表头(部门/中心总览区)— 年终奖预算表,单位 RMB**

数据来源:`BonusSubtypeBudget` 按 `bonus_subtype ∈ BonusPlan.enabled_subtypes` 过滤 + 当前作用域内 `BonusProposal` 实时汇总。**行数据驱动** —— 前端按 `enabled_subtypes` 动态渲染行,弹性未启用时整行不显示,无需改表头结构。

| 类别 | 子类别 | 可分配总盘 | 已分配 | 机动盘 |
|---|---|---|---|---|
| 年度服务奖 | - | SERVICE.budget_amount_cny | SERVICE.allocated_amount_cny(= sum service_award_amount_cny) | SERVICE.reserve_amount_cny |
| 年度绩效奖 | 基准奖金 | PERF_BASE.budget_amount_cny | PERF_BASE.allocated_amount_cny(= sum perf_base_final_cny) | PERF_BASE.reserve_amount_cny |
| 年度绩效奖 | 弹性奖金(仅启用时显示) | PERF_FLEX.budget_amount_cny | PERF_FLEX.allocated_amount_cny(= sum perf_flex_final_cny) | PERF_FLEX.reserve_amount_cny |
| 年度绩效奖 | 小计(启用中的 PERF_* 逐列相加) | 派生 | 派生 | 派生 |

**业务语义与灵活性**:
- 两个绩效池都有**各自独立的机动盘**;基准机动盘不能用于弹性奖金,反之亦然
- 机动盘由管理者在预算内调节员工奖金时动用(即管理者调整额来自该 subtype 的机动盘)
- `可分配总盘` 与 `机动盘` 由 HR 在管理后台维护;`已分配` 由应用层写入 Proposal 时累计
- 单侧管理者调整额为负时,释放回对应 subtype 的机动盘(不跨 subtype)
- **弹性奖金启停**:改 `BonusPlan.enabled_subtypes` 配置即可;表结构不变,前端表头与列自适应
- 未来若新增子类别(如 "项目奖金池"),扩展 `bonus_subtype` 枚举 + 添加对应 `BonusProposal` 三元组字段即可,旧数据不受影响

#### 4.5.2 调薪 + RSU 合并分配页列规范(以 Y=2026 周期为例)

| 分组 | 列名 | 后端字段 / 来源 | 可编辑 | 单位/币种 |
|---|---|---|---|---|
| 基础信息 | 序号 | 前端生成 | ❌ | - |
| | 辅助列 | 预留(留给前端排序/分组辅助键) | ❌ | - |
| | 姓名 | Employee.name_cn | ❌ | - |
| | 部门 | Employee.dept_name | ❌ | - |
| | 中心 | Employee.center_name | ❌ | - |
| | 专业职级(晋升后) | Employee.job_level_promoted | ❌ | - |
| | 职务(晋升后) | Employee.position_promoted | ❌ | - |
| | 人员类别 1 | Employee.employee_category_1 | ❌ | - |
| | 人员类别 2 | Employee.employee_category_2 | ❌ | - |
| | 入职日期 | Employee.hire_date | ❌ | - |
| | 发薪国家(地区) | Employee.pay_country_region | ❌ | - |
| | 币种 | Employee.pay_currency | ❌ | - |
| 绩效 | Y-1 年中 | PerformanceRating(Y-1, H1) | ❌ | - |
| | Y-1 年底 | PerformanceRating(Y-1, H2) | ❌ | - |
| 参与标志 | 是否参与年调 | Employee.participates_annual_adjustment | ❌(主数据) | 布尔 |
| | 晋升类别 | Employee.promotion_category | ❌ | 枚举 |
| 参考信息-当前 · 未来 5 年待归属 ADS | Y 年 | pending_ads_by_year[Y] | ❌ | ADS |
| | Y+1 | pending_ads_by_year[Y+1] | ❌ | ADS |
| | Y+2 | pending_ads_by_year[Y+2] | ❌ | ADS |
| | Y+3 | pending_ads_by_year[Y+3] | ❌ | ADS |
| | Y+4 | pending_ads_by_year[Y+4] | ❌ | ADS |
| 参考信息-当前 · 其它 | Y 年待归属 RSU 占比 | pending_ads_ratio_y[Y] | ❌ | 百分比 |
| | 建议关注(Y+1 RSU 减少且绩优) | rsu_attention_flag | ❌ | 布尔标签 |
| | 月薪水平 | monthly_salary_bucket | ❌ | P50/P75/P90 档 |
| | Y 年总包水平 | total_comp_bucket_Y | ❌ | P50/P75/P90 档 |
| | 建议年度调薪范围 | suggested_annual_adjustment_range | ❌ | 百分比区间 |
| 当前月薪(当地货币,元) | 当前月薪 | AdjustmentProposal.current_salary | ❌ | 当地币种 元 |
| 调薪分配 · 晋升调薪比例 | 晋升调薪比例 | AdjustmentProposal.promotion_adjustment_pct | ❌(**固定比例,管理者不可调整**;按职级变更查表) | 百分比 |
| 调薪分配 · 年度调薪比例 | 建议比例 | AdjustmentProposal.annual_suggested_pct | ❌ | 百分比 |
| | 管理者调整 | AdjustmentProposal.annual_manager_delta_pct | **✅** | 百分比 |
| | 调整后比例 | AdjustmentProposal.annual_final_pct(派生) | ❌ | 百分比 |
| 调薪分配 · 总调薪 | 总调薪比例 | AdjustmentProposal.total_adjustment_pct | ❌ | 百分比 |
| | 调整后月薪(当地货币,元) | AdjustmentProposal.proposed_salary(派生) | ❌ | 当地币种 元 |
| | 总调薪额(当地货币) | AdjustmentProposal.total_adjustment_amount_local(派生) | ❌ | 当地币种 元 |
| Y 年股票授予(ADS,5 年归属) | 是否具资格 | LTIGrant.is_eligible | ❌(规则计算) | 布尔 |
| | 授予档位 | LTIGrant.grant_tier | ❌(规则计算,HR 可覆写) | 枚举 |
| | 建议区间 | LTIGrant.suggested_range_min_ads / _max_ads | ❌ | ADS |
| | 授予 ADS | LTIGrant.granted_ads | **✅** | ADS |
| 分配后待归属 | Y+1 年待归属 ADS | 派生:pending + 本次授予在 Y+1 的归属份额 | ❌ | ADS |
| | Y+2 年待归属 ADS | 同上 | ❌ | ADS |
| Y+1 年年化薪酬总包(当地货币,万) | 现金-固薪 | TotalCompSnapshot(Y+1).annual_base_local | ❌ | 当地币种 万 |
| | 现金-奖金 | TotalCompSnapshot(Y+1).annual_bonus_target | ❌ | 当地币种 万 |
| | 现金-小计 | 派生 | ❌ | 当地币种 万 |
| | 长期激励-Y+1 年待归属 | TotalCompSnapshot(Y+1).annual_rsu_value_local | ❌ | 当地币种 万 |
| | 合计 | total_comp_local | ❌ | 当地币种 万 |
| | 长期激励占比 | lti_ratio | ❌ | 百分比 |
| | RSU 占比指引 | rsu_guideline_band(如 推荐 25-40%) | ❌ | 文本/色带 |
| Y 年年化薪酬总包(当地货币,万) | 现金-固薪 | TotalCompSnapshot(Y).annual_base_local | ❌ | 当地币种 万 |
| | 现金-奖金 | TotalCompSnapshot(Y).annual_bonus_target | ❌ | 当地币种 万 |
| | 现金-小计 | 派生 | ❌ | 当地币种 万 |
| | 长期激励-Y 年待归属 | TotalCompSnapshot(Y).annual_rsu_value_local | ❌ | 当地币种 万 |
| | 合计 | total_comp_local | ❌ | 当地币种 万 |
| | 长期激励占比 | lti_ratio | ❌ | 百分比 |
| Y-1 年年化薪酬总包(当地货币,万) | 年现金薪酬 | TotalCompSnapshot(Y-1).annual_cash_subtotal_local | ❌ | 当地币种 万 |
| | 长期激励-Y-1 年已归属 | TotalCompSnapshot(Y-1).annual_rsu_value_local | ❌ | 当地币种 万 |
| | 合计 | total_comp_local | ❌ | 当地币种 万 |
| 全面薪酬涨幅 · Y+1 vs Y | 长期激励 Δ% | 派生 | ❌ | 百分比 |
| | 总包 Δ% | 派生 | ❌ | 百分比 |
| 全面薪酬涨幅 · Y vs Y-1 | 现金 Δ% | 派生 | ❌ | 百分比 |
| | 长期激励 Δ% | 派生 | ❌ | 百分比 |
| | 总包 Δ% | 派生 | ❌ | 百分比 |

**页面表头(部门/中心总览区)— 调薪 + RSU 双预算表**

左表(调薪预算,单位 RMB)数据来源:`AdjustmentBudgetCell`,按当前 RewardCycle 过滤 + 当前作用域内 `AdjustmentProposal` 实时汇总。

| 类别 | 晋升调薪 · 可分配总盘 | 晋升调薪 · 已分配 | 晋升调薪 · 剩余 | 年度调薪 · 可分配总盘 | 年度调薪 · 已分配 | 年度调薪 · 剩余 |
|---|---|---|---|---|---|---|
| 管理干部 | Cell(PROMOTION, MANAGEMENT).budget_amount_cny | sum(promotion_adjustment_amount_cny where category=MGMT) | 派生 | Cell(ANNUAL, MANAGEMENT) | sum(annual_adjustment_amount_cny where category=MGMT) | 派生 |
| 员工 | Cell(PROMOTION, STAFF) | sum(...) | 派生 | Cell(ANNUAL, STAFF) | sum(...) | 派生 |
| 合计 | 前端汇总(MGMT + STAFF) | 同上 | 同上 | 同上 | 同上 | 同上 |

右表(RSU 预算,人数 + ADS 股数双维度)数据来源:`LTIBudgetCell`。

| 类别 | 可分配 · 人数 | 可分配 · 股数(ADS) | 已使用 · 人数 | 已使用 · 股数 | 结余 · 人数 | 结余 · 股数 |
|---|---|---|---|---|---|---|
| 管理干部 | Cell(MANAGEMENT).headcount_quota | Cell(MANAGEMENT).shares_quota_ads | headcount_used | shares_used_ads | 派生 | 派生 |
| 员工 | Cell(STAFF).headcount_quota | Cell(STAFF).shares_quota_ads | headcount_used | shares_used_ads | 派生 | 派生 |
| 合计 | 前端汇总 | 前端汇总 | 前端汇总 | 前端汇总 | 前端汇总 | 前端汇总 |

- 所有 CNY 金额统一**汇总换算** 展示;悬浮可查分币种明细
- 明细行内所有金额仍以**员工当地币种**原值展示
- `人员类别1` 以 `*_snapshot` 字段对账,避免变更漂移
- 超 Cell 或超总池均**不阻拦提交**:UI 实时高亮 + 提交时弹"已超预算,是否仍然提交?"确认框,允许带 `over_budget_flag` 提交;HR 终审把关

**可编辑字段汇总**(仅这些列管理者能改):
- 年终奖页:
  - `perf_base_manager_adjust_local`(基准奖金 · 管理者调整额,从 PERF_BASE 机动盘动用)
  - `perf_flex_manager_adjust_local`(弹性奖金 · 管理者调整额,从 PERF_FLEX 机动盘动用;仅启用 PERF_FLEX 时显示)
  - `note`
  - 系统公式字段(`service_award_amount_local`, `perf_base_suggested_local`, `perf_flex_suggested_local`)均不可编辑
- 合并页:`annual_manager_delta_pct`(年度调薪-管理者调整)、`granted_ads`、`is_special_case` + `market_benchmark_note` + `retention_reason`

**Simulate 接口行为**:
- 合并分配页:`POST /api/reward-cycle/{id}/simulate` → 返回 Y-1 / Y / Y+1 三年 TotalCompSnapshot(RSU cliff 首次归属需要 Y+1)
- 年终奖分配页:`POST /api/bonus-plan/{id}/simulate` → 返回 Y-1 / Y 两年 TotalCompSnapshot(仅现金奖金变化,无未来 RSU 新增因子)
- 共用一套 TotalComp 计算内核(`total_comp_service.simulate`),区别仅在输入字段与返回的 `year_offsets` 窗口
- 每次编辑可编辑字段 → 前端 debounce 300ms → 调接口 → 后端无副作用重算 → 前端刷新所有派生列
- 无 RSU 权限时的剔除逻辑对两个接口均生效(详见 §5.3)

---

## 5. 权限模型

### 5.1 功能权限(RBAC)

| 角色 | 员工端 | 管理后台 | 核心能力 |
|---|---|---|---|
| EMPLOYEE | ✅ | ❌ | 本人薪酬/RSU 查看、签收、异议 |
| DEPT_HEAD | ✅ | ❌ | 下属分配页(含年度调薪/晋升调薪/年终奖/RSU)、下级审批、**授权中心**、提交审批(晋升决策不在本系统;个别特殊调薪在年度调薪方案中以 `is_special_case` 标记承载) |
| CENTER_HEAD | ✅(获授权后) | ❌ | 所辖中心的分配页(资源按授权开关) |
| HRBP | ✅ | ✅ | 所辖分管范围内的方案配置、报表;**不在默认审批链上**,仅当 HR 在模板中显式加入 HRBP 节点时才会出现在审批流中 |
| HR_ADMIN | ✅ | ✅ | 所有方案 CRUD、终审、**执行门控**、股价锁定、全局报表、数据导入、授权审批 |
| EXEC | ✅ | ✅ | 大额审批、全公司看板(聚合优先)、只读明细 |
| SYS_ADMIN | ❌ | ✅ | 用户/角色/组织/数据对接配置;**不可见业务数据** |

### 5.2 数据权限 Scope

```
scope_type: GLOBAL | CHARGE | DEPT | CENTER | SELF
```

| Scope | 适用角色 | 可见范围 |
|---|---|---|
| SELF | EMPLOYEE | 本人 |
| CENTER | CENTER_HEAD | 所辖中心及下级 TEAM(需授权) |
| DEPT | DEPT_HEAD | 本部门及所有下级(含 CENTER、TEAM) |
| CHARGE | EXEC / 高管 / HRBP(按需) | 所绑定 `ManagementScope` 内全部 OrgUnit 的并集及其下级;一个分管人可分管多个部门/分公司 |
| GLOBAL | HR_ADMIN, EXEC | 全公司 |

实现:`DataScopedQuerysetMixin` 自动在 ORM 查询附加过滤;跨范围 DB 层面不可见。CHARGE 范围实现为 `Employee.org_unit_id IN (SELECT descendants(org_unit_id) FROM ManagementScopeMember WHERE scope_id = :charge_scope_id)`。

### 5.3 授权资源开关(resource_grants)

JSON 结构:

```json
{
  "reward_cycle": {
    "view": true,
    "allocate_adjustment": true,
    "allocate_lti": false,
    "submit_for_approval": true
  },
  "bonus": {
    "view": true,
    "allocate": true,
    "submit_for_approval": true
  },
  "adjustment": {
    "view": true,
    "allocate": true
  },
  "lti": {
    "view": false,
    "allocate": false
  },
  "total_comp_snapshot": {
    "view": true,
    "include_rsu_value": false
  }
}
```

> 注:不再有 `adjustment.promotion_propose` 开关——本系统不发起晋升。

**无 RSU 权限时的响应处理**:`TotalCompSnapshot` 序列化时**同时剔除** `annual_rsu_value` 和 `total_comp`,仅返回 `annual_cash_comp` 口径;前端列标题显示为"现金薪酬年包",完全不暴露"此人有 RSU"这一事实。

### 5.4 字段级掩码

| 字段 | EMPLOYEE | DEPT_HEAD | CENTER_HEAD(视授权) | HRBP/HR | EXEC | SYS_ADMIN |
|---|---|---|---|---|---|---|
| 本人薪酬 | ✅ | — | — | ✅ | ✅ | ❌ |
| 他人现金薪酬 | ❌ | 下属 | 中心内 | 范围内 | 聚合(点开留痕) | ❌ |
| 他人 RSU | ❌ | 下属 | 需 `lti.view=true` | ✅ | 聚合 | ❌ |
| 绩效评级 | 本人 | 下属 | 中心内(若有 adjustment.view) | 范围内 | 聚合 | ❌ |
| 调薪原因 | 本人 | 下属(近 2 年) | 中心内 | 全量 | — | ❌ |
| 晋升后职级(job_level_promoted)/ 晋升后职务(position_promoted)/ 是否晋升(is_promoted)/ 晋升类别(promotion_category)/ 人员类别1(employee_category_1)/ 人员类别2(employee_category_2) | 本人 | 下属 | 中心内 | 范围内 | 聚合 | ❌ |

SYS_ADMIN 在审计后台查看 `audit_log.before/after` 时,数值字段自动脱敏为 `***`,仅可见字段名、操作人、时间。

### 5.5 MFA 触发点

- HR_ADMIN 登录管理后台
- 执行"生效"动作(强制)
- 锁定/修改未来股价
- 导出超过 50 人的明细
- 修改审批链模板
- 批准 PermissionDelegation

---

## 6. 非功能性需求

### 6.1 性能

- 5000 员工方案批量生成 proposal + 全员 TotalComp 重算 ≤ 5 分钟(Celery)
- 分配页 simulate 接口(年终奖 `/bonus-plan/*/simulate` 与合并页 `/reward-cycle/*/simulate`)P99 ≤ 300ms(内存计算,不查复杂数据)
- 列表 API P99 ≤ 500ms(2000 员工规模)
- 报表预聚合每日凌晨执行,高管看板 P99 ≤ 1s

### 6.2 安全

- HTTPS 强制、HSTS、CSP
- JWT 短有效期 + refresh;管理后台 idle 15 分钟登出
- TOTP MFA;触发点见 §5.5
- 密码:Argon2 哈希
- Secrets:公有云用 KMS;私有化用 Vault 或 env + 受限文件系统权限
- 所有外部接口 HMAC 签名校验

### 6.3 审计与合规

- `audit_log` 不可篡改:应用账号仅 INSERT,表设 UPDATE/DELETE trigger 拒绝
- audit schema 备份独立且长期保留 ≥ 7 年
- 所有导出留痕 + 水印(导出人工号 + 时间)

### 6.4 可用性

- 预期 SLA 99.5%(工作时间);非高峰支持滚动升级
- RPO 15 分钟(WAL 归档);RTO 2 小时

---

## 7. 测试策略

| 层 | 覆盖 | 工具 |
|---|---|---|
| 单元 | 奖金公式、分位分档、TotalComp 聚合、vesting 生成、RSU 估值 | pytest |
| 模块集成 | service + repository + API;审批状态机全路径 | pytest + pytest-django + factory_boy |
| 跨模块 e2e(API) | 三大场景端到端 + RewardCycle 合并场景 + 授权工作流 | pytest + DRF test client |
| 权限矩阵 | 角色 × scope × 资源 × RSU 开关 on/off | 参数化 pytest |
| 审计完整性 | 关键动作必写日志 | 断言 audit_log 行 |
| 前端 e2e | 两套 SPA 主流程 | Playwright |
| 负载 | 批量算薪 / TotalComp 重算 / 导入 | Locust |

**TDD 范围**:算法类(公式、分位、vesting、TotalComp 聚合、RSU 估值)强制 TDD。

---

## 8. 交付节奏:两阶段单人合作模式

### 8.1 角色分工

**Claude 承担**:所有后端/前端代码、数据模型、迁移、测试、Docker 编排、文档、架构迭代。

**项目负责人承担**:
- 本地/服务器环境(Docker、Python、Node、PG、Redis)
- 真实或测试数据(员工、组织、绩效、股价、合同主体)
- 外部系统凭证(若需对接)
- 业务决策(公式系数、审批人、预算口径)
- 用户验收(HR / 部门长真实试用)
- 生产部署操作、合规签字

### 8.2 阶段 1:垂直切片验证(约 2 周)

产出一条**端到端可演示链路**——最简 RewardCycle:
- 账号/角色/组织/MFA
- 员工主数据(Excel 导入 1 份示例)
- 1 个简化 RewardCycle(5 名员工,调薪 + RSU)
- 合并分配页(静态 TotalComp,不含 Simulate)
- 固定 2 级审批 → 执行 → 签收
- 应用层审计日志
- Docker Compose 一键启动

**阶段 1 出口标准**:项目负责人在自己环境一键启动、完成一次调薪 + RSU 完整流转、看到审计日志。

### 8.3 阶段 2:按迭代补齐剩余功能(估计 12–16 周)

每迭代 1–2 周,交付可演示增量。大致顺序:

| 迭代 | 内容 |
|---|---|
| 1 | TotalComp 计算引擎完整版 + 通用 Simulate 内核 + 合并分配页实时测算(Y-1/Y/Y+1) |
| 2 | 年终奖 BonusPlan + 分层预算 + 分配页(含 Y-1/Y 实时 Simulate)+ 审批 + 执行 |
| 3 | 统一 AdjustmentPlan(年度+晋升+特殊三位一体);`promotion_adjustment_pct` 固定比例查表;`is_special_case` 标识;分位档位提示;表头 CNY/明细当地币种分离 |
| 4 | RSU 完整(vesting 生成、HR 锁股价、签收) |
| 5 | 两种打回粒度 + 审批链条件节点 + MFA 全触发点 |
| 6 | 中心层数据权限 + PermissionDelegation 工作流 + HR 审批 |
| 7 | 外部 HR 系统 API 对接 + 数据同步任务 |
| 8 | 高管看板 + 报表预聚合 + 导出与水印 |
| 9 | 审计查询后台(SYS_ADMIN 视角 + 脱敏) |
| 10 | Helm Chart + 冷备演练 + 性能压测 |

迭代顺序可根据阶段 1 后的反馈重排。

### 8.4 会话连续性保障

- **Spec 文档 + 每次实现计划 + git log** 作为跨会话记忆载体
- 每次会话开始:Claude 读取当前 spec、最新 plan、最近提交 → 确认进度
- 每次会话结束:提交 git + 更新进度到 plan 文档
- 重大变更发生时,同步修订 spec

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 单人开发时间拉长 | 项目周期长,业务侧不耐 | 两阶段 + 迭代式交付,2 周即见首个垂直切片 |
| 会话上下文断裂 | 实现偏离 spec | spec + plan + git 三重锚点;每会话首先对齐 |
| 业务规则变更频繁 | 大量返工 | 关键公式与审批链参数化(formula_config、ApprovalChainTemplate),变更只改配置 |
| 真实数据延迟到位 | 无法验收 | 阶段 1 用脱敏/假数据即可跑通,真实数据滚动接入 |
| 外部 HR 系统对接阻塞 | 数据来源缺失 | 一期只做 Excel 导入;API 对接放迭代 7 |
| 性能瓶颈 | 大批量算薪超时 | Celery 分队列 + 读写分离;压测在迭代 10 |
| 审计合规审查不通过 | 无法上线 | 审计埋点从第一天就做;独立 schema + 只追加;导出水印 |

---

## 10. 附录

### 10.1 关键术语表

| 术语 | 含义 |
|---|---|
| RewardCycle | 奖酬周期,调薪与 RSU 合并分配的上层容器 |
| Simulate | 分配页实时测算接口,无副作用的 TotalComp 计算;年终奖页(Y-1/Y 两年)与合并分配页(Y-1/Y/Y+1 三年)共用一套内核 |
| ManagementScope(分管范围) | 一位高管所分管的多个部门/分公司集合;组织树无 BU 层,`ManagementScope` 提供按 user 维度跨 OrgUnit 的数据权限 Scope |
| TotalComp | 税前年化薪酬总包(固薪 + 奖金 + RSU 价值) |
| Annual Cash Comp | 现金薪酬年包,不含 RSU 价值;用于无 RSU 权限视图 |
| Band Bucket | 月薪/总包分位档位(<P50 / P50-P75 / P75-P90 / >P90) |
| ADS | American Depositary Shares,RSU 以 ADS 为单位,5 年归属 |
| Grant Tier | RSU 授予档位(如 T1/T2/T3),由绩效+职级+人员类别决定 |
| Vesting | 股票/RSU 的分批归属 |
| Pending ADS | 某年尚未归属的 ADS 股数(用于参考信息列与 TotalComp 估值) |
| RSU Attention Flag | 绩效绩优且未来年 RSU 待归属减少的提示标签 |
| 年度服务奖 | 基于在职年限的固定奖励(`SERVICE` 池) |
| 基准奖金 | 公司业绩**基本达成预期**带来的绩效奖金池(`PERF_BASE`);员工基于绩效系数分配;管理者在该池机动盘内调节 |
| 弹性奖金 | 公司业绩**超额完成**带来的增量奖金池(`PERF_FLEX`);年度业绩未超额时**可启停**;管理者在该池独立机动盘内调节 |
| 机动盘 | 每个子类别池内 HR 预留给管理者调节用的额度;基准与弹性**各自独立**,不跨池调用 |
| 软预算约束 | 超预算不阻拦提交,仅弹出"已超预算,是否仍然提交?"确认框,并在批次上打 `over_budget_flag`;HR 终审把关时决定是否放行 |
| 池间混用 | 调薪的 `管理干部池 / 员工池` 以及 RSU 的 `管理干部池 / 员工池` 允许在总池内互相挪用;Cell 维度仅做可视化预警 |
| PermissionDelegation | 部门长授权给中心长的工作流记录 |
| resource_grants | 授权的资源级细粒度开关(含 RSU 可见性) |
| 基准币种 | CNY,用于跨币种预算汇总与对账;员工明细始终以 local_currency 展示 |

### 10.2 参考枚举

- `AdjustmentPlan`:**无 type 字段**。一个 RewardCycle 对应 1 个 AdjustmentPlan,同时承载年度调薪 + 晋升调薪 + 个别特殊调薪;晋升**决策**在外部系统完成,本系统消费 `Employee.is_promoted / job_level_promoted` 等静态字段作为调薪依据;个别特殊/保留性调薪通过 `AdjustmentProposal.is_special_case` + `market_benchmark_note` + `retention_reason` 承载
- `Employee.promotion_category`:VERTICAL(纵向晋升)/ LATERAL(横向调动)/ NONE(建议值,可按业务扩展)
- `Employee.employee_category_1`:MANAGEMENT(管理干部)/ STAFF(员工)(典型用法)
- `Employee.employee_category_2`:业务自定义第二维分类(如 CORE / GENERAL / PROBATION 等)
- `LTIPlan.share_unit`:ADS(默认)
- `LTIGrant.grant_tier`:T1 / T2 / T3 / T4 / NONE(建议值,可按方案扩展)
- `PerformanceRating.rating`:O / E+ / E / M / B / U(建议值,可按业务扩展)
- `BonusProposal.status`:DRAFT / SUBMITTED / APPROVED / REJECTED / LOCKED / EXECUTED
- `LTIGrant.status`:PROPOSED / APPROVED / SIGNED / ACTIVE / CANCELED
- `VestingEvent.status`:PENDING / VESTED / FORFEITED
- `StockPriceMonthly.source`:MARKET / HR_LOCKED
- `RewardCycle` 审批模式:**固定 UNIFIED**(调薪 + RSU 同批次、一条审批链同时审、原子执行;不支持拆分)
- `ApprovalStep.action`:APPROVE / REJECT_BATCH / REJECT_INDIVIDUAL / REJECT_WITH_COMMENT
- `UserRole.scope_type`:GLOBAL / CHARGE / DEPT / CENTER / SELF(CHARGE → `ManagementScope.id`,DEPT/CENTER → `OrgUnit.id`)
- `OrgUnit.type`:COMPANY / SUBSIDIARY(分公司,可选)/ DEPT / CENTER / TEAM(**不含 BU**)
- `ManagementScope.status`:ACTIVE / ARCHIVED
- `BonusSubtypeBudget.bonus_subtype`:SERVICE(年度服务奖)/ PERF_BASE(基准奖金,公司业绩基本达成预期)/ PERF_FLEX(弹性奖金,公司业绩超额完成的增量,**可启停**)/ 未来扩展
- `BonusPlan.enabled_subtypes`:启用中的 subtype JSONB 列表,默认 `["SERVICE", "PERF_BASE", "PERF_FLEX"]`;未启用的不生成 Budget 行、Proposal 对应字段为 NULL
- `AdjustmentBudgetCell.adjustment_type`:ANNUAL / PROMOTION(**预算维度,非 plan 类型**;用于表头"晋升调薪/年度调薪"两列预算分别追踪)
- `AdjustmentBudgetCell.employee_category_1` / `LTIBudgetCell.employee_category_1`:MANAGEMENT / STAFF

---

**文档状态**:草案 · 待项目负责人评审
**下一步**:评审通过后由 Claude 进入 writing-plans,产出阶段 1(垂直切片)的详细实现计划。
