"""build_current_snapshot 命令 smoke 测试。"""
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.analytics.models import EmployeeCompensationSnapshot
from apps.hr_master.models import CompensationRecord, Employee, LegalEntity
from apps.reward_cycle.models import RewardCycle


@pytest.mark.django_db
def test_build_actual_for_cycle():
    le = LegalEntity.objects.create(code="CN_CMD", name="CN", country="CN")
    emp = Employee.objects.create(
        employee_no="E_CMD_001", name_cn="x", legal_entity=le, status="ACTIVE",
    )
    CompensationRecord.objects.create(
        employee=emp, effective_date=date(2026, 1, 1),
        base_salary=Decimal("10000"), monthly_salary=Decimal("10000"), currency="CNY",
    )
    cycle = RewardCycle.objects.create(code="C2026", name="2026", period="2026")

    out = StringIO()
    call_command("build_current_snapshot", "--cycle-id", str(cycle.pk), stdout=out)

    assert "1 snapshots for 2026/ACTUAL" in out.getvalue()
    snap = EmployeeCompensationSnapshot.objects.get(employee=emp, year=2026)
    assert snap.snapshot_kind == "ACTUAL"
    assert snap.annual_fixed_cny == Decimal("120000.00")


@pytest.mark.django_db
def test_build_projected_offsets_year():
    le = LegalEntity.objects.create(code="CN_CMD2", name="CN", country="CN")
    emp = Employee.objects.create(
        employee_no="E_CMD_002", name_cn="y", legal_entity=le, status="ACTIVE",
    )
    CompensationRecord.objects.create(
        employee=emp, effective_date=date(2026, 1, 1),
        base_salary=Decimal("10000"), monthly_salary=Decimal("10000"), currency="CNY",
    )
    cycle = RewardCycle.objects.create(code="C2026P", name="2026P", period="2026")

    call_command("build_current_snapshot", "--cycle-id", str(cycle.pk), "--kind", "PROJECTED")

    snap = EmployeeCompensationSnapshot.objects.get(employee=emp, snapshot_kind="PROJECTED")
    assert snap.year == 2027


@pytest.mark.django_db
def test_unknown_cycle_raises():
    with pytest.raises(CommandError):
        call_command("build_current_snapshot", "--cycle-id", "999999")
