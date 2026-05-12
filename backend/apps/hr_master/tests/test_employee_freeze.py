"""EmployeeFreeze 用例：起止判断、开口冻结、批量帮手。"""
import pytest
from datetime import date

from apps.iam.models import OrgUnit
from apps.hr_master.models import Employee, EmployeeFreeze


@pytest.fixture
def emp(db):
    org = OrgUnit.objects.create(code="C1_FREEZE", name="AI 中心", type="CENTER")
    return Employee.objects.create(
        employee_no="E_FREEZE_100", name_cn="alice", org_unit=org, hire_date=date(2026, 4, 1),
    )


@pytest.mark.django_db
def test_freeze_active_blocks_proposal(emp):
    f = EmployeeFreeze.objects.create(
        employee=emp, reason="PROBATION",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 7, 1),
        notes="试用期",
    )
    assert f.is_active(as_of=date(2026, 5, 11)) is True
    assert f.is_active(as_of=date(2026, 7, 2)) is False


@pytest.mark.django_db
def test_freeze_open_ended(emp):
    f = EmployeeFreeze.objects.create(
        employee=emp, reason="LEAVING",
        start_date=date(2026, 5, 1),
        end_date=None,
        notes="离职流转",
    )
    assert f.is_active(as_of=date(2026, 12, 31)) is True


@pytest.mark.django_db
def test_employee_has_active_freeze_helper(emp):
    EmployeeFreeze.objects.create(
        employee=emp, reason="PROBATION",
        start_date=date(2026, 4, 1), end_date=date(2026, 7, 1),
    )
    assert EmployeeFreeze.has_active(emp, as_of=date(2026, 5, 11)) is True
    assert EmployeeFreeze.has_active(emp, as_of=date(2026, 8, 1)) is False
