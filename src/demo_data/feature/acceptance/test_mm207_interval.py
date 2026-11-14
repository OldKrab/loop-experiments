"""Hidden acceptance tests for MM-207: fields.Interval."""
import datetime as dt

import pytest

from marshmallow import Schema, ValidationError, fields


class Booking(Schema):
    period = fields.Interval(fields.Date())
    hours = fields.Interval(fields.Int, allow_empty=True)


def load_errors(data, schema=None):
    with pytest.raises(ValidationError) as exc:
        (schema or Booking()).load(data)
    return exc.value.messages


def test_exported():
    assert "Interval" in fields.__all__


def test_load():
    out = Booking().load({"period": {"start": "2024-01-01", "end": "2024-01-05"}})
    assert out == {"period": (dt.date(2024, 1, 1), dt.date(2024, 1, 5))}
    assert isinstance(out["period"], tuple)


def test_dump():
    assert Booking().dump({"period": (dt.date(2024, 1, 1), dt.date(2024, 1, 5))}) == {
        "period": {"start": "2024-01-01", "end": "2024-01-05"}
    }
    assert Booking().dump({"period": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)]}) == {
        "period": {"start": "2024-01-01", "end": "2024-01-02"}
    }
    assert Booking().dump({"period": None}) == {"period": None}


def test_order_error():
    assert load_errors({"period": {"start": "2024-01-05", "end": "2024-01-01"}}) == {
        "period": ["Start must not be after end."]
    }


def test_empty_error_and_allow_empty():
    assert load_errors({"period": {"start": "2024-01-01", "end": "2024-01-01"}}) == {
        "period": ["Interval must not be empty."]
    }
    assert Booking().load({"hours": {"start": 3, "end": 3}}) == {"hours": (3, 3)}


def test_inner_errors_keyed():
    assert load_errors({"period": {"start": "x", "end": "2024-01-01"}}) == {
        "period": {"start": ["Not a valid date."]}
    }
    assert load_errors({"hours": {"start": "a", "end": "b"}}) == {
        "hours": {"start": ["Not a valid integer."], "end": ["Not a valid integer."]}
    }


@pytest.mark.parametrize(
    "value",
    [{"start": "2024-01-01"}, {"start": "2024-01-01", "end": "2024-01-02", "x": 1}, ["2024-01-01", "2024-01-02"], "x", 5],
)
def test_invalid_shape(value):
    assert load_errors({"period": value}) == {"period": ["Not a valid interval."]}


def test_inner_bound_to_schema_format():
    class S(Schema):
        when = fields.Interval(fields.DateTime())

        class Meta:
            datetimeformat = "%Y/%m/%d %H:%M"

    a, b = dt.datetime(2024, 1, 1, 9, 0), dt.datetime(2024, 1, 1, 17, 30)
    assert S().dump({"when": (a, b)}) == {"when": {"start": "2024/01/01 09:00", "end": "2024/01/01 17:30"}}
    assert S().load({"when": {"start": "2024/01/01 09:00", "end": "2024/01/01 17:30"}}) == {"when": (a, b)}


def test_custom_error_messages():
    class S(Schema):
        p = fields.Interval(fields.Int(), error_messages={"order": "Backwards."})

    assert load_errors({"p": {"start": 2, "end": 1}}, S()) == {"p": ["Backwards."]}
