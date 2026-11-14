"""Hidden acceptance tests for MM-203: Meta.key_case."""
import pytest

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validates


def make(key_case, **declared):
    meta = type("Meta", (), {"key_case": key_case})
    return type("Generated", (Schema,), {**declared, "Meta": meta})


def test_default_is_none():
    class S(Schema):
        user_id = fields.Int()

    assert S.opts.key_case is None
    assert S().dump({"user_id": 1}) == {"user_id": 1}


@pytest.mark.parametrize(("name", "camel", "kebab"), [
    ("user_id", "userId", "user-id"),
    ("html_url", "htmlUrl", "html-url"),
    ("_private_note", "privateNote", "private-note"),
    ("api_URL", "apiURL", "api-URL"),
    ("name", "name", "name"),
    ("x2_value", "x2Value", "x2-value"),
])
def test_conversion(name, camel, kebab):
    assert make("camel", **{name: fields.Raw()})().dump({name: 1}) == {camel: 1}
    assert make("kebab", **{name: fields.Raw()})().dump({name: 1}) == {kebab: 1}


def test_example_from_ticket():
    class UserSchema(Schema):
        user_id = fields.Int()
        display_name = fields.Str()
        html_url = fields.Str(data_key="link")

        class Meta:
            key_case = "camel"

    assert UserSchema().dump({"user_id": 1, "display_name": "Ann", "html_url": "u"}) == {
        "userId": 1, "displayName": "Ann", "link": "u"}
    assert UserSchema().load({"userId": 1, "displayName": "Ann", "link": "u"}) == {
        "user_id": 1, "display_name": "Ann", "html_url": "u"}


def test_invalid_option():
    with pytest.raises(ValueError, match="`key_case` must be one of: camel, kebab."):
        make("snake", a_b=fields.Int())


def test_errors_and_unknown_use_converted_keys():
    S = make("camel", user_id=fields.Int(required=True))
    with pytest.raises(ValidationError) as exc:
        S().load({"userId": "x"})
    assert exc.value.messages == {"userId": ["Not a valid integer."]}
    with pytest.raises(ValidationError) as exc:
        S().load({"user_id": 1})
    assert exc.value.messages == {"userId": ["Missing data for required field."], "user_id": ["Unknown field."]}
    assert S(unknown=EXCLUDE).load({"userId": 1, "user_id": 2}) == {"user_id": 1}


def test_validates_uses_attribute_name():
    class S(Schema):
        user_id = fields.Int()

        class Meta:
            key_case = "camel"

        @validates("user_id")
        def check(self, value, **kwargs):
            if value < 0:
                raise ValidationError("negative")

    with pytest.raises(ValidationError) as exc:
        S().load({"userId": -1})
    assert exc.value.messages == {"userId": ["negative"]}


def test_only_exclude_partial_use_attribute_names():
    S = make("camel", user_id=fields.Int(required=True), display_name=fields.Str(required=True))
    assert S(only=("user_id",)).dump({"user_id": 1, "display_name": "a"}) == {"userId": 1}
    assert S(exclude=("user_id",)).dump({"user_id": 1, "display_name": "a"}) == {"displayName": "a"}
    assert S(partial=("display_name",)).load({"userId": 1}) == {"user_id": 1}
    assert S(load_only=("user_id",)).dump({"user_id": 1, "display_name": "a"}) == {"displayName": "a"}


def test_nested_uses_its_own_option():
    class Inner(Schema):
        street_name = fields.Str()

    class InnerKebab(Schema):
        street_name = fields.Str()

        class Meta:
            key_case = "kebab"

    class Outer(Schema):
        home_address = fields.Nested(Inner)
        work_address = fields.Nested(InnerKebab)

        class Meta:
            key_case = "camel"

    data = {"home_address": {"street_name": "a"}, "work_address": {"street_name": "b"}}
    dumped = Outer().dump(data)
    assert dumped == {"homeAddress": {"street_name": "a"}, "workAddress": {"street-name": "b"}}
    assert Outer().load(dumped) == data


def test_subclass_inherits():
    class Base(Schema):
        user_id = fields.Int()

        class Meta:
            key_case = "camel"

    class Child(Base):
        display_name = fields.Str()

    assert Child.opts.key_case == "camel"
    assert Child().dump({"user_id": 1, "display_name": "a"}) == {"userId": 1, "displayName": "a"}


def test_collision_raises():
    S = make("camel", user_id=fields.Int(), userId=fields.Int())
    with pytest.raises(ValueError, match="data_key"):
        S()

