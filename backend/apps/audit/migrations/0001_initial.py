from django.db import migrations


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE SCHEMA IF NOT EXISTS audit;
                CREATE TABLE IF NOT EXISTS audit.audit_log (
                    id bigserial PRIMARY KEY,
                    occurred_at timestamptz NOT NULL DEFAULT now(),
                    actor_id bigint,
                    actor_role varchar(32) DEFAULT '',
                    action varchar(128) NOT NULL,
                    resource_type varchar(64) NOT NULL DEFAULT '',
                    resource_id bigint,
                    before jsonb,
                    after jsonb,
                    ip inet,
                    user_agent text DEFAULT '',
                    request_id varchar(64) DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit.audit_log(actor_id);
                CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit.audit_log(action);
                CREATE TABLE IF NOT EXISTS audit.sensitive_view_log (
                    id bigserial PRIMARY KEY,
                    viewer_id bigint NOT NULL,
                    subject_type varchar(64) NOT NULL,
                    subject_id bigint NOT NULL,
                    fields_viewed jsonb DEFAULT '[]',
                    at timestamptz NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS audit.export_log (
                    id bigserial PRIMARY KEY,
                    exporter_id bigint NOT NULL,
                    kind varchar(64) NOT NULL,
                    filter jsonb DEFAULT '{}',
                    row_count int DEFAULT 0,
                    file_url text DEFAULT '',
                    at timestamptz NOT NULL DEFAULT now()
                );
                CREATE OR REPLACE RULE audit_log_no_update AS ON UPDATE TO audit.audit_log DO INSTEAD NOTHING;
                CREATE OR REPLACE RULE audit_log_no_delete AS ON DELETE TO audit.audit_log DO INSTEAD NOTHING;
            """,
            reverse_sql="DROP SCHEMA IF EXISTS audit CASCADE;",
        ),
    ]
