"""保存提案前的预算 cap 校验。

输入：cycle + 一组拟改动的 items（含 annual_manager_delta_pct / granted_ads）。
输出：违反列表 [{ou_id, adj_type, cat1, requested, budget}, ...]，空 list 表示通过。

实现思路（避免落库后回滚）：
- 拉出该 cycle 的所有 AdjustmentProposal，把待改 delta 应用到内存副本
- 用 owning_target 把每条提案归到目标 OrgUnit
- 按 (target_ou, adj_type, cat1) 聚合"应付金额"
- 与对应 AdjustmentBudgetCell.budget_amount_cny 比对

兜底：若该 (cycle, adj_type, cat1) 还没有任何目标层 cell（HR 未下发），
回退到公司层 cell 校验（保护早期未下发的演示流程）。
"""
from decimal import Decimal
from collections import defaultdict
from typing import Iterable

from apps.compensation_plan.models import AdjustmentBudgetCell, AdjustmentProposal
from apps.compensation_plan.services.org_targets import resolve_owning_target


def _index_target_budgets_adj(cycle):
    out: dict[tuple[int, str, str], Decimal] = {}
    for c in AdjustmentBudgetCell.objects.filter(
        reward_cycle=cycle, department__isnull=False
    ):
        out[(c.department_id, c.adjustment_type, c.employee_category_1)] = c.budget_amount_cny
    return out


def _index_company_budgets_adj(cycle):
    out: dict[tuple[str, str], Decimal] = {}
    for c in AdjustmentBudgetCell.objects.filter(
        reward_cycle=cycle, department__isnull=True
    ):
        out[(c.adjustment_type, c.employee_category_1)] = c.budget_amount_cny
    return out


def check_adjustment_cap(cycle, items: Iterable[dict]):
    """items 形如 [{"employee_id": int, "annual_manager_delta_pct": Decimal}]，未带的字段忽略。

    返回违反列表。空 list 表示 OK。
    """
    plan = cycle.linked_adjustment_plan
    if plan is None:
        return []

    overrides = {
        int(it["employee_id"]): Decimal(str(it["annual_manager_delta_pct"]))
        for it in items
        if "annual_manager_delta_pct" in it and it.get("employee_id") is not None
    }

    proposals = list(
        AdjustmentProposal.objects.filter(plan=plan).select_related("employee")
    )

    target_budgets = _index_target_budgets_adj(cycle)

    target_ids_by_key: dict[tuple[str, str], set[int]] = defaultdict(set)
    for (ou_id, adj, cat) in target_budgets:
        target_ids_by_key[(adj, cat)].add(ou_id)

    sums: dict[tuple[int, str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    company_sums: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))

    for p in proposals:
        cat = p.employee_category_1_snapshot
        delta = overrides.get(p.employee_id, p.annual_manager_delta_pct)
        annual_amount = (p.current_salary * (p.annual_suggested_pct + delta)) * 12
        promo_amount = p.promotion_adjustment_amount_cny

        for adj, amount in (("ANNUAL", annual_amount), ("PROMOTION", promo_amount)):
            if amount <= 0:
                continue
            tids = target_ids_by_key.get((adj, cat), set())
            if tids:
                ou = resolve_owning_target(p.employee, tids)
                if ou is not None:
                    sums[(ou, adj, cat)] += Decimal(amount)
            else:
                company_sums[(adj, cat)] += Decimal(amount)

    violations = []
    for (ou_id, adj, cat), amt in sums.items():
        budget = target_budgets.get((ou_id, adj, cat), Decimal("0"))
        if amt > budget:
            violations.append({
                "level": "TARGET",
                "target_org_unit_id": ou_id,
                "adjustment_type": adj,
                "employee_category_1": cat,
                "requested": str(amt.quantize(Decimal('0.01'))),
                "budget": str(budget),
            })

    if company_sums:
        company_budgets = _index_company_budgets_adj(cycle)
        for (adj, cat), amt in company_sums.items():
            budget = company_budgets.get((adj, cat), Decimal("0"))
            if amt > budget:
                violations.append({
                    "level": "COMPANY",
                    "adjustment_type": adj,
                    "employee_category_1": cat,
                    "requested": str(amt.quantize(Decimal('0.01'))),
                    "budget": str(budget),
                })

    return violations


def _index_target_budgets_lti(plan):
    from apps.lti.models import LTIBudgetCell
    out: dict[tuple[int, str], int] = {}
    for c in LTIBudgetCell.objects.filter(plan=plan, target_org_unit__isnull=False):
        out[(c.target_org_unit_id, c.employee_category_1)] = int(c.shares_quota_ads)
    return out


def _index_company_budgets_lti(plan):
    from apps.lti.models import LTIBudgetCell
    out: dict[str, int] = {}
    for c in LTIBudgetCell.objects.filter(plan=plan, target_org_unit__isnull=True):
        out[c.employee_category_1] = int(c.shares_quota_ads)
    return out


def check_lti_cap(cycle, items: Iterable[dict]):
    """LTI granted_ads dry-run cap check.

    items 形如 [{"employee_id": int, "granted_ads": int}]，未带的字段忽略。
    """
    from apps.lti.models import LTIGrant

    plan = cycle.linked_lti_plan
    if plan is None:
        return []

    overrides = {
        int(it["employee_id"]): int(it["granted_ads"])
        for it in items
        if "granted_ads" in it and it.get("employee_id") is not None
    }

    grants = list(LTIGrant.objects.filter(plan=plan).select_related("employee"))

    target_budgets = _index_target_budgets_lti(plan)

    target_ids_by_cat: dict[str, set[int]] = defaultdict(set)
    for (ou_id, cat) in target_budgets:
        target_ids_by_cat[cat].add(ou_id)

    sums: dict[tuple[int, str], int] = defaultdict(int)
    company_sums: dict[str, int] = defaultdict(int)

    for g in grants:
        cat = g.employee_category_1_snapshot
        shares = overrides.get(g.employee_id, int(g.granted_ads or 0))
        if shares <= 0:
            continue
        tids = target_ids_by_cat.get(cat, set())
        if tids:
            ou = resolve_owning_target(g.employee, tids)
            if ou is not None:
                sums[(ou, cat)] += shares
        else:
            company_sums[cat] += shares

    violations = []
    for (ou_id, cat), used in sums.items():
        budget = target_budgets.get((ou_id, cat), 0)
        if used > budget:
            violations.append({
                "level": "TARGET",
                "target_org_unit_id": ou_id,
                "subject": "LTI",
                "employee_category_1": cat,
                "requested": used,
                "budget": budget,
            })

    if company_sums:
        company_budgets = _index_company_budgets_lti(plan)
        for cat, used in company_sums.items():
            budget = company_budgets.get(cat, 0)
            if used > budget:
                violations.append({
                    "level": "COMPANY",
                    "subject": "LTI",
                    "employee_category_1": cat,
                    "requested": used,
                    "budget": budget,
                })

    return violations


def _index_target_budgets_bonus(cycle):
    from apps.bonus_pool.models import BonusBudgetCell
    out: dict[tuple[int, str], Decimal] = {}
    for c in BonusBudgetCell.objects.filter(reward_cycle=cycle, target_org_unit__isnull=False):
        out[(c.target_org_unit_id, c.employee_category_1)] = c.budget_amount_cny
    return out


def _index_company_budgets_bonus(cycle):
    from apps.bonus_pool.models import BonusBudgetCell
    out: dict[str, Decimal] = {}
    for c in BonusBudgetCell.objects.filter(reward_cycle=cycle, target_org_unit__isnull=True):
        out[c.employee_category_1] = c.budget_amount_cny
    return out


def check_bonus_cap(cycle, items: Iterable[dict]):
    """年终奖 manager_delta_amount_cny dry-run cap check.

    items 形如 [{"employee_id": int, "bonus_manager_delta_amount_cny": Decimal}]。
    """
    from apps.bonus_pool.models import BonusProposal

    plan = getattr(cycle, "linked_bonus_plan", None)
    if plan is None:
        return []

    overrides = {
        int(it["employee_id"]): Decimal(str(it["bonus_manager_delta_amount_cny"]))
        for it in items
        if "bonus_manager_delta_amount_cny" in it and it.get("employee_id") is not None
    }

    proposals = list(BonusProposal.objects.filter(plan=plan).select_related("employee"))

    target_budgets = _index_target_budgets_bonus(cycle)

    target_ids_by_cat: dict[str, set[int]] = defaultdict(set)
    for (ou_id, cat) in target_budgets:
        target_ids_by_cat[cat].add(ou_id)

    sums: dict[tuple[int, str], Decimal] = defaultdict(lambda: Decimal("0"))
    company_sums: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for p in proposals:
        cat = p.employee_category_1_snapshot
        delta = overrides.get(p.employee_id, p.manager_delta_amount_cny)
        amount = (p.suggested_amount_cny or Decimal("0")) + Decimal(delta or 0)
        if amount <= 0:
            continue
        tids = target_ids_by_cat.get(cat, set())
        if tids:
            ou = resolve_owning_target(p.employee, tids)
            if ou is not None:
                sums[(ou, cat)] += Decimal(amount)
        else:
            company_sums[cat] += Decimal(amount)

    violations = []
    for (ou_id, cat), amt in sums.items():
        budget = target_budgets.get((ou_id, cat), Decimal("0"))
        if amt > budget:
            violations.append({
                "level": "TARGET",
                "target_org_unit_id": ou_id,
                "subject": "BONUS",
                "employee_category_1": cat,
                "requested": str(amt.quantize(Decimal('0.01'))),
                "budget": str(budget),
            })

    if company_sums:
        company_budgets = _index_company_budgets_bonus(cycle)
        for cat, amt in company_sums.items():
            budget = company_budgets.get(cat, Decimal("0"))
            if amt > budget:
                violations.append({
                    "level": "COMPANY",
                    "subject": "BONUS",
                    "employee_category_1": cat,
                    "requested": str(amt.quantize(Decimal('0.01'))),
                    "budget": str(budget),
                })

    return violations
