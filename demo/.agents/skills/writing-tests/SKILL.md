---
name: writing-tests
description: Conventions for writing and organising pytest tests in this team's projects. Use when adding, changing, or reviewing tests.
---
# Writing tests

- Tests live in `tests/`, one file per module: `tests/test_<module>.py`.
- Name tests after the behaviour: `test_refund_capped_at_remaining`, not `test_refund_2`.
- One behaviour per test. Several asserts are fine when they check the same behaviour.
- Use plain `assert`; no `unittest.TestCase`.
- Use `pytest.raises` for errors, and match the message when it matters: `pytest.raises(ValueError, match="positive")`.
- Use `pytest.mark.parametrize` when the same behaviour is checked for several inputs, e.g. every currency.
- No network, no clock, no randomness in unit tests. Inject them.
- Write the expected value as a literal with a comment showing the human-readable meaning, e.g. `== 1_495  # $10.00 -> ¥1495`.
- A bug fix comes with a test that fails before the fix and passes after.
- Never delete or loosen an existing test to make a build green. If you believe a test is wrong, explain why in the issue or PR.

Run the suite with `python -m pytest -q`.
