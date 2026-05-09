from django.db import models


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
