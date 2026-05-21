from datetime import date
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.reward_cycle.models import RewardCycle
from apps.hr_master.models import CompensationRecord
from apps.lti.models import VestingEvent
from apps.audit.services import log_action


def _budget_year(cycle: RewardCycle) -> int:
    # period looks like "2026" or "2026H1"; take leading 4 digits
    return int(str(cycle.period)[:4])


@transaction.atomic
def execute_reward_cycle(cycle: RewardCycle, actor):
    assert cycle.status == "APPROVED_PENDING_EXECUTE", "cycle not approved"
    year = _budget_year(cycle)
    effective = date(year, 1, 1)

    adj_plan = cycle.linked_adjustment_plan
    if adj_plan is not None:
        for p in adj_plan.proposals.select_related("employee"):
            new_salary = Decimal(p.proposed_salary).quantize(Decimal("0.01"))
            latest = (
                CompensationRecord.objects
                .filter(employee=p.employee, superseded_by__isnull=True)
                .order_by("-effective_date")
                .first()
            )
            new_rec = CompensationRecord.objects.create(
                employee=p.employee,
                effective_date=effective,
                base_salary=new_salary,
                monthly_salary=new_salary,
                currency=p.local_currency or "CNY",
                source="REWARD_CYCLE",
                version=(latest.version + 1) if latest else 1,
            )
            if latest:
                latest.superseded_by = new_rec
                latest.save(update_fields=["superseded_by"])

            if p.employee.is_promoted and p.employee.job_level_promoted:
                p.employee.job_level_current = p.employee.job_level_promoted
                p.employee.save(update_fields=["job_level_current"])

            log_action(
                "EXECUTE_SALARY", actor, "Employee", p.employee.id,
                {}, {"new_monthly": str(new_salary), "proposal_id": p.id},
            )

    lti_plan = cycle.linked_lti_plan
    if lti_plan is not None:
        for g in lti_plan.grants.filter(granted_ads__gt=0):
            total = g.granted_ads
            per_year = total // 5
            remainder = total - per_year * 5
            for year_idx in range(1, 6):
                shares = per_year + (remainder if year_idx == 5 else 0)
                vest_date = date(year + year_idx, 4, 1)
                VestingEvent.objects.create(
                    grant=g,
                    scheduled_date=vest_date,
                    scheduled_shares=shares,
                    status="SCHEDULED",
                )
            log_action(
                "EXECUTE_LTI", actor, "LTIGrant", g.id,
                {}, {"granted_ads": total, "vesting_events": 5},
            )

    bonus_plan = getattr(cycle, "linked_bonus_plan", None)
    if bonus_plan is not None:
        from apps.bonus_pool.models import BonusProposal
        for bp in BonusProposal.objects.filter(plan=bonus_plan).select_related("employee"):
            bp.final_amount_cny = (
                Decimal(bp.suggested_amount_cny or 0)
                + Decimal(bp.manager_delta_amount_cny or 0)
            ).quantize(Decimal("0.01"))
            bp.status = "EXECUTED"
            bp.save(update_fields=["final_amount_cny", "status"])
            log_action(
                "EXECUTE_BONUS", actor, "Employee", bp.employee_id,
                {}, {"final_amount_cny": str(bp.final_amount_cny), "proposal_id": bp.id},
            )

    _finalize_adjustment_cells(cycle)
    _finalize_lti_cells(lti_plan)
    _finalize_bonus_cells(cycle)

    cycle.status = "EXECUTED"
    cycle.executed_at = timezone.now()
    cycle.save(update_fields=["status", "executed_at"])
    log_action("EXECUTE", actor, "RewardCycle", cycle.id, {}, {"final_status": "EXECUTED"})


def _finalize_adjustment_cells(cycle):
    """EXECUTE 后将每个目标层 cell 的 allocated/reclaim 固化（仅核算展示用）。"""
    from apps.compensation_plan.models import AdjustmentBudgetCell
    from apps.compensation_plan.services.budget_aggregation import (
        aggregate_adjustment_allocated,
    )

    allocated = aggregate_adjustment_allocated(cycle)
    target_cells = AdjustmentBudgetCell.objects.filter(
        reward_cycle=cycle, department__isnull=False
    )
    for cell in target_cells:
        used = allocated.get(
            (cell.department_id, cell.adjustment_type, cell.employee_category_1),
            Decimal("0"),
        )
        cell.allocated_amount_cny = Decimal(used).quantize(Decimal("0.01"))
        leftover = Decimal(cell.budget_amount_cny) - cell.allocated_amount_cny
        cell.reclaimed_amount_cny = leftover if leftover > 0 else Decimal("0")
        cell.save(update_fields=["allocated_amount_cny", "reclaimed_amount_cny"])


def _finalize_lti_cells(plan):
    """LTI 同上：把 shares_used / reclaim 固化到目标层 cell。"""
    if plan is None:
        return
    from apps.lti.models import LTIBudgetCell
    from apps.compensation_plan.services.budget_aggregation import aggregate_lti_allocated

    allocated = aggregate_lti_allocated(plan)
    for cell in LTIBudgetCell.objects.filter(plan=plan, target_org_unit__isnull=False):
        used = int(allocated.get((cell.target_org_unit_id, cell.employee_category_1), 0))
        cell.shares_used_ads = used
        leftover = int(cell.shares_quota_ads) - used
        cell.reclaimed_shares_ads = leftover if leftover > 0 else 0
        cell.save(update_fields=["shares_used_ads", "reclaimed_shares_ads"])


def _finalize_bonus_cells(cycle):
    """年终奖：把每个目标层 cell 的 allocated/reclaim 固化。"""
    if getattr(cycle, "linked_bonus_plan", None) is None:
        return
    from apps.bonus_pool.models import BonusBudgetCell
    from apps.bonus_pool.services.budget_aggregation import aggregate_bonus_allocated

    allocated = aggregate_bonus_allocated(cycle)
    target_cells = BonusBudgetCell.objects.filter(
        reward_cycle=cycle, target_org_unit__isnull=False,
    )
    for cell in target_cells:
        used = allocated.get(
            (cell.target_org_unit_id, cell.employee_category_1), Decimal("0"),
        )
        cell.allocated_amount_cny = Decimal(used).quantize(Decimal("0.01"))
        leftover = Decimal(cell.budget_amount_cny) - cell.allocated_amount_cny
        cell.reclaimed_amount_cny = leftover if leftover > 0 else Decimal("0")
        cell.save(update_fields=["allocated_amount_cny", "reclaimed_amount_cny"])
