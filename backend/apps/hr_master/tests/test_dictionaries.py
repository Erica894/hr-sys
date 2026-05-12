"""LevelBand + PositionGrade 字典表用例：唯一性、排序、外键反向。"""
import pytest
from django.db.utils import IntegrityError

from apps.hr_master.models import LevelBand, PositionGrade


@pytest.mark.django_db
def test_level_band_unique_code_and_ordering():
    LevelBand.objects.create(code="P5", name="P5 资深", order=5)
    LevelBand.objects.create(code="P6", name="P6 专家", order=6)
    bands = list(LevelBand.objects.order_by("order").values_list("code", flat=True))
    assert bands == ["P5", "P6"]


@pytest.mark.django_db
def test_level_band_code_unique():
    LevelBand.objects.create(code="P5", name="P5", order=5)
    with pytest.raises(IntegrityError):
        LevelBand.objects.create(code="P5", name="dup", order=5)


@pytest.mark.django_db
def test_position_grade_links_to_band():
    band = LevelBand.objects.create(code="M1", name="M1 经理", order=10)
    g = PositionGrade.objects.create(
        code="M1-A", name="M1 A 档", level_band=band, order=1,
    )
    assert g.level_band == band
    assert band.position_grades.count() == 1
