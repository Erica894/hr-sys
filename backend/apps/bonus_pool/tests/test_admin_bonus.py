import pytest
from rest_framework.test import APIClient
from django.core.management import call_command
from apps.iam.models import User


@pytest.fixture
def seeded(db):
    call_command("seed_phase1")


def test_anonymous_gets_401(seeded):
    c = APIClient()
    assert c.get("/api/admin/bonus-plans/").status_code == 401


def test_non_hr_gets_403(seeded):
    c = APIClient()
    c.force_authenticate(User.objects.get(email="alice@demo.com"))
    assert c.get("/api/admin/bonus-plans/").status_code == 403


def test_hr_gets_empty_list(seeded):
    c = APIClient()
    c.force_authenticate(User.objects.get(email="hr@demo.com"))
    r = c.get("/api/admin/bonus-plans/")
    assert r.status_code == 200
    data = r.data if isinstance(r.data, list) else r.data.get("results", [])
    assert data == []
