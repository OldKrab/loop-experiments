import pytest

from payments.currency import convert, format_amount, to_major, to_minor
from decimal import Decimal


def test_usd_roundtrip():
    assert to_minor(to_major(1050, "USD"), "USD") == 1050


def test_usd_to_eur():
    assert convert(10_000, "USD", "EUR") == 9_200  # $100.00 -> €92.00


def test_usd_to_jpy():
    assert convert(1_000, "USD", "JPY") == 1_495  # $10.00 -> ¥1495


def test_jpy_to_usd():
    assert convert(1_495, "JPY", "USD") == 1_000  # ¥1495 -> $10.00


def test_usd_to_kwd():
    assert convert(10_000, "USD", "KWD") == 30_700  # $100.00 -> 30.700 KWD


def test_half_even_rounding():
    assert to_minor(Decimal("0.125"), "USD") == 12
    assert to_minor(Decimal("0.135"), "USD") == 14


def test_format_amount():
    assert format_amount(1050, "USD") == "10.50 USD"
    assert format_amount(1495, "JPY") == "1495 JPY"
    assert format_amount(30700, "KWD") == "30.700 KWD"


def test_unsupported_currency():
    with pytest.raises(ValueError):
        convert(100, "USD", "XYZ")
