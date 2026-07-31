---
description: Bootstrap a Python stack in the current project — installs tooling, writes configs, copies the Python coding standards into plinth/, adds a Python CI job
---

# /bootstrap-python

Bootstrap a Python stack. Run this after the NLSpec has identified Python as the chosen language (or identified Python as one of several languages in a monorepo).

## Ground rules

**Always check current stable versions at runtime.** Do not trust version numbers from training data or from any doc in this repo. Before adding any dependency or pinning any version, look it up:

- Python: `uv python list --only-downloads` for available interpreters; the [CPython release schedule](https://devguide.python.org/versions/) for what is still supported.
- Tools: `uv --version`, `uvx ruff --version`, `uvx mypy --version`.
- Packages: `uv add <pkg>` resolves the latest compatible version automatically — prefer it over writing a pin by hand.

## Step 0 — Determine target directory

Decide where this bootstrap writes. Resolve `$TARGET` (a path relative to the repo root) **before any write**. The later steps use `$TARGET` everywhere that would have previously meant "repo root."

Decision inputs, in order:

1. **Explicit positional arg.** If the user invoked `/bootstrap-python <path>`, use that path. Skip to the "decision" below.
2. **Workspace markers at repo root.** Any of these means the root is already claimed by a workspace and you MUST target a subdirectory:
   - Root `pyproject.toml` has a `[tool.uv.workspace]` section.
   - Root `Cargo.toml` has a `[workspace]` section (hybrid Rust+Python monorepo).
   - `pnpm-workspace.yaml` exists at repo root, or root `package.json` has a `"workspaces"` field.
3. **NLSpec signals.** Read `plinth/specs/*.nlspec.md` (prefer the top-level spec). Look for §2 Architecture describing more than one deployable, stack declarations naming multiple runtimes, or explicit mentions of monorepo / workspace / `apps/` / `packages/`.
4. **Existing monorepo layout.** `apps/`, `crates/`, `packages/` directories already present at repo root.

Decision:

| Inputs | Action |
|--------|--------|
| Explicit arg given | `TARGET=<arg>`. Skip detection. |
| Workspace markers present, no arg | Propose `packages/<name>` informed by the NLSpec (e.g., `packages/ingest`). Ask the user to confirm before proceeding. |
| NLSpec clearly multi-component, no workspace markers yet | **Stop.** Tell the user to run `/bootstrap-monorepo` first. Do not write anything. |
| Ambiguous | Ask the user with a specific proposal. Do not guess silently. |
| Clearly single-component | `TARGET=.` — proceed at repo root. |

Workspace-mode flag: treat `$TARGET != "."` as "workspace mode." In workspace mode, shared configs (Ruff, mypy, the lockfile, CI, release-please) live at repo root; only `[project]` metadata and package-specific dependencies live in `$TARGET/pyproject.toml`.

## Step 0b — Determine the data profile

Decide whether this is a **data project**. It is if the NLSpec mentions any of: dataframes, ETL/ELT, pipelines, analytics, warehouses, data quality, profiling, machine learning, model training, notebooks, or a specific engine (Polars, pandas, Spark, DuckDB, Databricks).

If the signal is ambiguous, ask the user directly: *"Is this a data / analytics project? It determines whether I install the dataframe + data-contract stack and copy the data standards."*

Set `$DATA=yes|no`. Steps below branch on it.

## Steps

### 1. Load the standards

Read `~/dev/new-project-scaffold/templates/coding-standards/coding-standards-python.md`. Binding style guide for Python in this project — every decision below flows from it.

If `$DATA=yes`, also read `coding-standards-python-data.md` from the same directory.

### 2. Copy the standards into the project

Copy to `plinth/coding-standards-python.md` (always at repo root — the standards are shared regardless of `$TARGET`).

If `$DATA=yes`, also copy `coding-standards-python-data.md` to `plinth/coding-standards-python-data.md`.

Then add a line to the repo's `CLAUDE.md` telling every future session to load them.

### 3. Check prerequisites

Run `uv --version`. If missing, tell the user to install it (`curl -LsSf https://astral.sh/uv/install.sh | sh`, or `winget install astral-sh.uv` / `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` on Windows) and stop.

`ruff`, `mypy`, and `pytest` do NOT need to be installed globally — they come in as dev dependencies and run via `uv run`.

### 4. Initialize the project

Create `$TARGET` if it doesn't exist. Run in `$TARGET`:

```bash
uv init --lib --vcs none --python 3.12
```

`--lib` gives the `src/` layout the standards require. Use `--app` only if the NLSpec describes a pure executable with no importable package — and even then, restructure to `src/` afterward.

Verify the result is `src/<package>/`, not a flat module. If `uv init` produced a flat layout, move it.

**Workspace mode:** confirm `$TARGET` is covered by root `[tool.uv.workspace].members` (typically `["packages/*"]`). Add it explicitly if not. Run `uv sync` from the repo root — the workspace shares one `uv.lock` and one `.venv`.

### 5. Pin the interpreter

Write `.python-version` at repo root with the **latest stable** CPython you verified in Ground Rules (3.14+). Set `requires-python = ">=3.12"` in `pyproject.toml` — the floor is deliberately lower than the dev version so the code stays runnable on managed platforms that lag CPython. Do not raise the floor without the user's OK.

### 6. Write config files

Write the `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.lint.per-file-ignores]`, `[tool.ruff.lint.pydocstyle]`, `[tool.ruff.lint.flake8-tidy-imports]`, `[tool.ruff.lint.isort]`, `[tool.ruff.format]`, `[tool.mypy]`, and `[tool.pytest.ini_options]` sections from the "Configuration reference" in the standards doc. Everything goes in `pyproject.toml` — do not create `ruff.toml`, `mypy.ini`, `pytest.ini`, or `setup.cfg`.

Adjust from the reference as follows:

- `[tool.ruff].target-version` and `[tool.mypy].python_version` both track the `requires-python` **floor**, not the dev version.
- `[tool.ruff.lint.isort].known-first-party` = the package name.
- Drop `plugins = ["pydantic.mypy"]` if Pydantic isn't a dependency.
- If `$DATA=yes`, add `"PD"` and `"NPY"` to `select`, and add a `per-file-ignores` entry for notebooks:
  `"notebooks/**" = ["D", "ANN", "T20", "E402", "INP001", "ERA001"]`.

**Workspace mode:** these sections go in the **root** `pyproject.toml`; Ruff and mypy both walk up to it. `$TARGET/pyproject.toml` carries only `[project]` and its own dependencies.

### 7. Add dependencies

Runtime dependencies go in `[project.dependencies]` via `uv add`. Dev tooling goes in PEP 735 dependency groups via `uv add --group`:

```bash
uv add --group dev ruff mypy
uv add --group test pytest pytest-cov pytest-mock hypothesis pytest-bdd
```

Then add what the NLSpec calls for, using the "Blessed dependencies" table in the standards doc. Look up current versions at runtime — `uv add` handles this.

If `$DATA=yes`, add the data stack from the data standards' blessed-dependency table. Baseline for almost any data project:

```bash
uv add polars pandera pyarrow
uv add --group dev ydata-profiling   # profiling is a dev/exploration tool, never a CI gate
```

Add `pandas` only if a boundary library (scikit-learn, statsmodels, matplotlib) actually requires it. Add `soda-core` or `great-expectations` only if the NLSpec calls for a monitoring layer — ask the user which, present the tradeoff from the data standards doc, and record the choice in `CLAUDE.md`. Do not add both.

Do NOT use `tool.uv.dev-dependencies` — it predates PEP 735.

### 8. Create the source and test layout

```
src/<package>/__init__.py
tests/
```

If `$DATA=yes`, also create the four-stage layout from the data standards and a notebooks directory:

```
src/<package>/ingest/
src/<package>/contracts/
src/<package>/transform/
src/<package>/serve/
notebooks/
```

Each with an `__init__.py` carrying a one-line module docstring naming the stage's responsibility (`D104` requires it, and it tells the next agent where code belongs).

### 9. Update `.gitignore`

Ensure these are present at the **repo-root** `.gitignore`:

```
__pycache__/
*.py[cod]
.venv/
.mypy_cache/
.ruff_cache/
.pytest_cache/
.coverage
coverage.xml
htmlcov/
*.egg-info/
```

If `$DATA=yes`, also add `.ipynb_checkpoints/`, `data/raw/`, and `data/interim/` — raw and intermediate data are reproducible artifacts, not source. (`data/` itself stays tracked so the directory structure survives.)

**Commit `uv.lock`** — for applications and libraries alike. In workspace mode there is one lockfile at repo root.

### 10. Install dev tooling hooks

If `$DATA=yes` and Jupyter notebooks will be used, wire `nbstripout` into the repo's lefthook pre-commit stage so output cells are stripped before commit. This is a leak-prevention control, not a style preference — say so when you report it.

```bash
uv add --group dev nbstripout
```

Add to `lefthook.yml` under `pre-commit.commands`:

```yaml
  nbstripout:
    glob: '*.ipynb'
    run: uv run nbstripout {staged_files}
    stage_fixed: true
```

### 11. Add a Python CI job

Open `.github/workflows/ci.yml`.

**Single-app mode (`$TARGET == "."`):** replace the placeholder step in the existing `test` job with:

```yaml
- uses: astral-sh/setup-uv@v9
  with:
    enable-cache: true
- run: uv python install
- run: uv sync --locked --all-groups
- run: uv run ruff check --output-format=github .
- run: uv run ruff format --check .
- run: uv run mypy src tests
- run: uv run pytest
```

Look up the current major of `astral-sh/setup-uv` before writing it — do not copy the version above blind.

Order matters: lint, then format, then types, then tests. Never pass `--fix` or run `ruff format` without `--check` in CI — a CI job that mutates the tree hides the failure it should report.

Add a Python version matrix testing the `requires-python` floor and the latest stable:

```yaml
strategy:
  matrix:
    python-version: ['3.12', '3.14']
```

...with `uv python install ${{ matrix.python-version }}` and `uv sync --locked --all-groups --python ${{ matrix.python-version }}`.

**Workspace mode (`$TARGET != "."`):** add a new named job derived from the target leaf. Do NOT modify the generic `test` job. Scope the commands with `--package <name>` (`uv sync --locked --package <name>`) and point `mypy`/`pytest` at `$TARGET`. Then append the job name to the aggregate `ci` job's `needs:` list.

Also open `.github/workflows/audit.yml` and uncomment the Python (uv) block so `pip-audit` gates on advisories against the locked environment.

### 12. Scaffold a minimal failing test

Per the TDD pattern the tdd-guard hook enforces, write one failing test in `tests/test_<package>.py`. This confirms the harness works and gives the first iteration a red-to-green target.

If `$DATA=yes`, make it a contract test: a pandera `DataFrameModel` in `contracts/` plus a test asserting a bad frame is rejected. That establishes the data-contract pattern in the first commit, which is when it is cheapest to establish.

### 13. Wire up pytest-bdd for BDD

The scaffold already created a `features/` directory **at the repo root** with `README.md` and `example.feature`. Gherkin scenarios are always repo-root-owned, regardless of `$TARGET`.

1. `pytest-bdd` is already installed from step 7.
2. Create `tests/features/test_example.py`:

   ```python
   """Step definitions for the scaffold's example feature."""

   from __future__ import annotations

   from pytest_bdd import given, scenarios, then, when

   scenarios("../../features/example.feature")


   @given("the project has been scaffolded")
   def _scaffolded() -> None: ...


   @when("the first real feature is designed")
   def _designed() -> None: ...


   @then("this file is replaced with a real feature file")
   def _replaced() -> None: ...
   ```

   Adjust the relative path to `features/` for workspace mode, and add the remaining steps to match `example.feature`.

3. Verify `uv run pytest` picks the scenarios up. Because `pytest-bdd` runs inside pytest, the coverage gate and fixtures apply to feature steps automatically — no separate runner invocation in CI.
4. In workspace mode, each package owns a Gherkin tag prefix (e.g. `@ingest`); document the convention in `features/README.md`.

### 14. Update release-please config

**Single-app mode:** edit `.github/release-please-config.json` — set `"release-type": "python"` at the top level.

**Workspace mode:** ADD a `packages.<TARGET>` entry with `"release-type": "python"` (do NOT overwrite any existing `release-type`), and add `"<TARGET>": "0.0.0"` to `.github/.release-please-manifest.json`.

### 15. Summarize

Print: `$TARGET`, `$DATA`, what got installed, what configs were written, and what the user should do next (typically: write the first real test, then implement). If you added a monitoring layer or an orchestrator, name the choice and where it's recorded.

## What NOT to do

- Do not use `pip`, `poetry`, `pipenv`, `conda`, or `python -m venv` directly. `uv` owns environments, dependencies, and interpreter installs.
- Do not create `requirements.txt`, `setup.py`, `setup.cfg`, `mypy.ini`, `pytest.ini`, or `ruff.toml`. Everything lives in `pyproject.toml`.
- Do not set `select = ["ALL"]` in Ruff — see the standards doc for why.
- Do not relax `mypy` globally to silence an untyped dependency. Use a scoped `[[tool.mypy.overrides]]` block.
- Do not add `pandas` by default in a data project — Polars is the default engine, pandas is a boundary adapter.
- Do not install both `soda-core` and `great-expectations`.
- Do not wire `ydata-profiling` into CI. It is an exploration tool with no pass/fail signal.
- Do not write `unwrap`-equivalent shortcuts in example code: no bare `except`, no `assert` for validation, no `Any`. Follow the standards doc — the examples you write become the pattern every later agent copies.
