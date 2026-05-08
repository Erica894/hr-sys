import pytest
from django.core.management import call_command
from apps.hr_master.models import Employee


@pytest.mark.django_db
def test_import_creates_employees(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([
        "employee_no", "name_cn", "name_en", "email", "dept_name", "center_name",
        "team_name", "job_family", "job_level_current", "position_current",
        "is_promoted", "job_level_promoted", "position_promoted", "promotion_category",
        "participates_annual_adjustment", "employee_category_1", "employee_category_2",
        "hire_date", "monthly_salary", "pay_currency", "pay_country_region",
    ])
    ws.append([
        "E001", "陈爱丽", "Alice Chen", "alice@example.com", "Engineering", "", "",
        "Engineering", "P6", "Senior Engineer", "TRUE", "P7", "Lead Engineer", "VERTICAL",
        "TRUE", "MANAGEMENT", "CORE", "2020-01-15", "50000", "CNY", "CN",
    ])
    ws.append([
        "E002", "王博", "Bob Wang", "bob@example.com", "Engineering", "", "",
        "Engineering", "P4", "Engineer", "FALSE", "", "", "NONE",
        "TRUE", "STAFF", "GENERAL", "2021-06-01", "30000", "CNY", "CN",
    ])
    xlsx_path = tmp_path / "employees.xlsx"
    wb.save(str(xlsx_path))
    call_command("import_employees", str(xlsx_path))
    assert Employee.objects.count() == 2
    alice = Employee.objects.get(employee_no="E001")
    assert alice.is_promoted is True
    assert alice.job_level_promoted == "P7"
    assert alice.employee_category_1 == "MANAGEMENT"
