"""Hidden acceptance tests for MM-206: validate.Each."""
import pytest

from marshmallow import Schema, ValidationError, fields, validate
from marshmallow.validate import Each


def errors(validator, value):
    with pytest.raises(ValidationError) as exc:
        validator(value)
    return exc.value.messages


def test_requires_a_validator():
    with pytest.raises(ValueError, match="Each requires at least one validator."):
        Each()


def test_valid_returns_value():
    value = ["ab", "abc"]
    assert Each(validate.Length(max=3))(value) is value
    assert Each(validate.Length(max=3))([]) == []


def test_failing_indices_only():
    assert errors(Each(validate.Length(max=3)), ["ab", "abcd", "x", "wxyz"]) == {
        1: ["Longer than maximum length 3."],
        3: ["Longer than maximum length 3."],
    }


def test_all_validators_collected_in_order():
    v = Each(validate.Range(min=0), lambda x: x % 2 == 0)
    assert errors(v, [2, -1]) == {1: ["Must be greater than or equal to 0.", "Invalid value."]}
    assert errors(v, [3]) == {0: ["Invalid value."]}


def test_only_false_return_fails():
    assert Each(lambda x: None, lambda x: 0, lambda x: "")([1, 2]) == [1, 2]


def test_raising_callable():
    def no_x(value):
        if "x" in value:
            raise ValidationError("Contains x.")

    assert errors(Each(no_x), ["a", "x"]) == {1: ["Contains x."]}


def test_works_on_tuples_and_generators_of_items():
    assert errors(Each(validate.OneOf(["a", "b"])), ("a", "c")) == {1: ["Must be one of: a, b."]}


def test_repr():
    v = Each(validate.Length(max=3))
    assert repr(v).startswith(f"<Each(validators={v.validators!r}")
    assert isinstance(v.validators, tuple)


def test_in_schema():
    class S(Schema):
        tags = fields.List(fields.Str(), validate=Each(validate.Length(min=1)))

    assert S().load({"tags": ["a", "b"]}) == {"tags": ["a", "b"]}
    with pytest.raises(ValidationError) as exc:
        S().load({"tags": ["a", ""]})
    assert exc.value.messages == {"tags": [{1: ["Shorter than minimum length 1."]}]}
