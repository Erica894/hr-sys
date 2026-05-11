from django.db import migrations


SEVEN_ROLES = [
    ("HR_ADMIN", "薪酬 HR"),
    ("DEPT_HEAD", "部门负责人"),
    ("CENTER_HEAD", "中心负责人"),
    ("GROUP_LEAD", "组长"),
    ("EMPLOYEE", "员工"),
    ("FINANCE", "财务"),
    ("AUDITOR", "审计员"),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("iam", "Role")
    from apps.iam.constants import ROLE_BASE_FIELD_SETS

    for code, name in SEVEN_ROLES:
        Role.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "base_field_set": ROLE_BASE_FIELD_SETS[code],
            },
        )


def revert(apps, schema_editor):
    Role = apps.get_model("iam", "Role")
    Role.objects.filter(code__in=[c for c, _ in SEVEN_ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [("iam", "0002_sprint1_baseline")]
    operations = [migrations.RunPython(seed_roles, revert)]
