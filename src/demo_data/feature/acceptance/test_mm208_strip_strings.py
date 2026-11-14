"""Hidden acceptance tests for MM-208: Meta.strip_strings."""
import pytest

from marshmallow import Schema, ValidationError, fields, validate


class Signup(Schema):
    email = fields.Email()
    name = fields.Str(validate=validate.Length(min=1))
    password = fields.Str(metadata={"strip": False})
    tags = fields.List(fields.Str())
    pair = fields.Tuple((fields.Str(), fields.Int()))
    labels = fields.Dict(keys=fields.Str(), values=fields.Str())
    site = fields.Url()

    class Meta:
        strip_strings = True


def test_default_is_false():
    class S(Schema):
        a = fields.Str()

    assert S.opts.strip_strings is False
    assert S().load({"a": " x "}) == {"a": " x "}


def test_ticket_example():
    out = Signup().load(
        {"email": " ann@example.com ", "name": " Ann ", "password": " pw ", "tags": [" a ", "b "]}
    )
    assert out == {"email": "ann@example.com", "name": "Ann", "password": " pw ", "tags": ["a", "b"]}


def test_strip_before_validators():
    with pytest.raises(ValidationError) as exc:
        Signup().load({"name": "   "})
    assert exc.value.messages == {"name": ["Shorter than minimum length 1."]}


def test_subclasses_and_containers():
    out = Signup().load({"site": " https://example.com ", "pair": [" a ", 1], "labels": {"k": "\tv\n"}})
    assert out == {"site": "https://example.com", "pair": ("a", 1), "labels": {"k": "v"}}


def test_dump_unaffected():
    assert Signup().dump({"name": " Ann "}) == {"name": " Ann "}


def test_non_string_still_invalid():
    with pytest.raises(ValidationError) as exc:
        Signup().load({"name": 5})
    assert exc.value.messages == {"name": ["Not a valid string."]}


def test_nested_follows_own_option():
    class Plain(Schema):
        x = fields.Str()

    class Strips(Schema):
        x = fields.Str()

        class Meta:
            strip_strings = True

    class Outer(Schema):
        a = fields.Nested(Plain)
        b = fields.Nested(Strips)
        c = fields.Str()

        class Meta:
            strip_strings = True

    class OuterPlain(Schema):
        b = fields.Nested(Strips)
        c = fields.Str()

    assert Outer().load({"a": {"x": " 1 "}, "b": {"x": " 2 "}, "c": " 3 "}) == {
        "a": {"x": " 1 "}, "b": {"x": "2"}, "c": "3"}
    assert OuterPlain().load({"b": {"x": " 2 "}, "c": " 3 "}) == {"b": {"x": "2"}, "c": " 3 "}


@pytest.mark.parametrize("value", [1, "yes", None])
def test_non_bool_raises(value):
    with pytest.raises(ValueError, match="`strip_strings` must be a boolean."):

        class S(Schema):
            class Meta:
                strip_strings = value
