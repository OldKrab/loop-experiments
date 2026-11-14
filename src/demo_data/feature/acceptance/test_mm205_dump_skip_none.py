"""Hidden acceptance tests for MM-205: Meta.dump_skip_none."""
import pytest

from marshmallow import Schema, fields, post_dump


class Profile(Schema):
    name = fields.Str()
    bio = fields.Str()
    age = fields.Int()
    tags = fields.List(fields.Str())
    active = fields.Bool()

    class Meta:
        dump_skip_none = True


def test_default_is_false_and_keeps_none():
    class S(Schema):
        a = fields.Str()

    assert S.opts.dump_skip_none is False
    assert S().dump({"a": None}) == {"a": None}


def test_none_values_are_omitted():
    assert Profile().dump({"name": "Ann", "bio": None, "age": None}) == {"name": "Ann"}


def test_falsy_values_are_kept():
    data = {"name": "", "bio": "x", "age": 0, "tags": [], "active": False}
    assert Profile().dump(data) == data


def test_dump_default_none_is_omitted():
    class S(Schema):
        a = fields.Str(dump_default=None)
        b = fields.Str(dump_default="x")

        class Meta:
            dump_skip_none = True

    assert S().dump({}) == {"b": "x"}


def test_many():
    out = Profile(many=True).dump([{"name": "A", "bio": None}, {"name": None, "age": 3}])
    assert out == [{"name": "A"}, {"age": 3}]


def test_post_dump_sees_trimmed_dict():
    seen = []

    class S(Schema):
        a = fields.Str()
        b = fields.Str()

        class Meta:
            dump_skip_none = True

        @post_dump
        def record(self, data, **kwargs):
            seen.append(dict(data))
            return data

    S().dump({"a": "x", "b": None})
    assert seen == [{"a": "x"}]


def test_nested_follows_own_option():
    class Inner(Schema):
        x = fields.Str()

    class InnerSkip(Schema):
        x = fields.Str()

        class Meta:
            dump_skip_none = True

    class Outer(Schema):
        plain = fields.Nested(Inner)
        skip = fields.Nested(InnerSkip)
        missing_one = fields.Nested(Inner)

        class Meta:
            dump_skip_none = True

    out = Outer().dump({"plain": {"x": None}, "skip": {"x": None}, "missing_one": None})
    assert out == {"plain": {"x": None}, "skip": {}}


def test_option_off_on_outer_does_not_trim_nested_with_option_on_outer_only():
    class Inner(Schema):
        x = fields.Str()

    class Outer(Schema):
        inner = fields.Nested(Inner)
        y = fields.Str()

        class Meta:
            dump_skip_none = True

    assert Outer().dump({"inner": {"x": None}, "y": None}) == {"inner": {"x": None}}


def test_load_unaffected():
    class S(Schema):
        a = fields.Str(allow_none=True)

        class Meta:
            dump_skip_none = True

    assert S().load({"a": None}) == {"a": None}


@pytest.mark.parametrize("value", [1, "yes", None])
def test_non_bool_raises(value):
    with pytest.raises(ValueError, match="`dump_skip_none` must be a boolean."):

        class S(Schema):
            class Meta:
                dump_skip_none = value
