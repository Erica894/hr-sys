from django.db import models


# TODO(sprint-bonus): 当 Bonus 走二级分发时，参照
#   apps/compensation_plan/services/budget_distribution.compute_distribution
#   apps/compensation_plan/services/budget_aggregation.aggregate_*_allocated
# 复用同一套 distributor / aggregator。预期新增：
#   - BonusBudgetCell(plan, employee_category_1, target_org_unit, budget_amount_cny,
#                     distribution_rule, allocated_amount_cny, reclaimed_amount_cny)
#   - BonusProposal(cycle, employee, suggested_amount, manager_delta_amount, final_amount)
# 落地时：
#   1) 在 SaveProposalsView 的 cap 检查里追加 check_bonus_cap()
#   2) 在 reward_cycle.execute 的 finalize 阶段追加 _finalize_bonus_cells()
#   3) 前端复用 AdjustmentBudgetView/LtiBudgetView 的 distribute 对话框模板
# 本 sprint 仅留 hook，不改 schema、不写代码。


class BonusPlan(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    period = models.CharField(max_length=16)
    status = models.CharField(max_length=32, default="DRAFT")
    budget_total_cny = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    scope = models.JSONField(default=dict, blank=True)
    formula = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bonus_plan"
