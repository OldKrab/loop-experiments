---
name: marshmallow-conventions
description: How code is structured and written in the marshmallow codebase - fields, validators, schema Meta options, error messages, and where tests go. Use before reading or changing code under src/marshmallow/.
---
# marshmallow conventions

## Layout
- `src/marshmallow/fields.py`: one class per field type. Every public field is listed in `fields.__all__` (alphabetical).
- `src/marshmallow/validate.py`: validators, all subclasses of `Validator`.
- `src/marshmallow/schema.py`: `SchemaMeta`, `SchemaOpts` (the `class Meta` options), and `Schema`.
- Tests: `tests/test_fields.py`, `tests/test_serialization.py` (dump), `tests/test_deserialization.py` (load), `tests/test_validate.py`, `tests/test_options.py` (Meta options), `tests/test_schema.py`. `tests/base.py` has shared fixtures and models.
- Grep before reading: `fields.py` is about 2,100 lines and `schema.py` about 1,250. Read the class you are imitating, not the whole file.

## Fields
- Subclass `Field` and implement `_serialize(self, value, attr, obj, **kwargs)` and `_deserialize(self, value, attr, data, **kwargs)`. `_serialize` returns `None` for `None`.
- The base `Field.serialize` / `Field.deserialize` handle missing values, `None`, `required`, `allow_none`, `validate`, and defaults. Do not re-implement them.
- Error messages go in the class attribute `default_error_messages` (merged across the class hierarchy). Raise them with `raise self.make_error("key", **format_kwargs)`.
- Constructor arguments are validated eagerly, raising `ValueError` with a clear message (see `TimeDelta.__init__`).
- Fields that contain other fields (`List.inner`, `Tuple.tuple_fields`, `Dict`) resolve classes and instances with `_resolve_field_instance`. In `_bind_to_schema` they deep-copy the inner fields and bind them to `self`.
- Write a docstring with `:param ...:` lines, in the style of the neighbouring classes.

## Validators
- Subclass `Validator`. Set `default_message`, store `self.error = error or self.default_message`, and implement `_repr_args` and `_format_error`.
- `__call__` returns the value unchanged on success and raises `ValidationError(message)` otherwise.

## Schema Meta options
- A new option is read in `SchemaOpts.__init__` with `getattr(meta, "name", default)` and validated there, so a bad value fails when the class is defined.
- Document it in the `Schema.Meta` docstring and its attribute annotations, next to the others.
- Fields are bound per schema instance in `Schema._bind_field` (on deep copies of the declared fields). Per-schema adjustments to fields belong there.
- Data keys: `field.data_key if field.data_key is not None else field_name` is the key used in input, output and error messages.

## Running tests
- `python -m pytest -q` from the project root runs the whole suite (about 1,200 tests, a few seconds). Run a single module with `python -m pytest -q tests/test_fields.py`.
