from django.db import models


class AuditLog(models.Model):
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_id = models.BigIntegerField(null=True)
    actor_role = models.CharField(max_length=32, blank=True)
    action = models.CharField(max_length=128, db_index=True)
    resource_type = models.CharField(max_length=64)
    resource_id = models.BigIntegerField(null=True)
    before = models.JSONField(null=True)
    after = models.JSONField(null=True)
    ip = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label = "audit"
        db_table = 'audit"."audit_log'
        managed = False


class SensitiveViewLog(models.Model):
    viewer_id = models.BigIntegerField()
    subject_type = models.CharField(max_length=64)
    subject_id = models.BigIntegerField()
    fields_viewed = models.JSONField(default=list)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "audit"
        db_table = 'audit"."sensitive_view_log'
        managed = False


class ExportLog(models.Model):
    exporter_id = models.BigIntegerField()
    kind = models.CharField(max_length=64)
    filter = models.JSONField(default=dict)
    row_count = models.IntegerField(default=0)
    file_url = models.TextField(blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "audit"
        db_table = 'audit"."export_log'
        managed = False
