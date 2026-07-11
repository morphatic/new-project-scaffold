---
description: Set up monorepo workspace scaffolding at the repo root (pnpm workspace + Cargo workspace + monorepo release-please + per-package CI) before per-language bootstraps
---

# /bootstrap-monorepo

Set up the workspace scaffolding at the repo root for a multi-package project. Run this **once**, before the per-language bootstraps (`/bootstrap-nextjs`, `/bootstrap-rust`, etc.), after the NLSpec has identified multiple components.

This command does NOT install any language-specific tooling into any package. It prepares the repo-root structure so per-package bootstraps can slot in cleanly.

## Ground rules

**Always check current stable versions at runtime** (pnpm, Rust edition, shared dev deps). Don't trust numbers from training data.

## Step 0 — Preconditions

1. A tiered NLSpec exists at `plinth/specs/*.nlspec.md`. If not, stop and tell the user to run `/spec-quick` first.
2. No workspace markers already at repo root (check: `pnpm-workspace.yaml`, root `package.json` with `"workspaces"`, root `Cargo.toml` with `[workspace]`). If any exist, the repo is already a workspace — stop and tell the user this command is idempotent-ish but assumes a fresh repo; running it over an existing workspace would overwrite shared config. Proceed only on explicit confirmation.
3. No root-level `package.json` or `Cargo.toml` from a previous single-app bootstrap. If present, stop and ask the user whether to migrate (move existing code into a subpackage) or abort.

## Step 1 — Identify components from the NLSpec

Read the top-level NLSpec (the contract file, typically the shorter-named one without `-engine` or module-specific suffixes). Look for §2 Architecture. Identify distinct deployable or publishable components. Each becomes a package.

For each component, decide:

- **`apps/<name>`** if it's a deployable application (web frontend, mobile app, CLI tool, server).
- **`crates/<name>`** if it's a Rust library or a Rust-based deployable (since Cargo workspaces are conventionally under `crates/` in hybrid repos).
- **`packages/<name>`** if it's a TS library shared across apps.

If the NLSpec only describes one component, stop: this repo doesn't need a monorepo. Run the appropriate single-language bootstrap instead.

If any component's layout is unclear, ask the user with a specific proposal.

Summarize the proposed layout to the user and get explicit confirmation before writing anything. Example:

> Proposed layout:
> - `apps/web/` — Next.js frontend (from §2)
> - `crates/api/` — Cloudflare Worker (Rust, WASM)
> - `crates/scoring-engine/` — scoring library (from scoring-engine NLSpec)
>
> `plinth/`, `features/`, `cspell.json`, `.markdownlint.json`, `.github/` stay at root.
>
> Proceed?

## Step 2 — Create the directory skeleton

Create the top-level directories. Add a `.gitkeep` to each so git tracks them empty:

```
apps/.gitkeep
crates/.gitkeep
packages/.gitkeep   # only if the NLSpec needs shared TS packages
```

Do NOT create the per-component directories yet — the per-language bootstraps will create them with `cargo init` / `pnpm init`.

## Step 3 — Write `pnpm-workspace.yaml` at repo root

```yaml
packages:
  - 'apps/*'
  - 'packages/*'
```

Omit `packages/*` if the layout won't include a `packages/` directory.

## Step 4 — Write root `Cargo.toml` with `[workspace]`

```toml
[workspace]
resolver = "2"
members = ["crates/*"]

[workspace.package]
edition = "<latest stable edition, verified>"
rust-version = "<latest stable toolchain, verified>"
license = "UNLICENSED"

[workspace.lints.rust]
unsafe_code = "forbid"
# Add more from plinth/coding-standards-rust.md when it lands.

[workspace.lints.clippy]
pedantic = { level = "warn", priority = -1 }
nursery  = { level = "warn", priority = -1 }
# Do NOT enable clippy::restriction as a group — see the standards doc.

[workspace.dependencies]
# Shared deps the NLSpec calls for across multiple crates. Typical starters:
# serde        = { version = "<verified>", features = ["derive"] }
# tracing      = "<verified>"
# thiserror    = "<verified>"
# tokio        = { version = "<verified>", features = ["macros", "rt-multi-thread"] }
```

Look up Rust edition, toolchain, and shared-dep versions at write time.

Omit `[workspace]` entirely if the NLSpec has zero Rust components. But if Rust is anywhere on the roadmap, write this now — it's cheap and it means the next `/bootstrap-rust` invocation doesn't need to create a workspace retrospectively.

## Step 5 — Write root `package.json` for shared dev tooling

```json
{
  "name": "<repo-name>",
  "private": true,
  "type": "module",
  "packageManager": "pnpm@<verified>",
  "devDependencies": {
    "prettier": "<verified>",
    "cspell": "<verified>",
    "markdownlint-cli": "<verified>"
  },
  "scripts": {
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "lint:md": "markdownlint \"**/*.md\" --ignore node_modules --ignore target --ignore dist",
    "lint:spell": "cspell --no-progress --no-summary \"**/*\" --exclude node_modules --exclude target --exclude dist",
    "lint": "pnpm lint:md && pnpm lint:spell"
  }
}
```

Look up current versions of prettier, cspell, markdownlint-cli. Set `packageManager` to the pnpm version the user has installed (run `pnpm -v`).

Then run `pnpm install` at the root so the lockfile is created and shared dev deps are available.

## Step 6 — Shared configs at root

These should already exist (from the scaffold): `cspell.json`, `.markdownlint.json`, `.gitignore`. Leave them.

**Write `.prettierrc.json`** at root if it doesn't exist:

```json
{
  "singleQuote": true,
  "semi": true,
  "trailingComma": "all",
  "printWidth": 100
}
```

**Write `tsconfig.base.json`** at root (per-package `tsconfig.json` will extend this):

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "useUnknownInCatchVariables": true,
    "verbatimModuleSyntax": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "isolatedModules": true
  }
}
```

Leave `compilerOptions.lib` / `jsx` / `paths` for per-package configs.

## Step 7 — Workspace `rustfmt.toml` at root (only if Rust is on the roadmap)

```toml
edition = "<match workspace.package.edition>"
max_width = 100
group_imports = "StdExternalCrate"
imports_granularity = "Crate"
```

Per-crate `rustfmt.toml` files become unnecessary when this exists.

## Step 8 — Rewrite `.github/release-please-config.json` in monorepo mode

Replace the existing content with:

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "packages": {},
  "separate-pull-requests": true,
  "include-v-in-tag": true,
  "include-component-in-tag": true,
  "pull-request-title-pattern": "chore(${component}): release ${version}"
}
```

Per-package bootstraps (`/bootstrap-nextjs`, `/bootstrap-rust`, etc.) will populate `packages.<dir>` with per-package `release-type` and changelog config.

Clear `.github/.release-please-manifest.json` to `{}`.

## Step 9 — Rewrite `.github/workflows/ci.yml` for monorepo mode

Replace the existing file with this structure. The `lint` job stays as-is (repo-wide cspell + markdownlint). Replace the single `test` job with a comment placeholder. The aggregate `ci` job starts with `needs: [lint]` and grows as per-package bootstraps add jobs.

```yaml
name: CI

# All node-based actions pinned to major versions that run on Node 22+ runtime.
# Per-package test jobs are added by /bootstrap-<lang> commands and must be
# appended to the `needs:` list in the aggregate `ci` job below.

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main, develop]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: pnpm/action-setup@v6
        with:
          version: 10
      - uses: actions/setup-node@v6
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint:spell
        if: hashFiles('cspell.json') != ''
      - run: pnpm lint:md
        if: hashFiles('.markdownlint.json') != ''

  # --- Per-package jobs go here. Examples added by the bootstrap commands:
  #
  #   web:           # by /bootstrap-nextjs in apps/web
  #     defaults: { run: { working-directory: apps/web } }
  #     steps: ...
  #
  #   api:           # by /bootstrap-rust in crates/api
  #     steps: [ cargo test -p api, ... ]
  #
  #   scoring-engine: # by /bootstrap-rust in crates/scoring-engine
  #     steps: [ cargo test -p scoring-engine, ... ]

  ci:
    # Aggregate gate. Configure branch protection to require THIS check only —
    # individual jobs can be renamed or added without updating protection rules.
    name: CI (required check)
    runs-on: ubuntu-latest
    needs: [lint]   # bootstraps APPEND their job names here
    if: ${{ always() }}
    steps:
      - name: Verify all required jobs passed
        run: |
          # The `needs` context is a JSON object of {job: {result, outputs}}.
          # Fail if any needed job didn't succeed.
          echo '${{ toJson(needs) }}' | jq -e 'to_entries | all(.value.result == "success")' \
            || (echo "One or more required jobs failed:" && echo '${{ toJson(needs) }}' | jq 'to_entries | map({job: .key, result: .value.result})' && exit 1)
          echo "All required checks passed."
```

Note: `pnpm install --frozen-lockfile` at the root requires the root `pnpm-lock.yaml` to exist — Step 5 ran `pnpm install` so it does.

## Step 10 — Write `plinth/monorepo.md`

Document the layout decision so future agents orient without reconstructing it:

```markdown
# Monorepo layout

This repo is a pnpm workspace (TS packages) + Cargo workspace (Rust crates) + shared repo-root tooling.

## Layout

- `apps/<name>/` — deployable applications (e.g., `apps/web` for the Next.js frontend).
- `crates/<name>/` — Rust crates, both library and binary (e.g., `crates/api` for the Cloudflare Worker).
- `packages/<name>/` — TS libraries shared across apps (create on demand).
- `plinth/` — agent-facing context: specs, research, coding standards, this document.
- `features/` — Gherkin scenarios, shared across packages. Each package registers step definitions under `features/steps/<package-leaf>/` and tags scenarios (`@web`, `@api`, etc.) so each package's test runner can filter.
- `.github/` — CI workflows, release-please config, branch-protection setup script.
- Root-level shared config: `cspell.json`, `.markdownlint.json`, `.prettierrc.json`, `tsconfig.base.json`, `rustfmt.toml`, `.gitignore`.

## Workspace tooling

- pnpm workspace declared in `pnpm-workspace.yaml`.
- Cargo workspace declared in root `Cargo.toml` with `members = ["crates/*"]` and `[workspace.package]` / `[workspace.dependencies]` / `[workspace.lints.*]` for shared config.
- Dev tooling (prettier, cspell, markdownlint-cli) lives in the root `package.json` so every package gets the same version.

## Release-please

Release-please runs in monorepo mode with per-package versioning. Each package is registered under `packages.<dir>` in `.github/release-please-config.json` with its own `release-type` (`node` for TS/Next, `rust` for Rust). PRs are separated per package (`separate-pull-requests: true`). Component tags take the form `<package>-v<version>`.

## CI

Each package contributes one job to `.github/workflows/ci.yml`. The aggregate `CI (required check)` job's `needs:` list includes every package job. Adding a new package = adding a job + one line to `needs`.
```

## Step 11 — Summarize

Print:

- The directory skeleton created.
- The shared configs written.
- The recommended next steps:
  - Run `/bootstrap-nextjs` — it will propose `apps/web/` based on the NLSpec.
  - Run `/bootstrap-rust` once per crate — it will propose `crates/<name>/` based on the NLSpec; you may need to run it more than once (e.g., once for `crates/api`, once for `crates/scoring-engine`).
- The manual follow-up: after each per-language bootstrap, verify the new job name appears in the `ci` aggregate job's `needs:` list in `.github/workflows/ci.yml`.

## What NOT to do

- Do not run `cargo init` or `pnpm init` anywhere — that's the per-language bootstraps' job.
- Do not write any language-specific config (`tsconfig.json`, per-package `Cargo.toml`, `next.config.ts`) — only shared/workspace-level config.
- Do not overwrite `cspell.json`, `.markdownlint.json`, `.gitignore`, or anything already at repo root unless the user explicitly confirmed in Step 0.
- Do not create per-component directories (`apps/web/`, `crates/api/`) — leave that to the per-language bootstraps so their post-init state is known-good.
