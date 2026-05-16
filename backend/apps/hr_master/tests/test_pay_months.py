"""多国月薪制：LegalEntity.fixed_pay_months_per_year + Employee.pay_months_per_year_override

口径：
- override 优先（员工合同特例）
- 否则取 legal_entity.fixed_pay_months_per_year（默认 12，香港 13，西班牙 14）
- 否则兜底 12
"""
from decimal import Decimal

import pytest

from apps.hr_master.models import Employee, LegalEntity


@pytest.mark.django_db
def test_default_pay_months_is_12():
    le = LegalEntity.objects.create(code="CN01", name="中国大陆", country="CN")
    emp = Employee.objects.create(employee_no="E_PM_001", name_cn="zhangsan", legal_entity=le)
    assert emp.effective_pay_months_per_year == Decimal("12")


@pytest.mark.django_db
def test_hk_legal_entity_13_months():
    le = LegalEntity.objects.create(
        code="HK01", name="香港", country="HK",
        fixed_pay_months_per_year=Decimal("13"),
    )
    emp = Employee.objects.create(employee_no="E_PM_002", name_cn="lisi", legal_entity=le)
    assert emp.effective_pay_months_per_year == Decimal("13")


@pytest.mark.django_db
def test_es_legal_entity_14_months():
    le = LegalEntity.objects.create(
        code="ES01", name="西班牙", country="ES",
        fixed_pay_months_per_year=Decimal("14"),
    )
    emp = Employee.objects.create(employee_no="E_PM_003", name_cn="carlos", legal_entity=le)
    assert emp.effective_pay_months_per_year == Decimal("14")


@pytest.mark.django_db
def test_employee_override_wins():
    le = LegalEntity.objects.create(
        code="HK02", name="香港 B", country="HK",
        fixed_pay_months_per_year=Decimal("13"),
    )
    emp = Employee.objects.create(
        employee_no="E_PM_004", name_cn="特例合同", legal_entity=le,
        pay_months_per_year_override=Decimal("12"),
    )
    assert emp.effective_pay_months_per_year == Decimal("12")


@pytest.mark.django_db
def test_no_legal_entity_falls_back_to_12():
    emp = Employee.objects.create(employee_no="E_PM_005", name_cn="orphan")
    assert emp.effective_pay_months_per_year == Decimal("12")
