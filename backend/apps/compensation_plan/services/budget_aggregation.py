"""按"归属目标 OrgUnit"聚合提案 / LTI 授予的实时金额、股数。

不依赖 AdjustmentBudgetCell.allocated_amount_cny 字段（生产代码从未写入），
每次 cap 校验和 GET 都重算，避免 denormalized 计数器与提案漂移。
"""
from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from apps.compensation_plan.models import AdjustmentBudgetCell, AdjustmentProposal
from apps.compensation_plan.services.org_targets import resolve_owning_target
from apps.hr_master.models import Employee
from apps.lti.models import LTIBudgetCell, LTIGrant


def _adjustment_target_ids_for(cycle, adj_type: str, cat1: str) -> set[int]:
    return set(
        AdjustmentBudgetCell.objects.filter(
            reward_cycle=cycle,
            adjustment_type=adj_type,
            employee_category_1=cat1,
            department__isnull=False,
        ).values_list("department_id", flat=True)
    )


def aggregate_adjustment_allocated(cycle) -> dict[tuple[int, str, str], Decimal]:
    """返回 {(ou_id, adj_type, cat1): Decimal_amount}。

    口径：
    - ANNUAL：current_salary × (annual_suggested_pct + annual_manager_delta_pct) × 12
    - PROMOTION：promotion_adjustment_amount_cny
    """
    out: dict[tuple[int, str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    plan = cycle.linked_adjustment_plan if hasattr(cycle, "linked_adjustment_plan") else None
    if not plan:
        return dict(out)

    proposals = AdjustmentProposal.objects.filter(plan=plan).select_related("employee")
    for adj_type in ("ANNUAL", "PROMOTION"):
        for cat1 in ("MANAGEMENT", "STAFF"):
            target_ids = _adjustment_target_ids_for(cycle, adj_type, cat1)
            if not target_ids:
                continue
            for p in proposals:
                if p.employee_category_1_snapshot != cat1:
                    continue
                ou = resolve_owning_target(p.employee, target_ids)
                if ou is None:
                    continue
                if adj_type == "ANNUAL":
                    pct = p.annual_suggested_pct + p.annual_manager_delta_pct
                    amount = (p.current_salary * pct) * 12
                else:
                    amount = p.promotion_adjustment_amount_cny
                out[(ou, adj_type, cat1)] += Decimal(amount)
    return dict(out)


def _lti_target_ids_for(plan, cat1: str) -> set[int]:
    return set(
        LTIBudgetCell.objects.filter(
            plan=plan,
            employee_category_1=cat1,
            target_org_unit__isnull=False,
        ).values_list("target_org_unit_id", flat=True)
    )


def aggregate_lti_allocated(plan) -> dict[tuple[int, str], int]:
    """返回 {(ou_id, cat1): granted_ads_total}。"""
    out: dict[tuple[int, str], int] = defaultdict(int)
    grants = LTIGrant.objects.filter(plan=plan).select_related("employee")
    for cat1 in ("MANAGEMENT", "STAFF"):
        target_ids = _lti_target_ids_for(plan, cat1)
        if not target_ids:
            continue
        for g in grants:
            if g.employee_category_1_snapshot != cat1:
                continue
            ou = resolve_owning_target(g.employee, target_ids)
            if ou is None:
                continue
            out[(ou, cat1)] += int(g.granted_ads or 0)
    return dict(out)
