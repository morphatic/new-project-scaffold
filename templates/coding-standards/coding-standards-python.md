# Python coding standards

Binding guidelines for Python code in this project. Load this file at the start of any Python work session. When in doubt, defer to the linked sources in that order.

Data science, dataframe, and data-quality work has **additional binding rules** in `coding-standards-python-data.md`. Load that file too when the project touches data.

**Primary sources:**

1. [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) — the most complete opinionated guide; governs anything this doc doesn't override.
2. [PEP 8](https://peps.python.org/pep-0008/) — baseline style. Enforced mechanically by Ruff, not by review.
3. [Python typing spec](https://typing.python.org/en/latest/spec/) — canonical semantics for annotations.
4. [PEP 621](https://peps.python.org/pep-0621/) / [PEP 735](https://peps.python.org/pep-0735/) — project metadata and dependency groups in `pyproject.toml`.

## Versions and layout

- **`requires-python = ">=3.12"`.** Develop and CI-default on the latest stable (3.14+). CI matrix tests the floor *and* the latest — a project that only tests one is claiming support it hasn't verified. The 3.12 floor exists so code stays runnable on managed platforms (Databricks Runtime, EMR, Glue) that lag CPython.
- **`src/` layout, always.** `src/<package>/`, tests in `tests/`. A flat layout lets tests import the working tree instead of the installed package, which hides packaging bugs until release.
- **`pyproject.toml` is the single source of truth.** No `setup.py`, `setup.cfg`, `.flake8`, `requirements*.txt`, `mypy.ini`, or `pytest.ini`. One file, one place to look.
- Runtime dependencies in `[project.dependencies]`; everything else in `[dependency-groups]` (`dev`, `test`, `docs`, …) per PEP 735. Not `tool.uv.dev-dependencies` — that predates the standard.
- **Commit `uv.lock`** for applications *and* libraries. Libraries don't ship it, but a reproducible CI run is worth more than the purity argument.

## Toolchain

Four tools, no substitutions. Each has a single job and a `pyproject.toml` section.

| Job | Tool | CI command |
|-----|------|-----------|
| Environments, deps, Python installs | `uv` | `uv sync --locked` |
| Lint + format | `ruff` | `ruff check .` then `ruff format --check .` |
| Type check | `mypy` (strict) | `mypy src tests` |
| Test | `pytest` | `pytest` |

CI runs them in that order and never with `--fix`/auto-format — a CI job that mutates the tree hides the failure it should report.

## Typing

- **Every function is annotated** — parameters and return. `ANN` rules enforce it; `mypy --strict` is the gate.
- **`Any` is banned** (`ANN401`). Use `object` for "truly anything, will narrow", a `Protocol` for structural shapes, `TypeVar` for generics. If `Any` is genuinely unavoidable, confine it to one line with `# type: ignore[code]` plus a reason comment. Blanket `# type: ignore` is banned (`ignore-without-code`).
- **Modern syntax only:** `list[str]` not `List[str]`, `X | None` not `Optional[X]`, `type` aliases (PEP 695) where the floor allows. `from __future__ import annotations` at the top of every module — required by isort config.
- **`TypedDict` / `dataclass` / `Protocol` over bare `dict`.** A `dict[str, Any]` crossing a function boundary is an untyped API wearing a type annotation.
- **`Final` for module constants**, `Literal` for closed string sets, `NewType` for semantic IDs (`UserId = NewType("UserId", str)`) so an order ID can't be passed where a user ID belongs.
- **Frozen dataclasses for internal records:** `@dataclass(frozen=True, slots=True, kw_only=True)`. Pydantic is for *validating untrusted input at I/O boundaries*, not for internal plumbing — it costs runtime validation on every construction.
- Narrow with `TypeGuard`/`TypeIs`, not `cast()`. Every `cast()` is an unchecked assertion; treat it like `unsafe`.

## Errors

- **Define a package exception hierarchy.** One base (`class ProjectError(Exception)`), specific subclasses beneath it. Callers catch your base, never `Exception`.
- **Never `except:` or `except Exception:` without re-raising.** Catch the narrowest type that can actually be raised. Bare `except` that swallows is a `TRY` violation and a review blocker.
- **Chain, don't discard:** `raise ParseError(msg) from err`. Use `from None` only when the inner exception is genuinely noise, and say why.
- **No control flow through exceptions across module boundaries.** Expected, routine outcomes ("not found", "invalid input") return a value or a `None`; exceptions are for the abnormal.
- **Error messages are assigned first** (`EM` rules): `msg = f"..."` then `raise ValueError(msg)`. Keeps tracebacks readable and messages greppable.
- **Never `assert` for runtime validation** — `-O` strips it. `assert` is for tests and internal invariants only (`S101`).

## Naming and structure

- `snake_case` functions/variables/modules; `PascalCase` classes; `SCREAMING_SNAKE_CASE` constants; `_leading_underscore` for module-private.
- **No relative imports** (`ban-relative-imports = "all"`). Absolute imports from the package root — an agent moving a file shouldn't have to rewrite import graphs.
- **Modules under ~500 lines, functions under ~50.** Not a lint rule, a review heuristic: past that, an agent reading the file spends its budget on context instead of the change.
- **No wildcard imports.** `__init__.py` may re-export the package's public API with an explicit `__all__`; nothing else re-exports.
- **No mutable default arguments**, no work at import time beyond constant definition. Import must be free of side effects.
- Prefer `pathlib.Path` over `os.path` (`PTH` rules). Prefer f-strings; `%`-formatting only in logging calls.

## Docstrings

- **Google style** (`Args:` / `Returns:` / `Raises:`), enforced by Ruff's `D` rules with `convention = "google"`.
- Every public module, class, and function has one. First line is an imperative one-sentence summary ending in a period.
- Document `Raises:` for every exception the caller is expected to handle. Don't restate types the annotation already gives.
- Private helpers need a docstring only when *why* isn't obvious from the name.

## Logging

- **`structlog` with JSON output in production, console renderer locally.** Log records are data consumed by machines; a human-formatted string is a parsing problem you're handing to your future self.
- **Never log secrets, credentials, tokens, or PII.** Redact at the processor level so it can't be forgotten at a call site.
- `logger.info("event_name", key=value)` — event names are stable identifiers, context goes in fields. Never f-strings in log calls (`G` rules).
- `print()` is banned outside CLI entry points (`T20`).

## Testing

- **`tests/` mirrors `src/`.** `test_<module>.py`, one test file per source module.
- **Arrange-Act-Assert, one behavior per test.** Test names describe the behavior: `test_rejects_negative_quantity`, not `test_validate_2`.
- **`pytest` fixtures over `setUp`.** No `unittest.TestCase` in new code.
- **`hypothesis` for anything with a parsing, encoding, or invariant claim.** Property tests catch the input classes an example-based test never enumerates.
- **`pytest-bdd`** runs the repo-root `features/` Gherkin suite; step definitions in `tests/features/`.
- **Coverage ≥ 80% with branch coverage on**, enforced by `--cov-fail-under`. Coverage is a floor for noticing untested modules, not a goal.
- `filterwarnings = ["error"]` and `xfail_strict = true`. A `DeprecationWarning` you can't see is a migration you'll do under time pressure later.
- **Never skip or disable a failing test to go green** — see the repo's working agreement. The `tdd-guard` hook blocks `@pytest.mark.skip`, `skipif`, and `xfail` additions in test files.

## Security

- Ruff's `S` rules (bandit) are on. Never suppress `S` without a written justification on the `noqa`.
- **No secrets in code or in the repo.** Read from environment via `pydantic-settings`; `.env` is git-ignored and never committed.
- **Never `pickle`, `eval`, `exec`, or `yaml.load` untrusted input.** Use `yaml.safe_load`, JSON, or a typed parser.
- Subprocess calls: list form, `shell=False`, never interpolate user input into a command string.
- `pip-audit` runs in CI against the locked environment.

## Configuration reference

The `pyproject.toml` sections the bootstrap writes — treat these as the baseline, not a starting suggestion:

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
  "F", "E", "W", "I", "N", "D", "UP", "ANN", "ASYNC", "S", "B", "A", "C4",
  "DTZ", "EM", "FA", "ISC", "LOG", "G", "INP", "PIE", "T20", "PT", "RET",
  "SLF", "SIM", "TID", "TC", "ARG", "PTH", "ERA", "PL", "TRY", "PERF",
  "FURB", "RUF",
]
ignore = [
  "E501",    # line length is the formatter's job
  "D203",    # conflicts with D211
  "D213",    # conflicts with D212
  "ISC001",  # conflicts with the formatter
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D103", "PLR2004", "SLF001", "ANN201"]
"__init__.py" = ["F401"]  # explicit public re-exports only, with __all__

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

[tool.ruff.lint.isort]
required-imports = ["from __future__ import annotations"]

[tool.ruff.format]
docstring-code-format = true

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool", "possibly-undefined"]
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers --strict-config --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=80"
xfail_strict = true
filterwarnings = ["error"]
```

Do NOT use `select = ["ALL"]`. It silently enables every new rule on each Ruff upgrade, which turns a patch bump into an unplanned refactor — unacceptable in a codebase multiple people maintain. Add prefixes deliberately. Per-project deviations go in the same table with a comment saying why.

An untyped third-party dependency gets a scoped override, never a global relaxation:

```toml
[[tool.mypy.overrides]]
module = ["some_untyped_lib.*"]
ignore_missing_imports = true
```

## Blessed dependencies

Reach for these before rolling your own or picking from search results.

| Need | Pick |
|------|------|
| Package / env / Python manager | `uv` |
| Lint + format | `ruff` |
| Type check | `mypy` (CI gate); `ty` optionally for fast local feedback |
| Tests | `pytest` + `pytest-cov` + `pytest-mock` |
| Property tests | `hypothesis` |
| BDD / Gherkin | `pytest-bdd` |
| Snapshot tests | `syrupy` |
| Test data factories | `polyfactory` |
| I/O-boundary validation | `pydantic` v2 |
| App settings / secrets | `pydantic-settings` |
| Logging | `structlog` |
| HTTP client | `httpx` |
| Web API | `fastapi` |
| CLI | `typer` (stdlib `argparse` when zero-dep matters) |
| SQL | `sqlalchemy` 2.0 typed API + `alembic` |
| Retries / backoff | `tenacity` |
| Dates / times | stdlib `datetime`, always tz-aware via `zoneinfo` |
| Dependency audit | `pip-audit` |

## Judgment calls this doc has already made

- `uv` over Poetry/pip-tools/PDM — one tool for envs, deps, lockfiles, and Python installs.
- `mypy --strict` as the CI gate, not `pyright` or `ty`. mypy's plugin system is what makes Pydantic and pandera schemas actually type-check; `ty` is still 0.0.x beta as of mid-2026 and not a defensible enterprise gate.
- Google docstring style over NumPy style — more compact, less context cost per file, and cited by the primary source.
- Frozen dataclasses internally, Pydantic only at I/O boundaries.
- Exceptions over `Result` types — Pythonic, and the ecosystem gives no support for the alternative.
- Curated Ruff `select` list over `ALL` — upgrade stability beats maximal coverage in a shared codebase.
- 3.12 floor (managed-platform reality) with latest-stable development.
- `pytest-bdd` over `behave` — shares pytest's fixtures, coverage, and plugins instead of running a parallel test stack.
