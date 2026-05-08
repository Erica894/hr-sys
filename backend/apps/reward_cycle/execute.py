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

    cycle.status = "EXECUTED"
    cycle.executed_at = timezone.now()
    cycle.save(update_fields=["status", "executed_at"])
    log_action("EXECUTE", actor, "RewardCycle", cycle.id, {}, {"final_status": "EXECUTED"})
