"""import_historical_snapshots 双用途测试。"""
from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from django.core.management import call_command

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.hr_master.models import Employee, LegalEntity


def _make_xlsx(tmp_path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([
        "employee_no", "year",
        "annual_fixed_cny", "annual_bonus_cny", "annual_rsu_value_cny",
        "perf_grade_code", "pay_band",
    ])
    for r in rows:
        ws.append(r)
    p = tmp_path / "snap.xlsx"
    wb.save(p)
    return str(p)


@pytest.mark.django_db
def test_backfill_mode_creates_actual_with_import_source(tmp_path):
    le = LegalEntity.objects.create(code="CN_IMP", name="CN", country="CN")
    Employee.objects.create(employee_no="E_IMP_1", name_cn="a", legal_entity=le)
    Employee.objects.create(employee_no="E_IMP_2", name_cn="b", legal_entity=le)

    path = _make_xlsx(tmp_path, [
        ["E_IMP_1", 2025, 240000, 60000, 0, "B+", "P50_P75"],
        ["E_IMP_2", 2025, 300000, 100000, 50000, "A", "ABOVE_P75"],
    ])
    call_command("import_historical_snapshots", path)

    snaps = EmployeeCompensationSnapshot.objects.filter(year=2025).order_by("employee__employee_no")
    assert snaps.count() == 2
    s1 = snaps[0]
    assert s1.snapshot_kind == "ACTUAL"
    assert s1.source == "IMPORT"
    assert s1.annual_fixed_cny == Decimal("240000")
    assert s1.annual_cash_cny == Decimal("300000")
    assert s1.annual_total_comp_cny == Decimal("300000")
    s2 = snaps[1]
    assert s2.annual_total_comp_cny == Decimal("450000")


@pytest.mark.django_db
def test_bonus_only_mode_updates_derived_row(tmp_path):
    le = LegalEntity.objects.create(code="CN_IMP2", name="CN", country="CN")
    emp = Employee.objects.create(employee_no="E_IMP_3", name_cn="c", legal_entity=le)
    EmployeeCompensationSnapshot.objects.create(
        employee=emp, year=2026, snapshot_kind="ACTUAL",
        annual_fixed_cny=Decimal("240000"),
        annual_bonus_cny=Decimal("0"),
        annual_cash_cny=Decimal("240000"),
        annual_rsu_value_cny=Decimal("3600"),
        annual_total_comp_cny=Decimal("243600"),
        source="DERIVED",
    )

    path = _make_xlsx(tmp_path, [
        ["E_IMP_3", 2026, None, 80000, None, "", ""],
    ])
    call_command("import_historical_snapshots", path)

    snap = EmployeeCompensationSnapshot.objects.get(employee=emp, year=2026)
    assert snap.annual_fixed_cny == Decimal("240000")
    assert snap.annual_bonus_cny == Decimal("80000")
    assert snap.annual_cash_cny == Decimal("320000")
    assert snap.annual_rsu_value_cny == Decimal("3600")
    assert snap.annual_total_comp_cny == Decimal("323600")
    assert snap.source == "DERIVED+MANUAL_BONUS"


@pytest.mark.django_db
def test_bonus_only_without_existing_row_is_error(tmp_path, capsys):
    le = LegalEntity.objects.create(code="CN_IMP3", name="CN", country="CN")
    Employee.objects.create(employee_no="E_IMP_4", name_cn="d", legal_entity=le)

    path = _make_xlsx(tmp_path, [["E_IMP_4", 2026, None, 50000, None, "", ""]])
    call_command("import_historical_snapshots", path)
    assert EmployeeCompensationSnapshot.objects.count() == 0


@pytest.mark.django_db
def test_dry_run_rolls_back(tmp_path):
    le = LegalEntity.objects.create(code="CN_IMP4", name="CN", country="CN")
    Employee.objects.create(employee_no="E_IMP_5", name_cn="e", legal_entity=le)
    path = _make_xlsx(tmp_path, [["E_IMP_5", 2025, 100000, 0, 0, "", ""]])
    call_command("import_historical_snapshots", path, "--dry-run")
    assert EmployeeCompensationSnapshot.objects.count() == 0
