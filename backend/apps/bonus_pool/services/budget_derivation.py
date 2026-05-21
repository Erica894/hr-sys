"""年终奖派生预算 service: 部门池 + (国家×员工类别) 切片。

派生模型 (对标调薪 budget_derivation):
  - 部门池为预算下发的真实单位 (层 2)
  - 派生值 (DERIVED) = Σ(切片) = Σ(monthly_salary × base_months × factor)
  - 兜底覆盖 (IMPORTED) = HR 通过 BonusBudgetOverride 覆盖派生值, 逐部门生效

部门归属:
  - 员工的 department = 沿 employee.org_unit.parent 向上找到最近的 type=DEPT 节点
  - 找不到 → 记入"未分配部门"伪桶 (department_id=None, 不可被 override)
"""
from decimal import Decimal
from typing import Iterable

from apps.bonus_pool.models import (
    BonusBudgetOverride,
    BonusCategoryFactor,
    RegionalBonusRule,
)
from apps.hr_master.models import CompensationRecord, Employee
from apps.iam.models import OrgUnit
from apps.reward_cycle.models import RewardCycle


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


def derive_bonus_budget(cycle: RewardCycle) -> dict:
    """返回派生预算: 部门池 + 切片明细 + 摘要。

    返回结构:
    {
      "departments": [
        {department_id, department_name, employee_count,
         derived_amount_cny,
         override_amount_cny | None,
         effective_amount_cny,
         source,              # DERIVED / IMPORTED
         has_missing_rule, has_missing_factor}, ...
      ],
      "rows": [{department_id, department_name, country,
                employee_category_1, employee_count,
                salary_sum_cny, base_months, factor,
                derived_amount_cny, missing_rule, missing_factor}, ...],
      "total_derived_cny": Decimal,
      "total_effective_cny": Decimal,
      "skipped_no_salary_count": int,
      "skipped_no_country_count": int,
      "employee_total": int,
    }
    """
    rules_by: dict[str, Decimal] = {}
    for r in RegionalBonusRule.objects.filter(reward_cycle=cycle):
        rules_by[r.country] = r.base_months

    factors_by: dict[str, Decimal] = {}
    for f in BonusCategoryFactor.objects.filter(reward_cycle=cycle):
        factors_by[f.employee_category_1] = f.factor

    dept_lookup = _build_dept_lookup()

    employees = list(
        Employee.objects.filter(status="ACTIVE")
        .select_related("legal_entity", "org_unit")
    )
    employee_ids = [e.id for e in employees]
    salary_map = _latest_monthly_salary_map(employee_ids)

    # 切片 buckets, key = (dept_id_or_None, country, cat1)
    buckets: dict[tuple, dict] = {}
    # 部门聚合, key = dept_id_or_None
    dept_agg: dict = {}
    skipped_no_salary = 0
    skipped_no_country = 0

    for emp in employees:
        salary = salary_map.get(emp.id)
        if salary is None:
            skipped_no_salary += 1
            continue
        country = emp.legal_entity.country if emp.legal_entity else None
        if not country:
            skipped_no_country += 1
            continue

        cat1 = emp.employee_category_1 or "STAFF"

        if emp.org_unit_id and emp.org_unit_id in dept_lookup:
            dept_id, dept_name = dept_lookup[emp.org_unit_id]
        else:
            dept_id, dept_name = None, "未分配部门"

        d = dept_agg.get(dept_id)
        if d is None:
            d = {
                "department_id": dept_id,
                "department_name": dept_name,
                "employee_ids": set(),
                "amount_cny": Decimal("0"),
                "has_missing_rule": False,
                "has_missing_factor": False,
            }
            dept_agg[dept_id] = d
        d["employee_ids"].add(emp.id)

        key = (dept_id, country, cat1)
        bucket = buckets.get(key)
        if bucket is None:
            base_months = rules_by.get(country)
            factor = factors_by.get(cat1)
            bucket = {
                "department_id": dept_id,
                "department_name": dept_name,
                "country": country,
                "employee_category_1": cat1,
                "employee_count": 0,
                "salary_sum_cny": Decimal("0"),
                "base_months": base_months,
                "factor": factor,
                "derived_amount_cny": Decimal("0"),
                "missing_rule": base_months is None,
                "missing_factor": factor is None,
            }
            buckets[key] = bucket

        bucket["employee_count"] += 1
        bucket["salary_sum_cny"] += salary

        if bucket["base_months"] is None or bucket["factor"] is None:
            if bucket["missing_rule"]:
                d["has_missing_rule"] = True
            if bucket["missing_factor"]:
                d["has_missing_factor"] = True
            continue

        inc = salary * bucket["base_months"] * bucket["factor"]
        bucket["derived_amount_cny"] += inc
        d["amount_cny"] += inc

    rows = sorted(
        buckets.values(),
        key=lambda r: (r["department_name"], r["country"], r["employee_category_1"]),
    )
    for r in rows:
        r["derived_amount_cny"] = r["derived_amount_cny"].quantize(Decimal("0.01"))
        r["salary_sum_cny"] = r["salary_sum_cny"].quantize(Decimal("0.01"))

    overrides_by: dict[int, Decimal] = {}
    for ov in BonusBudgetOverride.objects.filter(reward_cycle=cycle):
        overrides_by[ov.department_id] = ov.override_amount_cny

    departments = []
    total_effective = Decimal("0")
    for d in dept_agg.values():
        derived = d["amount_cny"].quantize(Decimal("0.01"))
        dept_id = d["department_id"]
        ov = overrides_by.get(dept_id) if dept_id is not None else None
        eff = ov if ov is not None else derived
        total_effective += eff
        departments.append({
            "department_id": dept_id,
            "department_name": d["department_name"],
            "employee_count": len(d["employee_ids"]),
            "derived_amount_cny": derived,
            "override_amount_cny": ov.quantize(Decimal("0.01")) if ov is not None else None,
            "effective_amount_cny": eff.quantize(Decimal("0.01")),
            "source": "IMPORTED" if ov is not None else "DERIVED",
            "has_missing_rule": d["has_missing_rule"],
            "has_missing_factor": d["has_missing_factor"],
        })
    departments.sort(
        key=lambda x: (x["department_id"] is None, x["department_name"])
    )

    total_derived = sum((r["derived_amount_cny"] for r in rows), Decimal("0"))

    return {
        "departments": departments,
        "rows": rows,
        "total_derived_cny": total_derived,
        "total_effective_cny": total_effective.quantize(Decimal("0.01")),
        "skipped_no_salary_count": skipped_no_salary,
        "skipped_no_country_count": skipped_no_country,
        "employee_total": len(employees),
    }
