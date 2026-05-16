"""派生预算 service: 部门池 + (国家×员工类别×调薪类型) 切片。

派生模型 (2026-05-15 锁定):
  - 部门池为预算下发的真实单位 (层 2)
  - 派生值 (DERIVED) = Σ(切片) = Σ(monthly_salary × base_pct × factor); 月度增量, 不年化
  - 兜底覆盖 (IMPORTED) = HR 通过 BudgetOverride 覆盖派生值，逐 (部门, 调薪类型) 生效

部门归属:
  - 员工的 department = 沿 employee.org_unit.parent 向上找到最近的 type=DEPT 节点
  - 找不到 → 记入"未分配部门"伪桶 (department_id=None, 不可被 override)
"""
from decimal import Decimal
from typing import Iterable

from apps.compensation_plan.models import (
    BudgetOverride,
    EmployeeCategoryFactor,
    RegionalAdjustmentRule,
)
from apps.hr_master.models import (
    CompensationRecord,
    EmployeeCategoryAssignment,
)
from apps.iam.models import OrgUnit
from apps.reward_cycle.models import RewardCycle


ADJ_TYPES = ("ANNUAL", "PROMOTION")


def _latest_monthly_salary_map(employee_ids: Iterable[int]) -> dict[int, Decimal]:
    """对每个员工取最新一条 CompensationRecord.monthly_salary。"""
    result: dict[int, Decimal] = {}
    qs = (
        CompensationRecord.objects.filter(employee_id__in=list(employee_ids))
        .order_by("employee_id", "-effective_date", "-id")
        .values("employee_id", "monthly_salary")
    )
    for row in qs:
        eid = row["employee_id"]
        if eid not in result:
            result[eid] = row["monthly_salary"]
    return result


def _build_dept_lookup() -> dict[int, tuple[int, str]]:
    """为每个 OrgUnit 找到其归属的 (DEPT id, DEPT name)。

    向上回溯 parent 链直到 type=DEPT 的祖先 (含自身)。
    返回 {org_unit_id: (dept_id, dept_name)}。无 DEPT 祖先则不在 map 中。
    """
    units = {u.id: u for u in OrgUnit.objects.all().only("id", "type", "name", "parent_id")}
    result: dict[int, tuple[int, str]] = {}
    for uid, u in units.items():
        cursor = u
        seen: set[int] = set()
        while cursor is not None and cursor.id not in seen:
            seen.add(cursor.id)
            if cursor.type == "DEPT":
                result[uid] = (cursor.id, cursor.name)
                break
            cursor = units.get(cursor.parent_id) if cursor.parent_id else None
    return result


def derive_budget(cycle: RewardCycle) -> dict:
    """返回派生预算: 部门池 + 切片明细 + 摘要。

    返回结构:
    {
      "departments": [
        {department_id, department_name, employee_count,
         derived_annual_cny, derived_promotion_cny, derived_total_cny,
         override_annual_cny | None, override_promotion_cny | None,
         effective_annual_cny, effective_promotion_cny, effective_total_cny,
         annual_source, promotion_source,  # DERIVED / IMPORTED
         has_missing_rule, has_missing_factor}, ...
      ],
      "rows": [...切片同前...],
      "total_derived_cny": Decimal,        # 仅切片求和
      "total_effective_cny": Decimal,      # 应用 override 后
      "skipped_no_salary_count": int,
      "skipped_no_country_count": int,
      "employee_total": int,
    }
    """
    scheme = cycle.category_scheme
    if scheme is None:
        return {
            "departments": [],
            "rows": [],
            "total_derived_cny": Decimal("0"),
            "total_effective_cny": Decimal("0"),
            "skipped_no_salary_count": 0,
            "skipped_no_country_count": 0,
            "employee_total": 0,
        }

    rules_by: dict[tuple[str, str], Decimal] = {}
    for r in RegionalAdjustmentRule.objects.filter(reward_cycle=cycle):
        rules_by[(r.country, r.adjustment_type)] = r.base_pct

    factors_by: dict[tuple[int, str], Decimal] = {}
    for f in EmployeeCategoryFactor.objects.filter(reward_cycle=cycle):
        factors_by[(f.category_id, f.adjustment_type)] = f.factor

    dept_lookup = _build_dept_lookup()

    assignments = list(
        EmployeeCategoryAssignment.objects
        .filter(scheme=scheme, employee__status="ACTIVE")
        .select_related("employee", "category", "employee__legal_entity", "employee__org_unit")
    )
    employee_ids = [a.employee_id for a in assignments]
    salary_map = _latest_monthly_salary_map(employee_ids)

    # 切片 buckets, key = (dept_id_or_None, country, category_id, adj)
    buckets: dict[tuple, dict] = {}
    # 部门聚合, key = dept_id_or_None
    dept_agg: dict = {}
    skipped_no_salary = 0
    skipped_no_country = 0

    for a in assignments:
        emp = a.employee
        cat = a.category
        salary = salary_map.get(emp.id)
        if salary is None:
            skipped_no_salary += 1
            continue
        country = emp.legal_entity.country if emp.legal_entity else None
        if not country:
            skipped_no_country += 1
            continue

        if emp.org_unit_id and emp.org_unit_id in dept_lookup:
            dept_id, dept_name = dept_lookup[emp.org_unit_id]
        else:
            dept_id, dept_name = None, "未分配部门"

        # 部门聚合：每位员工按部门去重计数
        d = dept_agg.get(dept_id)
        if d is None:
            d = {
                "department_id": dept_id,
                "department_name": dept_name,
                "employee_ids": set(),
                "annual_amount_cny": Decimal("0"),
                "promotion_amount_cny": Decimal("0"),
                "has_missing_rule": False,
                "has_missing_factor": False,
            }
            dept_agg[dept_id] = d
        d["employee_ids"].add(emp.id)

        for adj in ADJ_TYPES:
            if adj == "ANNUAL" and not emp.participates_annual_adjustment:
                continue
            if adj == "PROMOTION" and not emp.is_promoted:
                continue

            key = (dept_id, country, cat.id, adj)
            bucket = buckets.get(key)
            if bucket is None:
                base_pct = rules_by.get((country, adj))
                factor = factors_by.get((cat.id, adj))
                bucket = {
                    "department_id": dept_id,
                    "department_name": dept_name,
                    "country": country,
                    "category_id": cat.id,
                    "category_code": cat.code,
                    "category_name": cat.name,
                    "category_sort_order": cat.sort_order,
                    "adjustment_type": adj,
                    "employee_count": 0,
                    "salary_sum_cny": Decimal("0"),
                    "base_pct": base_pct,
                    "factor": factor,
                    "derived_amount_cny": Decimal("0"),
                    "missing_rule": base_pct is None,
                    "missing_factor": factor is None,
                }
                buckets[key] = bucket

            bucket["employee_count"] += 1
            bucket["salary_sum_cny"] += salary

            if bucket["base_pct"] is None or bucket["factor"] is None:
                if bucket["missing_rule"]:
                    d["has_missing_rule"] = True
                if bucket["missing_factor"]:
                    d["has_missing_factor"] = True
                continue

            inc = salary * bucket["base_pct"] * bucket["factor"]
            bucket["derived_amount_cny"] += inc
            if adj == "ANNUAL":
                d["annual_amount_cny"] += inc
            else:
                d["promotion_amount_cny"] += inc

    rows = sorted(
        buckets.values(),
        key=lambda r: (
            r["department_name"],
            r["country"],
            r["category_sort_order"],
            r["adjustment_type"],
        ),
    )
    for r in rows:
        r.pop("category_sort_order", None)
        r["derived_amount_cny"] = r["derived_amount_cny"].quantize(Decimal("0.01"))
        r["salary_sum_cny"] = r["salary_sum_cny"].quantize(Decimal("0.01"))

    overrides_by: dict[tuple[int, str], Decimal] = {}
    for ov in BudgetOverride.objects.filter(reward_cycle=cycle):
        overrides_by[(ov.department_id, ov.adjustment_type)] = ov.override_amount_cny

    departments = []
    total_effective = Decimal("0")
    total_matrix = Decimal("0")
    total_discretionary = Decimal("0")
    dpct = (cycle.discretionary_pct or Decimal("0")).quantize(Decimal("0.0001"))
    matrix_pct = Decimal("1") - dpct
    for d in dept_agg.values():
        derived_annual = d["annual_amount_cny"].quantize(Decimal("0.01"))
        derived_promo = d["promotion_amount_cny"].quantize(Decimal("0.01"))
        dept_id = d["department_id"]

        ov_annual = overrides_by.get((dept_id, "ANNUAL")) if dept_id is not None else None
        ov_promo = overrides_by.get((dept_id, "PROMOTION")) if dept_id is not None else None

        eff_annual = ov_annual if ov_annual is not None else derived_annual
        eff_promo = ov_promo if ov_promo is not None else derived_promo
        eff_total = (eff_annual + eff_promo).quantize(Decimal("0.01"))
        total_effective += eff_total

        # 90/10 分池：每个 (dept, adj_type) 的 effective 拆成矩阵/机动盘
        matrix_annual = (eff_annual * matrix_pct).quantize(Decimal("0.01"))
        discretionary_annual = (eff_annual - matrix_annual).quantize(Decimal("0.01"))
        matrix_promo = (eff_promo * matrix_pct).quantize(Decimal("0.01"))
        discretionary_promo = (eff_promo - matrix_promo).quantize(Decimal("0.01"))
        matrix_pool = (matrix_annual + matrix_promo).quantize(Decimal("0.01"))
        discretionary_pool = (discretionary_annual + discretionary_promo).quantize(Decimal("0.01"))
        total_matrix += matrix_pool
        total_discretionary += discretionary_pool

        departments.append({
            "department_id": dept_id,
            "department_name": d["department_name"],
            "employee_count": len(d["employee_ids"]),
            "derived_annual_cny": derived_annual,
            "derived_promotion_cny": derived_promo,
            "derived_total_cny": (derived_annual + derived_promo).quantize(Decimal("0.01")),
            "override_annual_cny": ov_annual.quantize(Decimal("0.01")) if ov_annual is not None else None,
            "override_promotion_cny": ov_promo.quantize(Decimal("0.01")) if ov_promo is not None else None,
            "effective_annual_cny": eff_annual.quantize(Decimal("0.01")),
            "effective_promotion_cny": eff_promo.quantize(Decimal("0.01")),
            "effective_total_cny": eff_total,
            "matrix_annual_cny": matrix_annual,
            "matrix_promotion_cny": matrix_promo,
            "matrix_pool_cny": matrix_pool,
            "discretionary_annual_cny": discretionary_annual,
            "discretionary_promotion_cny": discretionary_promo,
            "discretionary_pool_cny": discretionary_pool,
            "annual_source": "IMPORTED" if ov_annual is not None else "DERIVED",
            "promotion_source": "IMPORTED" if ov_promo is not None else "DERIVED",
            "has_missing_rule": d["has_missing_rule"],
            "has_missing_factor": d["has_missing_factor"],
        })
    departments.sort(
        key=lambda x: (
            x["department_id"] is None,  # 未分配部门排最后
            x["department_name"],
        )
    )

    total_derived = sum((r["derived_amount_cny"] for r in rows), Decimal("0"))

    return {
        "departments": departments,
        "rows": rows,
        "total_derived_cny": total_derived,
        "total_effective_cny": total_effective.quantize(Decimal("0.01")),
        "total_matrix_cny": total_matrix.quantize(Decimal("0.01")),
        "total_discretionary_cny": total_discretionary.quantize(Decimal("0.01")),
        "discretionary_pct": dpct,
        "skipped_no_salary_count": skipped_no_salary,
        "skipped_no_country_count": skipped_no_country,
        "employee_total": len(assignments),
    }
