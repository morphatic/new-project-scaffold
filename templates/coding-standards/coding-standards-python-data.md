# Python data standards — data science, pipelines, and data quality

Binding guidelines for dataframe, pipeline, analysis, and data-quality code. **Additive to `coding-standards-python.md`** — everything there still applies. Load both files at the start of any data work session.

**Primary sources:**

1. [Polars user guide](https://docs.pola.rs/) — the default engine; its lazy/expression model governs how transforms are written here.
2. [pandera docs](https://pandera.readthedocs.io/) — schema-as-code, the mechanism for every data contract in this project.
3. [Apache Arrow / Parquet](https://arrow.apache.org/docs/) — the interchange and storage baseline.
4. [Soda Core](https://docs.soda.io/) and [Great Expectations](https://docs.greatexpectations.io/) — the opt-in monitoring layer (see "Data quality monitoring").

## Pipeline shape

Every data path is four separable stages, in separate modules. Do not fuse them.

```
ingest/   → raw I/O only. No business logic. Emits unvalidated frames.
contracts/→ pandera schemas. The only place shape/type/range is asserted.
transform/→ pure functions: validated frame in, validated frame out. No I/O.
serve/    → writes, APIs, reports, model training. No transforms.
```

The rule that makes this pay off: **`transform/` never reads a file, hits a network, or reads the clock.** A transform that takes its inputs as arguments is testable with a 20-row fixture; one that opens an S3 path is not testable at all. Inject `now` as a parameter — `DTZ` rules and reproducibility both depend on it.

## Dataframes

- **Polars is the default engine** for all pipeline and transform code.
- **pandas is permitted only at the boundary** where a downstream library requires it — scikit-learn, statsmodels, matplotlib/seaborn. Convert at that call site (`df.to_pandas()`), never earlier, and never let a pandas frame flow back upstream.
- **PySpark is the engine when the platform dictates it** (Databricks, EMR, Glue). Same contracts, same stage separation — pandera validates Spark frames too.
- **`narwhals` only for library code** that must accept a caller's dataframe of unknown type. It costs ~30–40% against raw Polars, so it is not a default; it is the right answer for a reusable package's public API.
- **Prefer `LazyFrame`.** Build the whole query, then `.collect()` once at the edge. An eager intermediate is a materialized copy that the optimizer can no longer push predicates through.
- **Never mix engines within a module.** One module, one dataframe type, declared in the annotations.

### Banned pandas patterns

When pandas is in play at a boundary, these are review blockers — each is a documented source of silent wrong answers, and each is one an LLM will produce by default if unconstrained:

- `inplace=True` — returns `None`, breaks chaining, and doesn't reliably avoid the copy anyway.
- Chained assignment (`df[df.a > 1]["b"] = x`) — writes to a temporary, silently loses the update.
- `iterrows()` / `itertuples()` / row-wise `.apply()` for anything vectorizable.
- Relying on the implicit index for alignment or joins. Reset it, or name the key and join on it explicitly.
- `pd.read_csv` without `dtype=` — type inference varies with the sample and turns an ID column into a float on the day a chunk is all-numeric.
- Bare `.merge()` without `how=` and `validate=`. `validate="one_to_one"` (or `"one_to_many"`) turns a silent fan-out into an exception.

## Data contracts

**Every frame crossing a module boundary has a pandera schema.** Untyped dataframes are the `Any` of data code — the type annotation says `DataFrame` and guarantees nothing about the 40 columns inside.

- Schemas are `DataFrameModel` classes in `contracts/`, versioned with the code, reviewed like any other type.
- Enforce with `@pa.check_types` on the function signature so the contract is declared in the annotation, not buried in the body.
- Declare, at minimum: column names, dtypes, nullability, and the primary key (`unique=True`). Add range/`isin`/regex checks wherever the domain has a real constraint.
- `strict = "filter"` or `strict = True` on ingest schemas — an unexpected new upstream column should be an event, not something that silently rides along into your warehouse.
- **Coerce at ingest, never mid-transform.** `coerce = True` belongs on the ingest schema; a transform that coerces is papering over an upstream contract break.
- Schema changes are semver-relevant. A narrowed constraint or a dropped column is a breaking change to every consumer.

## Data quality monitoring

Contracts catch shape. Monitoring catches *drift* — data that is still schema-valid and still wrong. Cover these six dimensions explicitly; a project that checks only the first two is not monitoring, it is asserting.

| Dimension | Question | Where it lives |
|-----------|----------|----------------|
| Schema | Did columns/types change? | pandera, at ingest |
| Volume | Is the row count within expected bounds? | monitoring layer |
| Freshness | Is the newest record as recent as it should be? | monitoring layer |
| Distribution | Have the mean / null-rate / cardinality shifted? | monitoring layer |
| Uniqueness | Are keys still unique? Duplicates introduced? | pandera + monitoring |
| Referential | Do foreign keys still resolve? | monitoring layer |

- **The in-process layer is pandera and is not optional.** It runs in the pipeline and fails the run.
- **The monitoring layer is opt-in per project**: `soda-core` when checks should be declarative YAML with alerting and anomaly detection over a warehouse; `great-expectations` when non-engineer stakeholders need to read Data Docs quality reports. Pick one per project and record the choice in `CLAUDE.md`. Do not run both.
- **Profiling is for humans, not for gates.** `ydata-profiling` on a new source produces the report you read once to *write* the contracts. Never wire a profiling run into CI — it is slow, non-deterministic on sampled data, and produces no pass/fail signal.
- **Every check declares its response**: fail the pipeline, quarantine the rows, or warn only. An alert nobody is required to act on trains the team to ignore alerts.
- Quality-check results are written as data (a table with run id, check name, status, observed value), not just logs. You cannot trend a log line.

## Nulls, types, and time

- **Distinguish "missing", "not applicable", and "zero".** Encoding all three as `null` destroys information no downstream consumer can recover. If the domain distinguishes them, the schema does too.
- **Never use `NaN` as a sentinel for missing in integer or categorical data.** Polars' null handling is type-preserving; use it.
- **Money is `Decimal` or integer minor units. Never float.** No exceptions.
- **All datetimes are timezone-aware and stored in UTC** (`DTZ` rules enforce the construction side). Convert to local only for display. A naive datetime in a pipeline is a bug waiting for a DST boundary.
- Be explicit about interval semantics — `[start, end)` half-open is the default here. Overlapping or ambiguous windows double-count.
- Column names are `snake_case` and stable. Renaming a column is a contract change.

## Reproducibility

- **Seed everything, once, in one place.** `random`, `numpy`, and any framework RNG. A helper `set_seeds(seed: int)` called at entry; the seed is a config value, logged with every run.
- **No absolute paths, no `~`, no hardcoded bucket names in code.** Paths come from settings (`pydantic-settings`).
- **Data is versioned or it is not an input.** A pinned snapshot, a table version, a partition date, or a content hash — recorded in the run's metadata. "Whatever was in the bucket that day" is not reproducible.
- **Parquet for every intermediate and output.** CSV is an interchange format for humans and legacy systems only: it has no types, no nulls distinct from empty strings, and no schema. If a CSV must be read, it is read once at ingest, with explicit dtypes, and immediately written as Parquet.
- Pipelines are idempotent — re-running the same stage on the same input yields the same output and does not double-write.

## Notebooks

Notebooks are for exploration. They are not a deployment artifact.

- **All notebooks live in `notebooks/`.** Nothing in `src/` ever imports from a notebook.
- **Notebooks contain no logic worth testing.** The moment a cell is worth reusing, it becomes a function in `src/` with a test, and the notebook imports it. A notebook is allowed to be a thin driver over tested code; it is not allowed to *be* the code.
- **Outputs are stripped on commit** (`nbstripout` in the pre-commit hook). Committed output cells bloat diffs, defeat review, and are the most common way credentials and PII leak into a repo.
- **Ruff formats and lints notebooks**; the docstring and annotation rules are relaxed there via `per-file-ignores`.
- **Prefer `marimo` for anything that must be reproduced or reviewed.** marimo notebooks are plain `.py` — they diff, review, type-check, and execute as scripts, and their reactive dataflow removes the hidden-state problem that makes under 4% of published `.ipynb` files reproducible. Use Jupyter where the platform requires it (Databricks, Colab, JupyterHub).
- Naming: `NN-short-description.ipynb` (`01-ingest-profiling.ipynb`) so reading order is obvious.

## Testing data code

- **Fixtures are small and hand-written** — 5 to 30 rows constructed inline, covering the null case, the boundary case, and the duplicate-key case. A test that loads a 2 GB production extract tests your network.
- **Test the transform, not the engine.** Assert on the frame your function returns; don't re-test that Polars can group by.
- **`hypothesis` for invariants** — round-trips, idempotence, and "output row count never exceeds input row count" are property tests, and pandera schemas can generate example data from a schema (`Schema.example()`).
- **Golden-file tests via `syrupy`** for report and aggregate outputs where the expected value is a table, not a scalar.
- **Contract tests run against real sources on a schedule, not in the PR gate.** Mark them `@pytest.mark.integration` and deselect by default — a PR that fails because an upstream vendor changed is a PR blocked on someone else's incident.
- Assert on frames with the engine's own comparator (`polars.testing.assert_frame_equal`), which reports the differing column instead of `False`.

## Models and ML

- **No `pickle` across a process, a machine, or a version boundary.** It is arbitrary code execution on load and it breaks on every library upgrade. Serialize to ONNX, a framework-native format, or explicit parameters.
- **Feature engineering lives in `transform/` and is shared between training and inference.** Two implementations of the same feature is the definition of training/serving skew.
- **Every training run records** the data version, the code commit, the seed, the hyperparameters, and the resulting metrics. Whether that is MLflow or a row in a table is a project choice; that it exists is not.
- Metrics are computed on a held-out split defined *before* the modeling work started, and the split rule is code, not a one-off notebook cell.

## Performance

- Profile before optimizing; `LazyFrame.explain()` shows what Polars will actually do.
- Push filters and column selection to the read (`scan_parquet` with predicate/projection pushdown), not after loading.
- Chunk or stream anything that doesn't fit comfortably in memory (`collect(engine="streaming")`); don't reach for a distributed engine before that fails.
- Reach for `duckdb` when the operation is naturally SQL over files — it composes with Polars via Arrow at zero copy.

## Privacy

- **PII never enters logs, exception messages, test fixtures, or committed notebook outputs.**
- Classify columns containing PII in the pandera schema (a field-level description or metadata tag) so the contract is the inventory.
- Mask or synthesize in non-production environments. A synthetic fixture generated from a schema is safer and faster than a scrubbed production sample.

## Blessed dependencies

| Need | Pick |
|------|------|
| Dataframes (default) | `polars` |
| Dataframes (boundary / ecosystem) | `pandas` |
| Dataframes (platform-mandated) | `pyspark` |
| Engine-agnostic library code | `narwhals` |
| Schema contracts | `pandera` |
| Quality monitoring (opt-in, one of) | `soda-core` *or* `great-expectations` |
| Exploratory profiling | `ydata-profiling` |
| In-process SQL / analytics | `duckdb` |
| Columnar interchange | `pyarrow` |
| Numerics | `numpy` |
| Classical ML | `scikit-learn` |
| Experiment tracking | `mlflow` |
| Notebooks (preferred) | `marimo` |
| Notebook hygiene (Jupyter) | `nbstripout` |
| Plotting | `plotly` (interactive) / `matplotlib` (static, publication) |
| Orchestration | `prefect` or `dagster` — project choice, recorded in `CLAUDE.md` |

## Judgment calls this doc has already made

- Polars is the default engine; pandas is a boundary adapter, not a peer.
- `narwhals` is for library APIs only — the overhead doesn't justify blanket use.
- pandera is mandatory and in-process; Soda/Great Expectations are the opt-in monitoring layer, and you run one, not both.
- Profiling (`ydata-profiling`) informs contract authoring and never gates CI.
- Notebooks are quarantined in `notebooks/`, import-only, output-stripped; `marimo` preferred where the platform allows.
- Parquet for intermediates; CSV only at the ingest edge.
- `pickle` is banned for model persistence.
- Transforms are pure and clock-free so they can be tested with tiny fixtures.
