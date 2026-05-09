from decimal import Decimal
from collections import defaultdict
from django.db import transaction
from apps.hr_master.models import Employee, PerformanceRating
from apps.compensation_plan.models import AdjustmentPlan, AdjustmentProposal
from apps.lti.models import LTIPlan, LTIGrant
from apps.reward_cycle.models import RewardCycle


PROMOTION_PCT_BY_TARGET = {"P2": "0.15", "P3": "0.12", "P4": "0.10", "P5": "0.10",
                           "P6": "0.10", "P7": "0.10"}


def _annual_suggested_pct(emp: Employee) -> Decimal:
    return Decimal("0.05")


def _promotion_pct(emp: Employee) -> Decimal:
    if not emp.is_promoted or not emp.job_level_promoted:
        return Decimal("0")
    return Decimal(PROMOTION_PCT_BY_TARGET.get(emp.job_level_promoted, "0.10"))


def _latest_monthly_salary(emp: Employee) -> Decimal:
    rec = emp.compensation_records.order_by("-effective_date").first()
    return rec.monthly_salary if rec else Decimal("0")


def _budget_year(cycle: RewardCycle):
    scope = cycle.scope or {}
    if "budget_year" in scope:
        try:
            return int(scope["budget_year"])
        except (ValueError, TypeError):
            pass
    try:
        return int(str(cycle.period)[:4])
    except (ValueError, TypeError):
        return None


@transaction.atomic
def generate_proposals(cycle: RewardCycle, adj_plan: AdjustmentPlan, lti_plan: LTIPlan):
    """Create one AdjustmentProposal per in-scope employee; LTIGrant for eligible."""
    for emp in Employee.objects.filter(status="ACTIVE"):
        AdjustmentProposal.objects.get_or_create(
            plan=adj_plan, employee=emp,
            defaults={
                "annual_suggested_pct": _annual_suggested_pct(emp) if emp.participates_annual_adjustment else Decimal("0"),
                "annual_manager_delta_pct": Decimal("0"),
                "promotion_adjustment_pct": _promotion_pct(emp),
                "current_salary": _latest_monthly_salary(emp),
                "current_job_level_snapshot": emp.job_level_current,
                "job_level_promoted_snapshot": emp.job_level_promoted,
                "employee_category_1_snapshot": emp.employee_category_1,
                "participates_annual_snapshot": emp.participates_annual_adjustment,
            },
        )
        LTIGrant.objects.get_or_create(
            plan=lti_plan, employee=emp,
            defaults={
                "granted_ads": 0,
                "unit_price_at_grant": lti_plan.unit_price_at_grant,
                "employee_category_1_snapshot": emp.employee_category_1,
                "stock_code": lti_plan.stock_code,
            },
        )


def _load_perf_y_minus_1(cycle: RewardCycle):
    """Return {employee_id: {"y_minus_1_h1": rating, "y_minus_1_h2": rating}}."""
    by = _budget_year(cycle)
    if by is None:
        return {}
    target_year = by - 1
    out = defaultdict(dict)
    qs = PerformanceRating.objects.filter(period_year=target_year)
    for r in qs:
        key = "y_minus_1_h1" if r.period_half == "H1" else "y_minus_1_h2"
        out[r.employee_id][key] = r.rating
    return out


def get_allocation_rows(cycle: RewardCycle):
    adj = cycle.linked_adjustment_plan
    lti = cycle.linked_lti_plan
    proposals = {p.employee_id: p for p in AdjustmentProposal.objects.filter(plan=adj)} if adj else {}
    grants = {g.employee_id: g for g in LTIGrant.objects.filter(plan=lti)} if lti else {}
    perf = _load_perf_y_minus_1(cycle)
    rows = []
    for emp in Employee.objects.filter(status="ACTIVE").order_by("employee_no"):
        rows.append({"employee": emp,
                     "proposal": proposals.get(emp.id),
                     "grant": grants.get(emp.id),
                     "perf": perf.get(emp.id, {})})
    return rows
