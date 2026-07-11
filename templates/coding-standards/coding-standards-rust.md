# Rust coding standards

Binding guidelines for Rust code in this project. Load this file at the start of any Rust work session. When in doubt, defer to the linked sources in that order.

**Primary sources:**

1. [Microsoft Pragmatic Rust Guidelines](https://microsoft.github.io/rust-guidelines/) — opinionated, Must/Should-tiered. Governs anything marked `M-*` below.
2. [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/checklist.html) — the rust-lang team's canonical style. `C-*` checklist IDs.
3. [Azure SDK Rust Guidelines](https://azure.github.io/azure-sdk/rust_introduction.html) — apply only when building a consumer-facing SDK crate.

## Error handling

- **Libraries** (any crate used by more than one caller): define typed errors with `thiserror`. Do not re-export `anyhow` or `Box<dyn Error>` across the public boundary. (M-ERRORS-CANONICAL-STRUCTS.)
- **Applications and app-private crates**: pick one of `anyhow` or `eyre` and use it exclusively. Don't mix.
- Propagate with `?`. Never `unwrap()` / `expect()` in library paths. Permitted in tests, `build.rs`, and `main()` fallible-init only.
- Panics are for programmer-error contract violations. User input / parsing / I/O must return `Result`. Document panics in a `# Panics` section. (C-FAILURE.)

## Unsafe

- Default stance: `#![forbid(unsafe_code)]` at crate root. Remove only with explicit written justification in the commit message.
- Every `unsafe` block has a `// SAFETY: ...` comment proving the invariants.
- Every `unsafe fn` has a `# Safety` doc section enumerating caller obligations.
- Unsafe code passes Miri in tests. (M-UNSAFE, M-UNSAFE-IMPLIES-UB, M-UNSOUND.)

## Naming and API design

- `UpperCamelCase` types/traits/enums; `snake_case` functions/modules/variables; `SCREAMING_SNAKE_CASE` consts/statics. (C-CASE.)
- Conversions: `as_*` cheap borrow-to-borrow; `to_*` expensive borrow-to-owned; `into_*` consuming owned-to-owned. (C-CONV.)
- Accept `&str` over `String`, `&[T]` over `&Vec<T>`, `impl AsRef<Path>` for paths.
- `impl Trait` in argument position for simple cases; generics when the type needs a name; `dyn Trait` for heterogeneous collections.
- Builders for more than three optional fields. (C-BUILDER.) Newtypes for semantic IDs. (C-NEWTYPE.)
- Public types always `Debug`; add `Clone`, `PartialEq`, `Eq`, `Hash`, `Default` when semantically valid. (C-COMMON-TRAITS.) Derive `Serialize`/`Deserialize` behind a `serde` feature.
- `#[must_use]` on anything the caller would be wrong to ignore. (C-MUST-USE.)
- Avoid `get_` prefix on getters except for index-like access. No `I` prefix on traits.

## Documentation

- Every public item has `///` docs. First line is a one-sentence summary ending in a period.
- Public functions document `# Errors`, `# Panics`, `# Safety` where applicable.
- Non-trivial public items include a runnable `# Examples` block that uses `?` (not `unwrap`).
- Crate root has `//!` docs with purpose + a top-level example.
- Library crates enable `#![deny(missing_docs)]`.

## Testing

- Unit tests are co-located: `#[cfg(test)] mod tests { use super::*; ... }` at the bottom of the module they test.
- Integration tests in `tests/` (each file is a separate binary — one scenario per file).
- Doc-tests in examples compile and run.
- Prefer `cargo nextest run` over `cargo test` when available.

## Lints (Cargo.toml `[lints]` table, RFC 3389)

```toml
[lints.rust]
unsafe_code = "forbid"       # remove only if FFI required
missing_docs = "warn"        # "deny" for library crates

[lints.clippy]
all = { level = "warn", priority = -1 }
pedantic = { level = "warn", priority = -1 }
cargo = { level = "warn", priority = -1 }
unwrap_used = "warn"
expect_used = "warn"
panic = "warn"
todo = "warn"
dbg_macro = "warn"
```

CI: `cargo clippy --all-targets --all-features -- -D warnings`.

Do NOT enable `clippy::nursery` or `clippy::restriction` as groups; cherry-pick from them. Per-project overrides go in the same `[lints]` table with a comment explaining why.

## Formatting (`rustfmt.toml`)

```
edition = "2024"
style_edition = "2024"
max_width = 100
```

`style_edition` must be explicit — `rustfmt` defaults to 2015 while `cargo fmt` infers from `Cargo.toml`, and they diverge silently otherwise.

## Blessed dependencies

Reach for these before rolling your own or picking from Google hits:

| Need | Pick |
|------|------|
| Error types (library) | `thiserror` |
| Error types (app) | `anyhow` or `eyre` |
| Async runtime | `tokio` (features `full` for apps; minimal for libs) |
| HTTP client (high-level) | `reqwest` |
| HTTP client (low-level) | `hyper` |
| JSON / serialization | `serde` + `serde_json` |
| Logging / tracing | `tracing` + `tracing-subscriber` (not `log`) |
| CLI parsing | `clap` (derive API) |
| UUIDs | `uuid` |
| Time / dates | `jiff` (preferred) or `time`; avoid `chrono` |
| Snapshot tests | `insta` |
| Property tests | `proptest` |
| Mocks | `mockall` |

## `Cargo.lock`

- Binary / app crates: **commit** `Cargo.lock`.
- Pure library crates: **ignore** `Cargo.lock` (per official cargo guidance).

## Judgment calls this doc has already made

- `anyhow` in apps, `thiserror` in libs (Microsoft's position, not "anyhow everywhere").
- `clippy::pedantic` on broadly (extra signal outweighs friction for AI-authored code).
- `forbid(unsafe_code)` as the default (force explicit removal for FFI).
- edition 2024 baseline.
- `tracing` over `log`.
- `jiff` over `chrono`.
