# A real project for the long task

The current long task (`demo-long/`) peaks at about 17k tokens of context in about 19 turns (`results-compaction.md`). That is too small for context compaction to pay off. The goal is 50+ turns and a 40–80k+ token peak.

**Plan.** We will vendor a pinned, stripped snapshot of a real Python library (no docs, CI files or git history) and write 3–4 detailed feature tickets with exact APIs. Each ticket gets hidden acceptance tests. The agent works through the tickets one after another in a single session, with one CI run (`ci_run_pipeline`, i.e. pytest) per ticket. Runs are judged by the hidden tests plus a manual review of the diff. This doc picks the project. Benchmark task formats are out of scope.

**Constraints on the project:**
- Pure Python, and used by a public coding benchmark.
- Permissive license (MIT, BSD or Apache) and under about 2 MB once stripped.
- `uv venv && uv pip install -e .` followed by pytest works with no system dependencies.
- The test suite runs offline, deterministically, in under about 30 s.

Researched 2026-11-14. Citations are URLs or `repo:path:Lstart-Lend`. "UNVERIFIED" marks claims I could not trace to a source, and "Inference" marks my own reasoning.

**How the numbers were measured:**
- Each repo was shallow-cloned under `/tmp`.
- Line counts are `wc -l` over `.py` files, blank lines included.
- Tests ran on Python 3.12 in a uv venv, 3 times with the network disabled (`unshare -rn`), and once more in random order with `pytest-randomly`.
- "Stripped" means the package source, tests, `pyproject.toml`/`setup.*`, LICENSE and README, with `__pycache__` removed.

## Which repos the benchmarks use

| Benchmark | Python repos | Small pure-Python ones |
|---|---|---|
| SWE-bench Verified / Lite test ([HF](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified)) | 12 large repos: django, sympy, sphinx, matplotlib, scikit-learn, astropy, xarray, pytest, pylint, requests, seaborn, flask | none (requests and flask are mid-size) |
| SWE-bench full, `dev` split ([HF](https://huggingface.co/datasets/princeton-nlp/SWE-bench)) | marshmallow, sqlfluff, pvlib, pydicom, astroid, … | **marshmallow** (9 instances, e.g. `marshmallow-code__marshmallow-1359`) |
| SWE-Gym ([HF](https://huggingface.co/datasets/SWE-Gym/SWE-Gym)) | 11 large repos: pandas, MONAI, moto, mypy, dvc, dask, modin, pydantic, conan, hydra, bokeh | none |
| SWE-bench-Live ([HF](https://huggingface.co/datasets/SWE-bench-Live/SWE-bench-Live)) | 200+ repos | tablib, pyjwt, attrs, freezegun, transitions, structlog, arrow |
| SWE-Bench Pro ([HF](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro)) | ansible, openlibrary, qutebrowser (plus Go/JS/TS) | none |
| FEA-Bench ([HF](https://huggingface.co/datasets/microsoft/FEA-Bench), 1,401 rows, 83 repos) | sympy, faker, conan, sqlglot, scikit-learn, … | lark, h2, pygments, prometheus client (5–10 instances each) |
| FeatBench ([HF](https://huggingface.co/datasets/PGCodeLLM/FeatBench), 156 rows) | conan (56), xarray, smolagents, starlette, … | pyjwt (3) |
| NoCode-bench, now Doc2Feat-bench ([GitHub](https://github.com/NoCode-bench/NoCode-bench), [HF](https://huggingface.co/datasets/Doc2Feat-bench/Doc2Feat-bench_Full), 634 rows) | scikit-learn, astropy, xarray, sphinx, seaborn, django, matplotlib, pylint, pytest, requests | none |
| Commit0 ([HF](https://huggingface.co/datasets/commit0/commit0), 54 libraries) | networkx, jinja, attrs, pydantic, … | **tinydb**, **marshmallow**, voluptuous, cachetools, pyjwt, sqlparse, more-itertools |
| ChainSWE ([arXiv 2607.02606](https://arxiv.org/abs/2607.02606), [HF](https://huggingface.co/datasets/C-lister/ChainSWE)) | 80 repos in the `unique` split | **pypika** (2 rows), apiflask, wtforms, tablib, packaging, Python-Markdown |
| Compact-Bench ([arXiv 2610.31710](https://arxiv.org/abs/2610.31710)) | 35 SWE-bench repairs on pytest, sympy, xarray, pylint, requests, sphinx, flask | none |

**Notes on the table:**
- I read the repo lists from each dataset's parquet file, fetched through `https://datasets-server.huggingface.co/parquet?dataset=…`.
- The SWE-bench-Live, SWE-Bench Pro and Compact-Bench lists come from a delegated check and were not re-read.
- I found no Microsoft Research "CompactionBench". The nearest match, [CompactBench](https://compactbench.github.io/compactbench), scores how well a summary of a conversation keeps facts and has no code repos.

## Candidates

I also measured voluptuous, wtforms, tablib, lark and pyjwt. All of them pass offline: voluptuous in 0.4 s, wtforms in 1.1 s, tablib in 1.7 s, lark in 7.3 s and pyjwt in 6.1 s. They are less of a fit for the reasons below.
- **voluptuous** (3.5k lines) is small, and its schemas are an unusual DSL.
- **wtforms** and **tablib** are fine, but neither appears in the benchmarks I checked myself.
- **lark** is a parser generator, so feature tickets need deep algorithmic context.
- **pyjwt** needs the `cryptography` wheel.
- **prometheus_client** needs `asgiref` before test collection even succeeds.

| | **marshmallow** | **pypika** | **tinydb** |
|---|---|---|---|
| What it is | Object (de)serialization and validation | SQL query builder | Document database backed by a JSON file |
| Used by | SWE-bench `dev` split, Commit0 | ChainSWE | Commit0 |
| License | MIT | Apache-2.0 | MIT |
| Pinned commit | tag `4.4.0` = `a38b7f6842042e65fd1a485ed152ca99f87880c0` (2026-11-03) | `master` `0653551bb3846da46599c5e8e10450ae481d917a` (2026-11-12); last tag `v0.51.1` | tag `v4.8.2` = `10644a0e07ad180c5b756aba272ee6b0dbd12df8`; `master` `edff96aeb261` |
| Source / test lines | 5,037 / 10,192 (at 4.4.0) | 6,584 / 10,793 | 2,303 / 2,202 |
| Stripped snapshot | 648 KB, 38 files | 824 KB, 68 files | 208 KB, 24 files |
| Runtime deps | none (`dependencies = []`) | none on Python ≥ 3.11 | none |
| Test deps | pytest, simplejson | pytest, parameterized | pytest, pyyaml |
| Python | ≥ 3.11 | ≥ 3.8 (UNVERIFIED for the upper bound) | ≥ 3.10 |
| Suite, offline | 1,192 passed in 0.8 s; random order OK | 1,228 passed in 0.8 s; random order OK | 228 passed in 0.7 s; random order OK |
| Largest files | `fields.py` 2,143, `schema.py` 1,253, `validate.py` 708 | `queries.py` 2,309, `terms.py` 1,907, `dialects.py` 1,077 | `table.py` 854, `queries.py` 535 |

### marshmallow

**Layout.** It is a flat package under `src/marshmallow/`:
- `fields.py`: one class per field type (`String`, `Number`, `DateTime`, `TimeDelta`, `Enum`, `IP`, …), each with `_serialize`/`_deserialize` and a `default_error_messages` dict.
- `validate.py`: `Validator` subclasses (`Range`, `Length`, `OneOf`, `ContainsOnly`, …).
- `schema.py`: `Schema` and its `Meta` options, `dump`/`load`, and hooks.
- `decorators.py`, `exceptions.py` and `error_store.py`.

**Approachability.** Every new field or validator follows the same pattern, and the tests mirror it (`tests/test_fields.py`, `tests/test_validate.py`, `tests/test_serialization.py`, …). Grep finds things easily.

**Setup quirks:**
- The `src/` layout means the vendored copy needs `pythonpath = ["src"]` in its pytest config, or an editable install. With that option, a bare venv holding only pytest and simplejson ran the stripped copy offline: 1,192 passed in 1.6 s.
- `tests/mypy_test_cases` is already excluded by `norecursedirs` (`marshmallow:pyproject.toml:L150-151`).

**Ticket ideas.** None of these exists upstream; I checked by grepping the class names in `fields.py`, `validate.py` and `schema.py`.
1. **`fields.Duration`** (~120 lines). ISO 8601 durations (`P1DT2H30M`, `PT0.5S`, `-P3D`) to and from `timedelta`.
   - Options: `precision` (truncate to seconds or microseconds).
   - Rejects years and months with a clear error, because they are ambiguous.
   - Error keys `invalid` and `ambiguous`.
   - Edge cases: zero (`PT0S`), negatives, fractional seconds, lowercase input.
2. **`validate.Unique(key=None, error=...)`** (~60–80 lines). A validator that fails on collections with duplicate items.
   - `key` can be an attribute name, a dict key or a callable.
   - The message formats `{duplicates}` in first-seen order.
   - Unhashable items need a defined behaviour.
3. **`Meta.key_case = "camel"`** (~100–150 lines in `schema.py`). Snake_case attribute names become camelCase data keys on dump, and are mapped back on load.
   - An explicit `data_key` wins.
   - The option is inherited by subclasses and does not leak into `Nested` schemas unless they set it themselves.
   - Unknown-field handling must use the converted names.
4. **`fields.Union(fields, dump_map=None)`** (~150 lines).
   - Load tries the candidate fields in order and returns the first success. If all fail, it raises one `ValidationError` whose messages are keyed by candidate index.
   - Dump picks a field by `isinstance` via `dump_map`, falling back to trying candidates in order.
   - Inference: a model may recall the third-party `marshmallow-union` package, so the ticket must pin the exact API and error shape.
5. (spare) **`Meta.dump_skip_none = True`** (~40 lines). Omit keys whose value is `None` on dump, overridable per field.

Tickets 1 and 4 both touch `fields.py` but add separate classes, so they do not conflict when done in sequence (Inference).

### pypika

**Layout:**
- `queries.py`: `Query`, `QueryBuilder`, joins, and the CREATE/DROP builders.
- `terms.py`: `Term`, `Criterion`, `Field` and `Case`.
- `functions.py`: SQL function classes.
- `dialects.py`: MySQL, Postgres, Oracle, MSSQL, ClickHouse and others.

**Approachability.** The builder pattern is uniform (`@builder` methods that return a copy). The SQL string tests (`pypika/tests/test_*.py`) are a good template for hidden tests: they assert on exact output.

**Snapshot caveats:**
- The tests live inside the package (`pypika/tests/`), so hidden tests would need their own directory.
- The repo ships an agent instruction file (`CLAUDE.md`), which must be stripped.

**Ticket ideas:**
1. **`Query.merge_into(table).using(src).on(cond).when_matched_update(...).when_not_matched_insert(...)`** (~200–300 lines). `MERGE` does not exist today: `merge` appears 0 times in `queries.py`.
2. **`Greatest`/`Least`, plus `Query.truncate(table)`** (~60–100 lines). Neither exists (I grepped for them).
3. **CHECK constraints in `CreateQueryBuilder`** (`.check(criterion, name=None)`, ~80 lines).
4. **Postgres `EXPLAIN [ANALYZE] [(FORMAT JSON)]` prefix** on any query (~60 lines).

**Fit.** Inference: SQL string output makes the hidden tests exact. The downside is that runs can differ in quoting and whitespace unless the ticket gives full expected strings.

### tinydb

**Layout.** Only six real modules:
- `table.py`: `Table` with insert, search, update, upsert and remove.
- `queries.py`: `Query`, `where`, and the operators `matches`, `any`, `all`, `one_of` and `fragment`.
- `storages.py`, `middlewares.py` (`CachingMiddleware`), `operations.py` and `database.py`.

**Approachability.** It is the easiest of the three to grep. Its `pytest.ini` sets `addopts` with `--cov`, which must be removed in the snapshot (`tinydb:pytest.ini`).

**Ticket ideas:**
1. `Query.between(lo, hi, inclusive=True)` (~40 lines).
2. `Table.search(cond, order_by=..., limit=..., offset=...)` (~80 lines).
3. Unique-field constraints, `db.table("users", unique=["email"])`, raising `DuplicateError` on insert, update and upsert (~120 lines).
4. `ExpiringMiddleware(ttl_field=..., clock=...)`, which hides and purges expired documents (~120 lines).

**Fit.** Inference: at 2.3k source lines, the whole codebase costs only about 20k tokens to read, so it may not reach a 40–80k peak even with four tickets.

## Recommendation

**Use marshmallow at tag `4.4.0` (`a38b7f6842042e65fd1a485ed152ca99f87880c0`, MIT).** Reasons:
- It is in SWE-bench (the `dev` split) and Commit0.
- It has no runtime dependencies.
- The stripped snapshot is 648 KB.
- The 1,192 tests run in under 2 s, offline and in random order.
- The field, validator and `Meta`-option pattern makes tickets with exact APIs natural.

Inference: `fields.py` alone is about 2.1k lines (roughly 20k tokens). Four tickets that each need `fields.py`/`schema.py`, the matching tests, and a CI log should plausibly push the peak into the 40–80k range. This is UNVERIFIED until measured.

**Setup:**

```sh
git clone --depth 1 --branch 4.4.0 https://github.com/marshmallow-code/marshmallow.git /tmp/mm
mkdir demo-mm && cp -r /tmp/mm/{src,tests,pyproject.toml,LICENSE,NOTICE,README.rst} demo-mm/
find demo-mm -name __pycache__ -prune -exec rm -rf {} +
# add pythonpath = ["src"] under [tool.pytest.ini_options] in demo-mm/pyproject.toml
uv add --dev simplejson      # the tests import it; the harness venv already has pytest
cd demo-mm && uv run pytest -q  # expect 1192 passed
```

**Fallback.** pypika (`0653551bb384`, Apache-2.0) is the fallback, as a larger codebase with exact-output tests. tinydb is the fallback if a smaller, faster-to-read project is wanted.

**Risks:**
- **Ambiguous tickets.** Runs will diverge on error-message text, ordering and edge cases unless each ticket fixes the API, the error keys and messages, and 3–5 worked examples. Hidden tests should assert only what the ticket states.
- **Recall and contamination.** Models have seen marshmallow, and similar features exist in third-party packages (marshmallow-union, isodate). Exact specs limit the drift. If upstream later adds the same feature, the pinned tag keeps the snapshot fixed.
- **Environment drift.** Pin the tag and keep the snapshot in the repo. `simplejson` is the only extra test dependency. Python must be ≥ 3.11, and the harness requires ≥ 3.12.
- **Flaky tests.** None seen: 4 offline runs, one of them in random order, all gave the same result. Hidden tests should avoid wall-clock time; for `Duration`, use fixed `timedelta` values.
- **Reading cost varies.** An agent that greps instead of reading `fields.py` whole will have a much lower peak. Measure the peak on a first batch of runs before fixing compaction thresholds.
