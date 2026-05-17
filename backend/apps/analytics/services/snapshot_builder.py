"""派生 EmployeeCompensationSnapshot — 5 列年度总包(CNY)。

口径(plan A2b):
- months = emp.effective_pay_months_per_year
- annual_fixed_local = 最新 CompensationRecord(effective_date <= year-12-31).monthly_salary × months
- annual_fixed_cny = fx.convert(annual_fixed_local, emp.pay_currency, "CNY", f"{year}-12")
- annual_bonus_cny = 0 (派生路径下置 0；由 import_historical_snapshots 补 Y/Y-1 实发奖金)
- annual_cash_cny = annual_fixed_cny + annual_bonus_cny
- annual_rsu_value_cny = Σ(pending_shares_by_year[year] × StockPrice[stock, f"{year}-03"].closing_price
                           × fx.convert(1, price.currency, "CNY", f"{year}-03"))
- annual_total_comp_cny = annual_cash_cny + annual_rsu_value_cny
- 一并冻结 perf_grade_code / pay_band / employee_category_1 / org_unit_id
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.analytics.services.fx import convert
from apps.hr_master.models import CompensationRecord, Employee, PerformanceRating
from apps.lti.models import LTIGrant, StockPriceMonthly


def _latest_comp_record(employee: Employee, year: int) -> CompensationRecord | None:
    return (
        CompensationRecord.objects
        .filter(employee=employee, effective_date__lte=date(year, 12, 31))
        .order_by("-effective_date", "-version")
        .first()
    )


def _annual_fixed_cny(employee: Employee, year: int) -> Decimal:
    rec = _latest_comp_record(employee, year)
    if rec is None:
        return Decimal("0.00")
    months = employee.effective_pay_months_per_year
    annual_local = (rec.monthly_salary * months).quantize(Decimal("0.01"))
    return convert(annual_local, rec.currency or "CNY", "CNY", f"{year}-12")


def _annual_rsu_value_cny(employee: Employee, year: int) -> Decimal:
    total = Decimal("0.00")
    grants = LTIGrant.objects.filter(employee=employee).select_related("plan")
    for grant in grants:
        shares = grant.pending_shares_by_year or {}
        n = shares.get(str(year)) or shares.get(year)
        if not n:
            continue
        stock_code = grant.stock_code or grant.plan.stock_code
        if not stock_code:
            continue
        try:
            price_row = StockPriceMonthly.objects.get(stock_code=stock_code, month=f"{year}-03")
        except StockPriceMonthly.DoesNotExist:
            continue
        price_cny = convert(price_row.closing_price, price_row.currency, "CNY", f"{year}-03")
        total += (Decimal(n) * price_cny).quantize(Decimal("0.01"))
    return total.quantize(Decimal("0.01"))


def _latest_perf_grade(employee: Employee, year: int) -> str:
    pr = (
        PerformanceRating.objects
        .filter(employee=employee, period_year__lte=year)
        .order_by("-period_year", "-period_half")
        .first()
    )
    return pr.rating if pr else ""


@transaction.atomic
def build_snapshot_for_employee(
    employee: Employee, year: int, snapshot_kind: str = "ACTUAL", cycle=None
) -> EmployeeCompensationSnapshot:
    fixed_cny = _annual_fixed_cny(employee, year)
    bonus_cny = Decimal("0.00")
    rsu_cny = _annual_rsu_value_cny(employee, year)
    cash_cny = fixed_cny + bonus_cny
    total_cny = cash_cny + rsu_cny

    snap, _ = EmployeeCompensationSnapshot.objects.update_or_create(
        employee=employee, year=year, snapshot_kind=snapshot_kind,
        defaults=dict(
            annual_fixed_cny=fixed_cny,
            annual_bonus_cny=bonus_cny,
            annual_cash_cny=cash_cny,
            annual_rsu_value_cny=rsu_cny,
            annual_total_comp_cny=total_cny,
            perf_grade_code=_latest_perf_grade(employee, year),
            pay_band="",
            employee_category_1_snapshot=employee.employee_category_1 or "",
            org_unit_snapshot_id=employee.org_unit_id,
            source="DERIVED",
            derived_from_cycle=cycle,
        ),
    )
    return snap


def build_for_cycle(cycle, year: int, snapshot_kind: str = "ACTUAL") -> int:
    """对 cycle 范围内全部 active 员工派生快照，返回写入条数。"""
    qs = Employee.objects.filter(status="ACTIVE")
    n = 0
    for emp in qs.iterator():
        build_snapshot_for_employee(emp, year, snapshot_kind, cycle=cycle)
        n += 1
    return n
