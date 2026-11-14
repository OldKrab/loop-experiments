"""Hidden acceptance tests for MM-202: fields.Duration."""
import datetime as dt

import pytest

from marshmallow import Schema, ValidationError, fields

td = dt.timedelta


@pytest.mark.parametrize(("value", "expected"), [
    (td(days=1, hours=2, minutes=30), "P1DT2H30M"),
    (td(seconds=0.5), "PT0.5S"),
    (td(days=-3), "-P3D"),
    (td(hours=-1, seconds=-30), "-PT1H30S"),
    (td(days=2, microseconds=1500), "P2DT0.0015S"),
    (td(hours=26), "P1DT2H"),
    (td(0), "PT0S"),
    (td(minutes=5, seconds=7), "PT5M7S"),
])
def test_serialize(value, expected):
    assert fields.Duration().serialize("d", {"d": value}) == expected


def test_serialize_none():
    assert fields.Duration().serialize("d", {"d": None}) is None


def test_serialize_seconds_precision():
    assert fields.Duration(precision="seconds").serialize("d", {"d": td(seconds=1, microseconds=999)}) == "PT1S"


@pytest.mark.parametrize(("value", "expected"), [
    ("P1DT2H30M", td(days=1, hours=2, minutes=30)),
    ("p1dt2h30m", td(days=1, hours=2, minutes=30)),
    ("PT0.5S", td(seconds=0.5)),
    ("PT0,5S", td(seconds=0.5)),
    ("-P3D", td(days=-3)),
    ("+PT90M", td(minutes=90)),
    ("P2W", td(days=14)),
    ("PT1.1234567S", td(seconds=1, microseconds=123456)),
    ("PT2M", td(minutes=2)),
    ("PT0S", td(0)),
])
def test_deserialize(value, expected):
    assert fields.Duration().deserialize(value) == expected


def test_deserialize_timedelta_passthrough():
    value = td(hours=1)
    assert fields.Duration().deserialize(value) == value


def test_deserialize_seconds_precision():
    assert fields.Duration(precision="seconds").deserialize("PT1.5S") == td(seconds=1)


@pytest.mark.parametrize("value", ["P1Y", "P2M", "P1Y2M3D"])
def test_ambiguous(value):
    with pytest.raises(ValidationError) as exc:
        fields.Duration().deserialize(value)
    assert exc.value.messages == ["Durations with years or months are not supported."]


@pytest.mark.parametrize("value", ["P", "PT", "P1DT", "1D", "", 12, [], "P1000000000D", "PT1H2X"])
def test_invalid(value):
    with pytest.raises(ValidationError) as exc:
        fields.Duration().deserialize(value)
    assert exc.value.messages == ["Not a valid ISO 8601 duration."]


def test_bad_precision():
    with pytest.raises(ValueError, match="The precision must be one of: seconds, microseconds."):
        fields.Duration(precision="hours")


def test_exported_and_roundtrip_in_schema():
    assert "Duration" in fields.__all__

    class S(Schema):
        timeout = fields.Duration()

    value = td(days=1, hours=2, minutes=3, seconds=4, microseconds=500000)
    dumped = S().dump({"timeout": value})
    assert dumped == {"timeout": "P1DT2H3M4.5S"}
    assert S().load(dumped) == {"timeout": value}
