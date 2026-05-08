import pytest
from django.db import IntegrityError
from apps.lti.models import LTIPlan, LTIGrant
from apps.hr_master.models import Employee, LegalEntity


@pytest.mark.django_db
def test_lti_grant_unique_per_plan_employee():
    entity = LegalEntity.objects.create(code="HQ", name="总部", country="CN")
    emp = Employee.objects.create(employee_no="E001", name_cn="Alice", legal_entity=entity)
    plan = LTIPlan.objects.create(
        code="RSU-2026", name="2026 RSU", grant_date="2026-01-01",
        total_shares=100000, unit_price_at_grant="10.00",
    )
    LTIGrant.objects.create(plan=plan, employee=emp, granted_ads=500)
    with pytest.raises(IntegrityError):
        LTIGrant.objects.create(plan=plan, employee=emp, granted_ads=300)
