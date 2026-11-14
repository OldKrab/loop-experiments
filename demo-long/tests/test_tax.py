import pytest

from payments.tax import gross_minor, vat_minor


def test_vat_exact():
    assert vat_minor(1_250, "FR") == 250


def test_vat_rounds_to_nearest_cent():
    assert vat_minor(1_999, "DE") == 380  # 379.81


def test_vat_half_even():
    assert vat_minor(35, "JP") == 4  # 3.5 -> 4
    assert vat_minor(25, "JP") == 2  # 2.5 -> 2


def test_gross():
    assert gross_minor(1_999, "DE") == 2_379


def test_unknown_country():
    with pytest.raises(ValueError):
        vat_minor(100, "XX")
