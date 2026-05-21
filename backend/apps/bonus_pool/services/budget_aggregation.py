"""按"归属目标 OrgUnit"聚合年终奖提案的实时金额。

不依赖 BonusBudgetCell.allocated_amount_cny 字段（生产代码从未写入），
每次 cap 校验和 GET 都重算。对标 compensation_plan/budget_aggregation。
"""
from collections import defaultdict
from decimal import Decimal

from apps.bonus_pool.models import BonusBudgetCell, BonusProposal
from apps.compensation_plan.services.org_targets import resolve_owning_target


def _bonus_target_ids_for(cycle, cat1: str) -> set[int]:
    return set(
        BonusBudgetCell.objects.filter(
            reward_cycle=cycle,
            employee_category_1=cat1,
            target_org_unit__isnull=False,
        ).values_list("target_org_unit_id", flat=True)
    )


def aggregate_bonus_allocated(cycle) -> dict[tuple[int, str], Decimal]:
    """返回 {(ou_id, cat1): Decimal_amount}。

    口径：suggested_amount_cny + manager_delta_amount_cny
    """
    out: dict[tuple[int, str], Decimal] = defaultdict(lambda: Decimal("0"))
    plan = getattr(cycle, "linked_bonus_plan", None)
    if not plan:
        return dict(out)

    proposals = BonusProposal.objects.filter(plan=plan).select_related("employee")
    for cat1 in ("MANAGEMENT", "STAFF"):
        target_ids = _bonus_target_ids_for(cycle, cat1)
        if not target_ids:
            continue
        for p in proposals:
            if p.employee_category_1_snapshot != cat1:
                continue
            ou = resolve_owning_target(p.employee, target_ids)
            if ou is None:
                continue
            amount = (p.suggested_amount_cny or Decimal("0")) + (
                p.manager_delta_amount_cny or Decimal("0")
            )
            out[(ou, cat1)] += Decimal(amount)
    return dict(out)
