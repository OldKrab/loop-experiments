"""Hidden acceptance tests for MM-204: fields.Union."""
import datetime as dt
import uuid

import pytest

from marshmallow import Schema, ValidationError, fields


class CatSchema(Schema):
    name = fields.Str(required=True)
    lives = fields.Int(required=True)


class DogSchema(Schema):
    name = fields.Str(required=True)
    breed = fields.Str(required=True)


class S(Schema):
    ident = fields.Union([fields.Int(), fields.UUID()])
    payload = fields.Union([fields.Nested(CatSchema), fields.Nested(DogSchema)])
    when = fields.Union([fields.Date(), fields.DateTime()],
                        dump_map={dt.datetime: fields.DateTime(), dt.date: fields.Date()})


UID = "2f1b8f3e-9c3a-4d2b-8f4e-1a2b3c4d5e6f"


def test_exported():
    assert "Union" in fields.__all__


def test_load_first_matching_candidate():
    assert S().load({"ident": "12"})["ident"] == 12
    assert S().load({"ident": UID})["ident"] == uuid.UUID(UID)


def test_load_error_keyed_by_candidate_index():
    with pytest.raises(ValidationError) as exc:
        S().load({"ident": "nope"})
    assert exc.value.messages == {"ident": {0: ["Not a valid integer."], 1: ["Not a valid UUID."]}}


def test_load_nested_candidates():
    assert S().load({"payload": {"name": "Tom", "lives": 9}})["payload"] == {"name": "Tom", "lives": 9}
    assert S().load({"payload": {"name": "Rex", "breed": "lab"}})["payload"] == {"name": "Rex", "breed": "lab"}
    with pytest.raises(ValidationError) as exc:
        S().load({"payload": {"name": "X"}})
    errors = exc.value.messages["payload"]
    assert set(errors) == {0, 1}
    assert errors[0] == {"lives": ["Missing data for required field."]}
    assert errors[1] == {"breed": ["Missing data for required field."]}


def test_candidate_order_matters():
    class T(Schema):
        value = fields.Union([fields.Str(), fields.Int()])

    assert T().load({"value": "12"}) == {"value": "12"}


def test_classes_are_instantiated():
    class T(Schema):
        value = fields.Union([fields.Int, fields.Str])

    assert T().load({"value": "7"}) == {"value": 7}
    assert T().load({"value": "x"}) == {"value": "x"}


def test_dump_map():
    assert S().dump({"when": dt.datetime(2024, 1, 2, 3, 4)})["when"] == "2024-01-02T03:04:00"
    assert S().dump({"when": dt.date(2024, 1, 2)})["when"] == "2024-01-02"


def test_dump_without_map_tries_candidates():
    class T(Schema):
        value = fields.Union([fields.Int(), fields.Str()])

    assert T().dump({"value": 5}) == {"value": 5}
    assert T().dump({"value": "abc"}) == {"value": "abc"}
    assert T().dump({"value": None}) == {"value": None}


def test_no_candidate():
    class T(Schema):
        value = fields.Union([fields.Int()])

    with pytest.raises(ValidationError) as exc:
        T().dump({"value": "abc"})
    assert exc.value.messages == ["Value 'abc' cannot be serialized by any candidate field."]


def test_empty_candidates():
    with pytest.raises(ValueError, match="Union requires at least one candidate field."):
        fields.Union([])


def test_none_required_allow_none():
    class T(Schema):
        a = fields.Union([fields.Int()], required=True)
        b = fields.Union([fields.Int()], allow_none=True)

    with pytest.raises(ValidationError) as exc:
        T().load({})
    assert exc.value.messages == {"a": ["Missing data for required field."]}
    assert T().load({"a": 1, "b": None}) == {"a": 1, "b": None}
    with pytest.raises(ValidationError) as exc:
        T().load({"a": None})
    assert exc.value.messages == {"a": ["Field may not be null."]}


def test_candidates_bound_to_schema():
    class T(Schema):
        value = fields.Union([fields.DateTime()])

        class Meta:
            datetimeformat = "%Y"

    assert T().dump({"value": dt.datetime(2024, 5, 6)}) == {"value": "2024"}
