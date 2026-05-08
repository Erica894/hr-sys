from django.core.management.base import BaseCommand
import openpyxl
from apps.hr_master.models import Employee

COLS = {
    "employee_no": 0, "name_cn": 1, "name_en": 2, "email": 3,
    "dept_name": 4, "center_name": 5, "team_name": 6, "job_family": 7,
    "job_level_current": 8, "position_current": 9,
    "is_promoted": 10, "job_level_promoted": 11, "position_promoted": 12,
    "promotion_category": 13, "participates_annual_adjustment": 14,
    "employee_category_1": 15, "employee_category_2": 16,
    "hire_date": 17, "monthly_salary": 18, "pay_currency": 19, "pay_country_region": 20,
}


def _bool(v):
    return str(v).strip().upper() in ("TRUE", "YES", "1", "是")


class Command(BaseCommand):
    help = "Import employees from Excel"

    def add_arguments(self, parser):
        parser.add_argument("file_path")

    def handle(self, *args, **options):
        wb = openpyxl.load_workbook(options["file_path"])
        ws = wb.active
        created = updated = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            data = {k: (row[v] if row[v] is not None else "") for k, v in COLS.items()}
            emp_no = data.pop("employee_no")
            data.pop("monthly_salary", None)
            data["is_promoted"] = _bool(data["is_promoted"])
            data["participates_annual_adjustment"] = _bool(data["participates_annual_adjustment"])
            if not data["promotion_category"]:
                data["promotion_category"] = "NONE"
            _, c = Employee.objects.update_or_create(employee_no=emp_no, defaults=data)
            created += c
            updated += not c
        self.stdout.write(f"Done: {created} created, {updated} updated")
