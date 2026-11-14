"""Hidden acceptance tests for MM-201: validate.Unique."""
from types import SimpleNamespace

import pytest

from marshmallow import Schema, ValidationError, fields, validate
from marshmallow.validate import Unique


def message(validator, value):
    with pytest.raises(ValidationError) as exc:
        validator(value)
    return exc.value.messages[0]


def test_distinct_values_are_returned():
    value = [1, 2, 3]
    assert Unique()(value) is value
    assert Unique()(()) == ()


def test_duplicates_in_first_seen_order():
    assert message(Unique(), [1, 2, 1, 3, 2, 1]) == "Duplicate items: 1, 2."
    assert message(Unique(), [3, 3, 1, 1]) == "Duplicate items: 3, 1."


def test_duplicates_use_repr():
    assert message(Unique(), ["a", "b", "a"]) == "Duplicate items: 'a'."


def test_string_key_on_mappings_and_objects():
    assert message(Unique(key="id"), [{"id": 1}, {"id": 2}, {"id": 1}]) == "Duplicate items: 1."
    objs = [SimpleNamespace(id=5), SimpleNamespace(id=5)]
    assert message(Unique(key="id"), objs) == "Duplicate items: 5."
    assert Unique(key="id")([{"id": 1}, {"id": 2}]) == [{"id": 1}, {"id": 2}]


def test_callable_key():
    assert message(Unique(key=str.lower), ["A", "a"]) == "Duplicate items: 'a'."


def test_unhashable_items():
    assert message(Unique(), [{"x": 1}, {"x": 1}]) == "Duplicate items: {'x': 1}."
    assert Unique()([[1], [2]]) == [[1], [2]]


def test_missing_key():
    assert message(Unique(key="id"), [{"id": 1}, {}]) == "Item at index 1 has no key 'id'."
    assert message(Unique(key="id", error="custom"), [SimpleNamespace(), {}]) == "Item at index 0 has no key 'id'."


def test_custom_error():
    assert message(Unique(error="Not unique: {duplicates} in {input}"), [1, 1]) == "Not unique: 1 in [1, 1]"


def test_repr():
    assert repr(Unique(key="id")) == "<Unique(key='id', error='Duplicate items: {duplicates}.')>"


def test_in_schema():
    class S(Schema):
        tags = fields.List(fields.Str(), validate=validate.Unique())

    assert S().load({"tags": ["a", "b"]}) == {"tags": ["a", "b"]}
    with pytest.raises(ValidationError) as exc:
        S().load({"tags": ["a", "a"]})
    assert exc.value.messages == {"tags": ["Duplicate items: 'a'."]}
