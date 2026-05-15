from django.db import migrations


def seed_default_scheme(apps, schema_editor):
    """建立 '2026-default' 方案（MGMT/STAFF 两桶），把所有现有员工按
    employee_category_1 字段映射进去。已有同名 scheme 时跳过创建。
    """
    CategoryScheme = apps.get_model("hr_master", "CategoryScheme")
    EmployeeCategory = apps.get_model("hr_master", "EmployeeCategory")
    EmployeeCategoryAssignment = apps.get_model("hr_master", "EmployeeCategoryAssignment")
    Employee = apps.get_model("hr_master", "Employee")
    RewardCycle = apps.get_model("reward_cycle", "RewardCycle")

    scheme, created = CategoryScheme.objects.get_or_create(
        code="2026-default",
        defaults={
            "name": "2026 默认方案 (干部 / 员工)",
            "status": "ACTIVE",
            "description": "迁移自旧 employee_category_1 字段，老接口与既有数据可继续工作",
        },
    )

    mgmt, _ = EmployeeCategory.objects.get_or_create(
        scheme=scheme, code="MGMT",
        defaults={"name": "管理干部", "sort_order": 0},
    )
    staff, _ = EmployeeCategory.objects.get_or_create(
        scheme=scheme, code="STAFF",
        defaults={"name": "员工", "sort_order": 1},
    )

    code_map = {"MANAGEMENT": mgmt, "STAFF": staff}
    for emp in Employee.objects.all():
        bucket = code_map.get(emp.employee_category_1, staff)
        EmployeeCategoryAssignment.objects.get_or_create(
            employee=emp, scheme=scheme,
            defaults={"category": bucket},
        )

    # 把还没绑定方案的 RewardCycle 都绑到这个默认方案
    RewardCycle.objects.filter(category_scheme__isnull=True).update(category_scheme=scheme)


def unseed(apps, schema_editor):
    CategoryScheme = apps.get_model("hr_master", "CategoryScheme")
    CategoryScheme.objects.filter(code="2026-default").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hr_master", "0004_categoryscheme_employeecategory_and_more"),
        ("reward_cycle", "0003_rewardcycle_category_scheme"),
    ]

    operations = [
        migrations.RunPython(seed_default_scheme, unseed),
    ]
