import pytest

from payments.refunds import refundable


def test_partial_refund():
    assert refundable(paid_minor=1000, refunded_minor=300, requested_minor=500) == 500


def test_refund_capped_at_remaining():
    assert refundable(paid_minor=1000, refunded_minor=800, requested_minor=500) == 200


def test_refund_must_be_positive():
    with pytest.raises(ValueError):
        refundable(1000, 0, 0)
