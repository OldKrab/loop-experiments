"""Hidden acceptance tests for MM-209: fields.Masked."""
import datetime as dt

import pytest

from marshmallow import Schema, ValidationError, fields


class Card(Schema):
    number = fields.Masked()
    token = fields.Masked(visible=2, mask_char="#")
    pin = fields.Masked(fields.Int(), visible=0)


def test_exported():
    assert "Masked" in fields.__all__


def test_dump_example():
    assert Card().dump({"number": "4111111111111111", "token": "secret", "pin": 1234}) == {
        "number": "************1111", "token": "####et", "pin": "****"}


def test_short_values_fully_masked():
    assert Card().dump({"number": "abc", "token": "ab"}) == {"number": "***", "token": "##"}
    assert Card().dump({"number": "abcd"}) == {"number": "****"}
    assert Card().dump({"number": ""}) == {"number": ""}


def test_none_dumps_none():
    assert Card().dump({"number": None}) == {"number": None}


def test_load_delegates():
    assert Card().load({"number": "4111111111111111", "pin": "12"}) == {"number": "4111111111111111", "pin": 12}
    with pytest.raises(ValidationError) as exc:
        Card().load({"pin": "x"})
    assert exc.value.messages == {"pin": ["Not a valid integer."]}


def test_inner_class_and_schema_binding():
    class S(Schema):
        when = fields.Masked(fields.Date, visible=2)

        class Meta:
            dateformat = "%d.%m.%Y"

    assert S().dump({"when": dt.date(2024, 3, 9)}) == {"when": "********24"}
    assert S().load({"when": "09.03.2024"}) == {"when": dt.date(2024, 3, 9)}


@pytest.mark.parametrize("visible", [-1, 1.5, "4", True])
def test_bad_visible(visible):
    with pytest.raises(ValueError, match="`visible` must be a non-negative integer."):
        fields.Masked(visible=visible)


@pytest.mark.parametrize("mask_char", ["", "**", 1, None])
def test_bad_mask_char(mask_char):
    with pytest.raises(ValueError, match="`mask_char` must be a single character."):
        fields.Masked(mask_char=mask_char)
