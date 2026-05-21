from decimal import Decimal

from apps.analytics.models import EmployeeCompensationSnapshot

FIVE_COLS = (
    "annual_fixed_cny",
    "annual_bonus_cny",
    "annual_cash_cny",
    "annual_rsu_value_cny",
    "annual_total_comp_cny",
)


def _resolve_snapshot(employee_id: int, year: int):
    """同一员工同一年优先 ACTUAL，否则取 PROJECTED；都没就抛 LookupError。"""
    qs = EmployeeCompensationSnapshot.objects.filter(
        employee_id=employee_id, year=year
    )
    snap = qs.filter(snapshot_kind="ACTUAL").first() or qs.filter(
        snapshot_kind="PROJECTED"
    ).first()
    if snap is None:
        raise LookupError(f"no snapshot for emp={employee_id} year={year}")
    return snap


def compute_5col_delta(employee_id: int, year_from: int, year_to: int):
    """返回 5 列各自的 Δ% (Decimal, 4 位小数)；分母 0 时返回 None。"""
    a = _resolve_snapshot(employee_id, year_from)
    b = _resolve_snapshot(employee_id, year_to)
    out = {}
    for col in FIVE_COLS:
        base = Decimal(getattr(a, col) or 0)
        target = Decimal(getattr(b, col) or 0)
        if base == 0:
            out[col] = None
        else:
            out[col] = ((target - base) / base).quantize(Decimal("0.0001"))
    return out
