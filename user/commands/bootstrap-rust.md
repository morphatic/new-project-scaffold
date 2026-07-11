---
description: Bootstrap a Rust stack in the current project — installs tooling, writes configs, copies the Rust coding standards into plinth/, adds a Rust CI job
---

# /bootstrap-rust

Bootstrap a Rust stack. Run this after the NLSpec has identified Rust as the chosen language (or identified Rust as one of several languages in a monorepo).

## Ground rules

**Always check current stable versions at runtime.** Do not trust version numbers from training data or from any doc in this repo. Before adding any dependency or pinning any toolchain version, look it up:

- Rust toolchain: `rustc --version` for installed; `curl -s https://static.rust-lang.org/dist/channel-rust-stable.toml | grep -E '^\[pkg\.rust\]' -A 2` for latest, or check the [Rust releases page](https://www.rust-lang.org/).
- Edition: use the latest stable edition (check [edition guide](https://doc.rust-lang.org/edition-guide/)).
- Crate versions: `cargo search <crate>` or query crates.io.

## Step 0 — Determine target directory

Decide where this bootstrap writes. Resolve `$TARGET` (a path relative to the repo root) **before any write**. The later steps use `$TARGET` everywhere that would have previously meant "repo root."

Decision inputs, in order:

1. **Explicit positional arg.** If the user invoked `/bootstrap-rust <path>`, use that path. Skip to the "decision" below.
2. **Workspace markers at repo root.** Any of these means the root is already claimed by a workspace and you MUST target a subdirectory:
   - Root `Cargo.toml` has a `[workspace]` section (possibly with `members` listed).
   - `pnpm-workspace.yaml` exists at repo root (the repo is a hybrid TS+Rust monorepo).
   - Root `package.json` has a `"workspaces"` field.
3. **NLSpec signals.** Read `plinth/specs/*.nlspec.md` (prefer the top-level spec). Look for:
   - §2 Architecture describing more than one deployable (web app + API, frontend + worker, app + library).
   - Stack declarations naming multiple runtimes (e.g., a Rust Worker AND Next.js).
   - Explicit mentions of monorepo / workspace / `apps/` / `crates/` / `packages/`.
4. **Existing monorepo layout.** `apps/`, `crates/`, `packages/` directories already present at repo root.

Decision:

| Inputs | Action |
|--------|--------|
| Explicit arg given | `TARGET=<arg>`. Skip detection. |
| Workspace markers present, no arg | Propose `crates/<name>` informed by the NLSpec (e.g., `crates/api`, `crates/<component-name>`). Ask the user to confirm before proceeding. |
| NLSpec clearly multi-component, no workspace markers yet | **Stop.** Tell the user to run `/bootstrap-monorepo` first. Do not write anything. |
| Ambiguous | Ask the user with a specific proposal. Do not guess silently. |
| Clearly single-component | `TARGET=.` — proceed at repo root. Original single-crate behavior. |

Workspace-mode flag: treat `$TARGET != "."` as "workspace mode." In workspace mode, some steps below write to repo-root files (shared configs, release-please, CI, workspace `Cargo.toml`) rather than `$TARGET`.

## Steps

### 1. Load the standards

Read `~/dev/claude_research/new-projects/templates/coding-standards/coding-standards-rust.md`. Binding style guide for Rust in this project — every decision below flows from it.

### 2. Copy the standards into the project

Copy the file to `plinth/coding-standards-rust.md` (always at repo root — the standards are shared regardless of `$TARGET`).

### 3. Check prerequisites

Run `rustc --version`, `cargo --version`, `cargo clippy --version`, `cargo fmt --version`. If any are missing, tell the user how to install via rustup and stop.

### 4. Initialize the crate

Create `$TARGET` if it doesn't exist. `cd $TARGET` for the commands below.

If there's no `$TARGET/Cargo.toml`, run `cargo init --vcs none` in `$TARGET` (git is already initialized by the scaffold). Pass `--lib` or leave as binary based on what the NLSpec says for this component.

**Workspace mode:** after `cargo init`, verify the new crate is a member of the root workspace:

- Open repo-root `Cargo.toml`.
- Ensure `$TARGET` is covered by `[workspace].members` (typically `["crates/*"]` is set by `/bootstrap-monorepo`, which picks up `crates/<leaf>` automatically; verify the new crate is visible via `cargo metadata --format-version=1 --no-deps | jq '.workspace_members'`).
- If not covered, add `$TARGET` explicitly to `members`.

### 5. Write config files

**Single-app mode:** create `$TARGET/Cargo.toml` `[lints]` section and `$TARGET/rustfmt.toml` per the standards doc. Set `edition` and `rust-version` to the latest stable you verified above. Don't copy stale version numbers from the standards doc — those are illustrative.

**Workspace mode:** prefer workspace-level config. If the root `Cargo.toml` already has `[workspace.lints.*]` and the repo root has a workspace `rustfmt.toml` (written by `/bootstrap-monorepo`), the per-crate `Cargo.toml` should just say:

```toml
[package]
name = "<crate-name>"
version = "0.0.0"
edition.workspace = true
rust-version.workspace = true

[lints]
workspace = true
```

No per-crate `rustfmt.toml` — the workspace one applies.

If the root doesn't yet have workspace lints (e.g., `/bootstrap-monorepo` was skipped or is older), fall back to per-crate `[lints]` + `rustfmt.toml` from the standards doc.

### 6. Add blessed dependencies

Add the dependencies called for by the NLSpec for this crate, using the "blessed dependencies" table in the standards doc. Look up current versions at runtime. Prefer `cargo add <crate>` inside `$TARGET` (it picks the latest compatible version automatically).

In workspace mode, dependencies shared across multiple crates should go in `[workspace.dependencies]` at root, and each crate uses `<dep>.workspace = true`. Shared deps are typically: `serde`, `tracing`, `thiserror`, `tokio` (if async across the stack), and anything the NLSpec declares cross-crate.

### 7. Install dev tooling

Suggest the user globally install (user decides): `cargo-nextest`, `cargo-audit`, `cargo-deny`. Do not install without confirmation.

### 8. Update `.gitignore`

Ensure these entries are present at the **repo-root** `.gitignore` (they cover all crates in the workspace):

```
/target
**/*.rs.bk
*.pdb
```

For **binary/app crates** (anything with `fn main`), commit `Cargo.lock` — in workspace mode this is the workspace-root `Cargo.lock`, which covers every crate. For a **pure library-only repo** (no binaries anywhere), add `Cargo.lock` to `.gitignore`. Determine from the NLSpec. **Monorepos with at least one binary crate → always commit the workspace `Cargo.lock`.**

### 9. Add a Rust CI job

Open `.github/workflows/ci.yml`.

**Single-app mode (`$TARGET == "."`):** uncomment and adjust the Rust block in the existing `test` job:

```yaml
- uses: dtolnay/rust-toolchain@stable
  with:
    components: rustfmt, clippy
- uses: Swatinem/rust-cache@v2
- run: cargo fmt --all -- --check
- run: cargo clippy --all-targets --all-features -- -D warnings
- run: cargo test --all-features
- run: cargo build --release
```

**Workspace mode (`$TARGET != "."`):** add a new named job (derive the job name from the target leaf, e.g., `api` for `crates/api`). Do NOT modify the generic `test` job; `/bootstrap-monorepo` replaced that with a placeholder.

```yaml
  <target-leaf>:
    name: <target-leaf>
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: rustfmt, clippy
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: '. -> target'
      - run: cargo fmt -p <crate-name> -- --check
      - run: cargo clippy -p <crate-name> --all-targets --all-features -- -D warnings
      - run: cargo test -p <crate-name> --all-features
      - run: cargo build -p <crate-name> --release
```

Then append `<target-leaf>` to the aggregate `ci` job's `needs:` list.

**WASM crates** (e.g., Cloudflare Worker): add a `cargo build --target wasm32-unknown-unknown -p <crate-name>` step after the regular build so WASM-specific compile errors surface in CI.

### 10. Scaffold a minimal failing test

Per the TDD pattern the tdd-guard hook enforces, write one failing unit test inside `$TARGET/src/` using `#[cfg(test)] mod tests { ... }`. This confirms the test harness works and gives the first iteration a red-to-green target.

### 11. Wire up cucumber-rs for BDD

The scaffold already created a `features/` directory **at the repo root** with `README.md` and `example.feature`. Gherkin scenarios are always repo-root-owned, regardless of `$TARGET`.

**Single-app mode:** Rust cucumber-rs runs from the crate root against `../features/` (or in single-app mode, `features/` is at the project root and the crate root IS the project root).

**Workspace mode:** the root `features/` is shared across packages (see `plinth/monorepo.md`). Each crate registers steps with a unique tag prefix (e.g., `@api`, `@scoring-engine`). Step definitions for this crate go in `$TARGET/tests/cucumber.rs`.

1. Add dev-deps (look up current versions first):

   ```bash
   cd $TARGET
   cargo add --dev cucumber
   cargo add --dev tokio --features macros,rt-multi-thread
   ```

   If the NLSpec indicates a sync-only project and adding `tokio` is undesirable, substitute `futures` and use `futures::executor::block_on` in step 3 instead of `#[tokio::main]`.

2. Append to `$TARGET/Cargo.toml`:

   ```toml
   [[test]]
   name = "cucumber"
   harness = false
   ```

3. Create `$TARGET/tests/cucumber.rs`:

   ```rust
   use cucumber::{given, then, when, World};

   #[derive(Debug, Default, World)]
   pub struct AppWorld;

   #[given("the project has been scaffolded")]
   fn project_scaffolded(_w: &mut AppWorld) {}

   #[when("the first real feature is designed")]
   fn feature_designed(_w: &mut AppWorld) {}

   #[then("this file is replaced with a real feature file")]
   fn file_replaced(_w: &mut AppWorld) {}

   #[given(regex = r#"^the input "(.+)"$"#)]
   fn given_input(_w: &mut AppWorld, _input: String) {}

   #[when("the system processes it")]
   fn system_processes(_w: &mut AppWorld) {}

   #[then(regex = r#"^the output is "(.+)"$"#)]
   fn output_is(_w: &mut AppWorld, _output: String) {}

   #[tokio::main]
   async fn main() {
       // In workspace mode, features live at repo root; adjust the path to match.
       // Single-app mode: "features". Workspace mode: "../../features".
       let features_path = if std::path::Path::new("features").exists() {
           "features"
       } else {
           "../../features"
       };
       AppWorld::cucumber()
           .filter_run(features_path, |_feat, _rule, sc| {
               // In workspace mode, filter by tag to avoid running other crates' steps:
               // sc.tags.iter().any(|t| t == "@<target-leaf>")
               true
           })
           .await;
   }
   ```

4. Verify: `cargo test -p <crate-name> --test cucumber` runs the example scenarios. `cargo test -p <crate-name>` picks it up too.

5. In workspace mode, update `features/README.md` to document the tag-filtering convention so future agents know each crate owns a tag prefix.

### 12. Update release-please config

**Single-app mode:** edit `.github/release-please-config.json` — set `"release-type": "rust"` at the top level.

**Workspace mode:** edit `.github/release-please-config.json` to ADD a `packages.<TARGET>` entry (do NOT overwrite any existing `release-type`):

```json
{
  "packages": {
    "<TARGET>": {
      "release-type": "rust",
      "changelog-sections": [ /* same as single-app default */ ]
    }
  },
  "separate-pull-requests": true,
  "include-v-in-tag": true,
  "include-component-in-tag": true
}
```

Also add `"<TARGET>": "0.0.0"` to `.github/.release-please-manifest.json`.

### 13. Summarize

Print: `$TARGET`, what got installed, what configs were written, what the user should do next (typically: write the first real test, then implement).

## What NOT to do

- Do not run `cargo install` without the user's explicit OK.
- Do not use `unwrap()` / `expect()` in example code you write — follow the standards doc.
- Do not enable `clippy::nursery` or `clippy::restriction` as groups.
- Do not add `anyhow` as a dependency for a library crate (see the standards doc for the lib/app split).
- Do not write anything at repo root that should be per-crate in workspace mode (or vice versa). If in doubt, check the plan in Step 0 before writing.
