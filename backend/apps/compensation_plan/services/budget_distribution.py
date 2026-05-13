"""预算下发计算器：把公司层总额按规则切到目标 OrgUnit 集合。

三种规则：
- MANUAL：直接用调用者给的金额，仅校验 sum
- HEADCOUNT：按目标单元下符合 cat1 的活跃员工人数加权
- SALARY_TOTAL：按目标单元下符合 cat1 的员工最新月薪 × 12 总额加权

舍入误差归到权重最大的目标，确保 Σ targets == total。
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Iterable

from apps.hr_master.models import Employee, CompensationRecord
from apps.compensation_plan.services.org_targets import members_under


MODES = ("MANUAL", "HEADCOUNT", "SALARY_TOTAL")


def _quantize_decimal(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _headcount_weight(unit_id: int, cat1: str) -> int:
    return members_under(unit_id).filter(
        employee_category_1=cat1, status="ACTIVE"
    ).count()


def _salary_total_weight(unit_id: int, cat1: str) -> Decimal:
    emp_ids = list(
        members_under(unit_id)
        .filter(employee_category_1=cat1, status="ACTIVE")
        .values_list("id", flat=True)
    )
    if not emp_ids:
        return Decimal("0")
    total = Decimal("0")
    for eid in emp_ids:
        rec = (
            CompensationRecord.objects.filter(employee_id=eid)
            .order_by("-effective_date", "-version")
            .first()
        )
        if rec:
            total += rec.monthly_salary * 12
    return total


def compute_distribution(
    *,
    total: Decimal,
    cat1: str,
    mode: str,
    target_unit_ids: Iterable[int],
    manual_amounts: dict | None = None,
    integer_units: bool = False,
) -> dict[int, Decimal]:
    """返回 {ou_id: amount}。total 为公司层预算总额。

    integer_units=True 时所有金额量整为整数（用于 LTI 股数 ADS）。
    """
    if mode not in MODES:
        raise ValueError(f"invalid mode {mode!r}, expected one of {MODES}")
    target_ids = [int(i) for i in target_unit_ids]
    if not target_ids:
        return {}

    if mode == "MANUAL":
        if not manual_amounts:
            raise ValueError("MANUAL mode requires manual_amounts dict")
        out: dict[int, Decimal] = {}
        for tid in target_ids:
            v = manual_amounts.get(tid, manual_amounts.get(str(tid), 0))
            out[tid] = Decimal(str(v))
        s = sum(out.values(), Decimal("0"))
        if s > total:
            raise ValueError(f"manual sum {s} exceeds company total {total}")
        return _round_dict(out, integer_units)

    weight_fn: Callable[[int, str], Decimal | int]
    if mode == "HEADCOUNT":
        weight_fn = _headcount_weight
    else:  # SALARY_TOTAL
        weight_fn = _salary_total_weight

    weights = {tid: Decimal(str(weight_fn(tid, cat1))) for tid in target_ids}
    weight_sum = sum(weights.values(), Decimal("0"))
    if weight_sum == 0:
        even = total / Decimal(len(target_ids))
        out = {tid: even for tid in target_ids}
        return _round_dict(out, integer_units, total=total)

    out = {tid: total * w / weight_sum for tid, w in weights.items()}
    return _round_dict(out, integer_units, total=total, weights=weights)


def _round_dict(
    raw: dict[int, Decimal],
    integer_units: bool,
    total: Decimal | None = None,
    weights: dict[int, Decimal] | None = None,
) -> dict[int, Decimal]:
    if integer_units:
        rounded = {k: Decimal(int(v)) for k, v in raw.items()}
    else:
        rounded = {k: _quantize_decimal(v) for k, v in raw.items()}
    if total is None:
        return rounded
    drift = total - sum(rounded.values(), Decimal("0"))
    if drift == 0:
        return rounded
    if weights:
        anchor = max(weights, key=lambda k: weights[k])
    else:
        anchor = max(rounded, key=lambda k: rounded[k])
    rounded[anchor] = rounded[anchor] + drift
    if integer_units:
        rounded[anchor] = Decimal(int(rounded[anchor]))
    return rounded
