"""Hidden acceptance tests for MM-210: Schema.json_schema()."""
import enum

from marshmallow import EXCLUDE, Schema, fields, validate

DRAFT = "https://json-schema.org/draft/2020-12/schema"


def props(*fields_, **named):
    attrs = {f"f{i}": f for i, f in enumerate(fields_)} | named
    S = Schema.from_dict(attrs)
    return S().json_schema()["properties"]


def one(field):
    return props(x=field)["x"]


class Color(enum.Enum):
    RED = "r"
    GREEN = "g"


def test_ticket_example():
    class UserSchema(Schema):
        id = fields.Int(dump_only=True)
        email = fields.Email(required=True)
        tags = fields.List(fields.Str(), validate=validate.Length(max=5))
        nick = fields.Str(allow_none=True, metadata={"description": "Shown name"})

    assert UserSchema().json_schema() == {
        "$schema": DRAFT,
        "title": "UserSchema",
        "type": "object",
        "properties": {
            "id": {"type": "integer", "readOnly": True},
            "email": {"type": "string", "format": "email"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "nick": {"type": ["string", "null"], "description": "Shown name"},
        },
        "required": ["email"],
        "additionalProperties": False,
    }


def test_required_omitted_and_additional_properties():
    class S(Schema):
        a = fields.Str()

        class Meta:
            unknown = EXCLUDE

    out = S().json_schema()
    assert "required" not in out
    assert out["additionalProperties"] is True


def test_scalar_types():
    assert one(fields.Int()) == {"type": "integer"}
    assert one(fields.Float()) == {"type": "number"}
    assert one(fields.Decimal()) == {"type": "number"}
    assert one(fields.TimeDelta()) == {"type": "number"}
    assert one(fields.Bool()) == {"type": "boolean"}
    assert one(fields.Str()) == {"type": "string"}
    assert one(fields.Url()) == {"type": "string", "format": "uri"}
    assert one(fields.UUID()) == {"type": "string", "format": "uuid"}
    assert one(fields.DateTime()) == {"type": "string", "format": "date-time"}
    assert one(fields.AwareDateTime()) == {"type": "string", "format": "date-time"}
    assert one(fields.Date()) == {"type": "string", "format": "date"}
    assert one(fields.Time()) == {"type": "string", "format": "time"}
    assert one(fields.Duration()) == {"type": "string", "format": "duration"}
    assert one(fields.Masked()) == {"type": "string"}
    assert one(fields.Raw()) == {}
    assert one(fields.Function(lambda o: 1, deserialize=lambda v: v)) == {}
    assert one(fields.Function(lambda o: 1)) == {"readOnly": True}  # serialize-only is dump_only


def test_enum():
    assert one(fields.Enum(Color)) == {"enum": ["RED", "GREEN"]}
    assert one(fields.Enum(Color, by_value=True)) == {"enum": ["r", "g"]}


def test_containers():
    assert one(fields.List(fields.Int())) == {"type": "array", "items": {"type": "integer"}}
    assert one(fields.Tuple((fields.Str(), fields.Int()))) == {
        "type": "array", "prefixItems": [{"type": "string"}, {"type": "integer"}], "minItems": 2, "maxItems": 2}
    assert one(fields.Dict()) == {"type": "object"}
    assert one(fields.Dict(keys=fields.Str(), values=fields.Int())) == {
        "type": "object", "additionalProperties": {"type": "integer"}}
    assert one(fields.Union([fields.Int(), fields.Str()])) == {"anyOf": [{"type": "integer"}, {"type": "string"}]}
    assert one(fields.Interval(fields.Date())) == {
        "type": "object",
        "properties": {"start": {"type": "string", "format": "date"}, "end": {"type": "string", "format": "date"}},
        "required": ["start", "end"],
        "additionalProperties": False,
    }


def test_nested():
    class Inner(Schema):
        a = fields.Int(required=True)

    inner = {"title": "Inner", "type": "object", "properties": {"a": {"type": "integer"}},
             "required": ["a"], "additionalProperties": False}
    assert one(fields.Nested(Inner)) == inner
    assert one(fields.Nested(Inner, many=True)) == {"type": "array", "items": inner}
    assert one(fields.List(fields.Nested(Inner))) == {"type": "array", "items": inner}


def test_validators():
    assert one(fields.Int(validate=validate.Range(min=1, max=9))) == {"type": "integer", "minimum": 1, "maximum": 9}
    assert one(fields.Float(validate=validate.Range(min=0, max=1, min_inclusive=False, max_inclusive=False))) == {
        "type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1}
    assert one(fields.Str(validate=validate.Length(min=2))) == {"type": "string", "minLength": 2}
    assert one(fields.Str(validate=validate.Length(equal=3))) == {"type": "string", "minLength": 3, "maxLength": 3}
    assert one(fields.List(fields.Int(), validate=validate.Length(min=1, max=4))) == {
        "type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 4}
    assert one(fields.Int(validate=validate.Length(max=3))) == {"type": "integer"}
    assert one(fields.Str(validate=validate.OneOf(["a", "b"]))) == {"type": "string", "enum": ["a", "b"]}
    assert one(fields.Str(validate=validate.Regexp(r"^\d+$"))) == {"type": "string", "pattern": r"^\d+$"}
    assert one(fields.List(fields.Int(), validate=validate.Unique())) == {
        "type": "array", "items": {"type": "integer"}, "uniqueItems": True}
    assert one(fields.Str(validate=[validate.Length(max=3), lambda v: True])) == {"type": "string", "maxLength": 3}


def test_modifiers():
    assert one(fields.Str(load_only=True)) == {"type": "string", "writeOnly": True}
    assert one(fields.Enum(Color, allow_none=True)) == {"anyOf": [{"enum": ["RED", "GREEN"]}, {"type": "null"}]}
    assert one(fields.Raw(allow_none=True)) == {"anyOf": [{}, {"type": "null"}]}
    assert one(fields.Int(allow_none=True, dump_only=True, validate=validate.Range(min=0))) == {
        "type": ["integer", "null"], "minimum": 0, "readOnly": True}


def test_data_keys_only_exclude_and_key_case():
    class S(Schema):
        first_name = fields.Str(required=True)
        last_name = fields.Str(data_key="surname", required=True)
        age = fields.Int()

        class Meta:
            key_case = "camel"

    assert list(S().json_schema()["properties"]) == ["firstName", "surname", "age"]
    assert S().json_schema()["required"] == ["firstName", "surname"]
    out = S(only=("age", "last_name")).json_schema()
    assert set(out["properties"]) == {"age", "surname"}
    assert out["required"] == ["surname"]
    assert set(S(exclude=("age",)).json_schema()["properties"]) == {"firstName", "surname"}
