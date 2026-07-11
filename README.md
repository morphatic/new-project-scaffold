# new-project-scaffold — scaffold, hooks, and workflow commands

Morgan's infrastructure for starting new projects with sensible defaults and keeping agents on rails while they work.

Three layers:

1. **Scaffold** (`new-project` script + `templates/`) — run once per new project. Creates directory structure, configs, spec templates, and an initial git commit.
2. **User-level assets** (`user/hooks/` + `user/commands/`) — the global Claude Code hooks and slash commands, versioned here and synced into `~/.claude/` by `install.sh`. Edit the sources here, never the live copies.
3. **This repo's own docs** (`plinth/`) — the design checklist and rationale behind the system.

After cloning or editing anything under `user/`, run:

```bash
bash install.sh          # sync user/hooks + user/commands into ~/.claude/
bash install.sh --dry-run
```

`install.sh` does not touch `~/.claude/settings.json` — hook *registration* lives there and changes rarely; see "Global hooks" below for the expected blocks.

---

## Prerequisites

Installed globally on the machine:

| Tool | Why | How |
| ---- | --- | --- |
| Python 3 | All hooks are Python scripts | Already present |
| Git | Scaffold does `git init`; hooks look for `.git` to locate repo root | Already present |
| `pnpm` | Node package manager Morgan uses globally | `winget install pnpm.pnpm` (or equivalent) |
| `cspell` | Lint hook invokes it when a project has `cspell.json` | `pnpm add -g cspell` |
| `markdownlint-cli` | Lint hook invokes `markdownlint` when a project has `.markdownlint.json` | `pnpm add -g markdownlint-cli` |
| `lefthook` | Scaffolded repos use it for pre-commit / commit-msg / pre-push hooks | `pnpm add -g lefthook` |
| `gh` CLI | `setup-github.sh` applies branch protection, merge strategy, and default-branch settings via `gh api` | `winget install GitHub.cli`, then `gh auth login` |
| `prodkit` (optional) | `/spec-interview` slash command reads its framework | `git clone https://github.com/ramybarsoum/prodkit ~/dev/prodkit` |

Verify with: `pnpm list -g` and `gh auth status`.

### Windows-only: `LEFTHOOK_BIN` shim

pnpm installs `lefthook` as a bash shim (no `.exe`), so lefthook's generated git-hook scripts can't locate the binary by the usual resolution order. Add this to `~/.bash_profile`:

```bash
export LEFTHOOK_BIN=/c/Users/Morgan/AppData/Local/pnpm/lefthook
```

Without this, `git commit` / `git push` will fail with "lefthook not found" after `lefthook install`.

---

## Creating a new project

```bash
mkdir my-thing && cd my-thing
new-project                         # uses folder name as slug, prompts for description + branching
new-project --desc "one-liner"      # skip the description prompt
new-project --with-staging          # two-tier (main + develop). Default for apps/sites/services.
new-project --without-staging       # trunk-based (main only). Good for libraries and utilities.
new-project --force                 # allow scaffolding into a non-empty folder
```

What you get:

- `plinth/` — agent-facing context (specs, research, planning). See `plinth/README.md`.
- `plinth/specs/<slug>.nlspec.{index,md,rationale.md}` — empty tiered NLSpec templates.
- `plinth/planning/bootstrap-language.md` — stub checklist to run once a stack is chosen.
- `features/README.md` + `features/example.feature` — Gherkin/BDD scaffold. The `/bootstrap-<lang>` commands wire up the matching runner based on whether the project has a UI: `cucumber-rs` (Rust), `@cucumber/cucumber` (plain TS CLI/lib), `playwright-bdd` (Next.js, Tauri — real browser against the frontend; Tauri mocks IPC). Unit tests run via `pnpm test` / `cargo test`; E2E suites run via `pnpm test:e2e`.
- `.claude/settings.json` — minimal allow-list.
- `.claude/commands/spec-{quick,interview,audit}.md` — project-level slash commands.
- `.editorconfig`, `.gitignore`, `cspell.json`, `.markdownlint.json` — baseline configs.
- `.gitmessage` — Conventional Commits reference (wired up via `commit.template`).
- `lefthook.yml` — runs the three git hooks below.
- `.github/hooks/no-commit-on-protected.sh` — pre-commit, blocks commits on `main`/`master`/`develop`.
- `.github/hooks/conventional-commits.sh` — commit-msg, enforces `<type>[(<scope>)][!]: <desc>`.
- `.github/hooks/no-push-to-protected.sh` — pre-push, blocks pushes from a protected branch.
- `.github/workflows/ci.yml` — compute-budget CI (pattern ported from heliotrek): a `changes` path-filter job gates `test` and `audit` so pushes only run jobs whose inputs could have changed; `lint` always runs; a weekly full-matrix schedule + `workflow_dispatch` keep the filters honest; every job carries `timeout-minutes`; the `CI (required check)` aggregate accepts success-or-skipped via `jq`. Test job has commented per-language templates to uncomment.
- `.github/workflows/audit.yml` — reusable dependency-advisory workflow: called from ci.yml when the dependency graph changes, plus a daily self-schedule so new CVEs surface even when no code is moving. Ecosystem steps activate automatically when a lockfile appears.
- `.github/PULL_REQUEST_TEMPLATE.md` — What / Why / Testing / Spec impact / Checklist.
- `.github/ISSUE_TEMPLATE/` — structured bug / enhancement / docs forms (intent, acceptance criteria, spec anchor, visible-UI flag).
- `.github/dependabot.yml` — monthly, minor+patch grouped into one PR per ecosystem (majors individual); npm/cargo/pip blocks commented and ready to enable.
- `.github/workflows/dependabot-auto-merge.yml` — auto-enables squash-merge on dependabot patch PRs once required checks pass.
- `.github/workflows/release-please.yml` + `release-please-config.json` + `.release-please-manifest.json` — release-please reads the Conventional Commits on `main` and opens/maintains a release PR with version bump + `CHANGELOG.md`. Merging that PR tags the release. Default release-type is `simple` (manages `version.txt` + changelog); switch to `node`/`rust`/`python` in the config when the stack is chosen.
- `.github/setup-github.sh` — one-shot GitHub config: squash-merge only, auto-delete branches, standard labels (`priority:*`, `NOT4AI`), branch protection on `main` (+ `develop` when two-tier), required status check = `CI (required check)`, `enforce_admins: true`.
- `CLAUDE.md` — pointer into `plinth/`, plus git-workflow, PR-workflow (never merge without explicit approval; manual-test steps + wait), external-service (no silent provider swaps; aesthetics is Morgan's call) and hard TDD discipline rules (tests-first; never skip/disable; never edit a test to make it pass; done means the full suite passes).
- Initial git commit on `main`, then a switch to `develop` (if two-tier). Lefthook installed.

Next:

1. `claude` in the folder, then `/spec-quick` (freeform) or `/spec-interview` (structured) to draft the spec.
2. Once ready to push: `gh repo create`, `git push -u origin main` (and `develop` if two-tier), then `bash .github/setup-github.sh` (add `--trunk-only` if you used `--without-staging`).

### Git workflow baked into the scaffold

- **Branching:** two-tier (`main` + `develop`) by default. Feature branches merge into `develop`; `develop` → `main` for release. `--without-staging` switches to trunk-based (`main` only) for libraries.
- **Never commit on `main`/`develop`.** Pre-commit hook blocks this. Use `feat/<slug>`, `fix/<slug>`, `chore/`, `docs/`, `refactor/`, `test/`, `perf/`.
- **Conventional Commits.** Commit-msg hook enforces `<type>[(<scope>)][!]: <description>`. Types: feat, fix, chore, docs, refactor, test, perf, build, ci, style, revert.
- **Never push from a protected branch.** Pre-push hook blocks this locally; GitHub branch protection catches the server-side case.
- **Squash-merge only, auto-delete on merge.** Set by `setup-github.sh`.
- **Wait for CI.** `gh pr checks --watch <num>`. Don't use `--admin` — `enforce_admins: true` on protected branches would reject it anyway.

---

## Global hooks (installed — no per-project action required)

Versioned sources live in `user/hooks/` in this repo; the live copies in `~/.claude/hooks/` are synced by `install.sh` and registered in `~/.claude/settings.json`. They apply to every project you open. To change a hook: edit `user/hooks/`, run `bash install.sh`, and re-run `python3 tools/benchmark_hook.py` for compound-approver changes.

### 1. compound-approver (PreToolUse / Bash)

Auto-approves compound Bash commands (joined by `&&`, `||`, `;`, `|`) when every component is on the safe list. Bails on command substitution, file redirects, heredocs, `sudo`, destructive ops. Covers ~80% of compound commands in Morgan's history.

- Config: `~/.claude/hooks/compound-approver-config.json` — edit the JSON to extend coverage. No restart needed; hook re-reads each invocation.
- Three tiers: `safe_commands` (unconditional), `safe_with_arg_check` (approved only when no denied flags/subcommands), `dangerous_first_tokens` (never approved).
- Debug: `COMPOUND_APPROVER_LOG=1` → `compound-approver.log`.

### 2. gitignore-autoupdate (PostToolUse / Bash)

After each Bash command, scans the git root for well-known build/dep directories and appends missing entries to `.gitignore` under a managed block (`# --- added by gitignore-autoupdate ---`).

- Detects: `node_modules/`, `__pycache__/`, `.venv/`, `venv/`, `target/`, `dist/`, `.next/`, `.nuxt/`, `.svelte-kit/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.turbo/`, `coverage/`, `.nyc_output/`, `.parcel-cache/`.
- Additive only. Idempotent. Silent outside git repos.
- Signature list is hard-coded in `gitignore-autoupdate.py` — edit the `SIGNATURES` dict to extend.
- Debug: `GITIGNORE_AUTOUPDATE_LOG=1` → `gitignore-autoupdate.log`.

### 3. lint-on-write (PostToolUse / Write | Edit)

After Claude writes or edits a file, runs the relevant linters. Surfaces findings back as hook context so the agent sees them. **Never blocks.**

- `markdownlint` runs on `*.md` files — only if the repo has `.markdownlint.json`.
- `cspell` runs on every text file — only if the repo has `cspell.json`.
- To enable in a project: drop the relevant config file at the repo root. (The scaffold already includes both.)
- To disable in a project: delete the config file, or add an ignore pattern inside it.
- Debug: `LINT_ON_WRITE_LOG=1` → `lint-on-write.log`.

### 4. tdd-guard (PreToolUse / Write | Edit)

Blocks edits that introduce test-skip/disable patterns or empty out a test file. Addresses the "agent skips the failing test instead of fixing the source" failure mode.

**Scope (only these paths are checked):**

- `tests/`, `spec/`, `__tests__/`, `features/`
- `test_*.py`, `*_test.py`, `*_test.go`, `*_test.rs`, `*_spec.rb`
- `*.test.{ts,tsx,js,jsx,mjs,cjs}`, `*.spec.{ts,tsx,js,jsx,mjs,cjs}`
- `*.feature`
- Any `.rs` file whose content contains `#[cfg(test)]` or `mod tests` (Rust inline-tests convention)

**Blocks these patterns when *added* by the edit** (each scoped to the languages where it's actually a test-skip idiom):

- JS/TS: `.skip(`, `.only(`, `xit`, `xdescribe`, `fit`, `fdescribe`
- Python: `@pytest.mark.{skip,skipif,xfail}`, `@unittest.skip`, `pytest.skip()`, bare `@skip`/`@skipIf`/`@skipUnless`
- Rust: `#[ignore]` — and ONLY that; `Iterator::skip(...)`/`skip_while(...)` are legitimate std methods and are allowed (false positive found in heliotrek, fixed 2026-07-11)
- Go: `t.Skip`/`t.SkipNow` · JVM: `@Ignore`, `@Disabled` · Ruby: `skip:`/`skip(` · Gherkin: `@skip`/`@ignore`/`@wip` tags

Count-based — preserving a pre-existing skip during an unrelated edit is fine. Regression checks: `python3 tools/check_tdd_guard.py`.

**Escape hatch:** include the literal marker `tdd-guard: allow-skip` as a comment in the added content. The hook allows the edit; the marker stays in the file and is auditable in `git blame`.

```python
# tdd-guard: allow-skip (flaky integration test, tracked in issue #42)
@pytest.mark.skip
def test_foo(): ...
```

To bypass for a whole project (not recommended): remove the `Write|Edit` matcher block from `~/.claude/settings.json`, or edit `tdd-guard.py` to early-exit on certain paths.

Debug: `TDD_GUARD_LOG=1` → `tdd-guard.log`.

---

## Slash commands

Versioned sources live in `user/commands/`; installed at user level (`~/.claude/commands/`) via `install.sh`, so they work in every project:

- **`/spec-interview`** — structured NLSpec interview. Requires prodkit at `~/dev/prodkit/`. Three depth tiers (Quick / Standard / Deep). Produces `<name>.nlspec.{md,rationale.md,index.md,audit.md}`.
- **`/spec-audit`** — standalone completeness audit against any existing NLSpec. Writes `<name>.nlspec.audit.md`. Read-only; doesn't modify the spec.
- **`/bootstrap-rust`** / **`/bootstrap-typescript`** / **`/bootstrap-nextjs`** / **`/bootstrap-tauri`** — language/framework bootstraps. Run after the NLSpec has picked a stack. Framework commands automatically run their language prereqs (e.g. `/bootstrap-nextjs` runs the TypeScript setup first; `/bootstrap-tauri` runs both Rust and TypeScript first). Each command copies the matching `coding-standards-<lang>.md` into `plinth/`, checks current stable versions at runtime, writes config files, uncomments the right CI block, installs blessed tooling, scaffolds a minimal failing test, and wires up the matching BDD runner: `cucumber-rs` (Rust), `@cucumber/cucumber` (plain TS CLI/library), `playwright-bdd` (Next.js, Tauri — browser-level BDD with Tauri IPC mocked). Sources: Microsoft Pragmatic Rust Guidelines + Rust API Guidelines; Google TypeScript Style Guide + `@tsconfig/strictest`; Next.js official docs + Vercel security blog; Tauri v2 docs.

And project-level (only in scaffolded projects, via `.claude/commands/`):

- **`/spec-quick`** — freeform description → draft NLSpec.

To use `/spec-quick` in a non-scaffolded project, copy it from `templates/claude/commands/spec-quick.md` into `.claude/commands/` there, or promote it to user-level by copying to `~/.claude/commands/`.

---

## Adding the tooling to an existing (non-scaffolded) project

The global hooks and user-level slash commands already apply. To opt into the lint hook:

1. Copy `templates/config/cspell.json` to the project root to enable cspell.
2. Copy `templates/config/.markdownlint.json` to the project root to enable markdownlint.
3. (Optional) Copy `templates/claude/settings.json` to `.claude/settings.json` for baseline permissions.

To opt into the git workflow bundle:

1. Copy `templates/lefthook.yml`, `templates/gitmessage` → `.gitmessage`, and `templates/github/` → `.github/` into the project.
2. `chmod +x .github/hooks/*.sh .github/setup-github.sh`.
3. `git config commit.template .gitmessage` and `lefthook install`.
4. After first push: `bash .github/setup-github.sh` (add `--trunk-only` if no `develop` branch).

The gitignore-autoupdate and tdd-guard hooks need no per-project setup — they fire on any git repo.

---

## Troubleshooting

- **A hook isn't firing:** check it's registered in `~/.claude/settings.json` under `hooks.PreToolUse` or `hooks.PostToolUse`. Restart Claude Code after config changes.
- **A hook is firing too aggressively:** enable the log env var (see each hook's section), reproduce, read the log, adjust config or patterns.
- **cspell/markdownlint not running:** confirm `cspell` / `markdownlint` are on PATH (`pnpm list -g`). Confirm the project has `cspell.json` / `.markdownlint.json` at the repo root.
- **tdd-guard blocked a legitimate skip:** add the `tdd-guard: allow-skip` marker in the same edit, with a stated reason.
- **compound-approver isn't approving something simple:** the hook is conservative by design. Add the command to `safe_commands` (unconditional) or `safe_with_arg_check` (gated by flag inspection) in the config JSON.
- **lefthook hooks failing with "command not found" on Windows:** confirm `LEFTHOOK_BIN` is set in `~/.bash_profile` (see Prerequisites). Without it, the bash shim pnpm installs can't be located by the generated hook scripts.
- **`setup-github.sh` fails with 404 / "resource not accessible":** the repo must exist on GitHub and you must be authenticated. `gh repo view` to confirm, then `gh auth status`.
- **Pre-commit hook refuses a legitimate commit on `main`:** for a freshly-scaffolded repo, the first commit is made by the scaffold script *before* `lefthook install` runs, so the initial commit goes through. After that, use feature branches.

---

## Key file locations

```text
~/dev/new-project-scaffold/
  new-project                  # scaffold script (bash)
  install.sh                   # syncs user/ into ~/.claude/
  plinth/                      # this repo's own design docs (checklist + rationale convo)
  templates/                   # what the scaffold copies
    config/                    # .editorconfig, .gitignore, cspell.json, .markdownlint.json
    claude/                    # settings.json + commands/spec-*.md
    plinth/                    # bootstrap-language.md
    features/                  # Gherkin scaffold — README.md + example.feature
    nlspec/                    # tiered NLSpec templates
    coding-standards/          # binding standards docs copied by /bootstrap-<lang> commands
      coding-standards-rust.md
      coding-standards-typescript.md
      coding-standards-nextjs.md
      coding-standards-tauri.md
    lefthook.yml               # pre-commit / commit-msg / pre-push hook config
    gitmessage                 # Conventional Commits template (copied as .gitmessage)
    github/
      workflows/
        ci.yml                     # path-filtered lint + test + audit + aggregate gate
        audit.yml                  # reusable dependency-advisory workflow (daily self-schedule)
        dependabot-auto-merge.yml  # auto-squash-merges patch updates
        release-please.yml         # opens/maintains a release PR from commits
      ISSUE_TEMPLATE/              # structured bug / enhancement / docs forms
      PULL_REQUEST_TEMPLATE.md
      dependabot.yml               # monthly grouped update schedule per ecosystem
      release-please-config.json   # release-please config (release-type, changelog sections)
      .release-please-manifest.json  # tracks current version (starts at 0.0.0)
      setup-github.sh              # one-shot branch protection + labels + merge-strategy setup
      hooks/                       # scripts referenced from lefthook.yml
        no-commit-on-protected.sh
        conventional-commits.sh
        no-push-to-protected.sh
  user/                        # versioned sources for ~/.claude/ (sync via install.sh)
    commands/
      spec-interview.md
      spec-audit.md
      bootstrap-monorepo.md
      bootstrap-rust.md
      bootstrap-typescript.md
      bootstrap-nextjs.md
      bootstrap-tauri.md
    hooks/
      compound-approver.py
      compound-approver-config.json
      gitignore-autoupdate.py
      lint-on-write.py
      tdd-guard.py
  tools/
    benchmark_hook.py          # measures compound-approver approval rate after config changes

~/.claude/
  settings.json                # hooks + permissions REGISTERED here (not managed by install.sh)
  commands/                    # live copies — synced from user/commands/
  hooks/                       # live copies — synced from user/hooks/ (+ *.log debug output)

~/dev/prodkit/                  # optional — required for /spec-interview
~/dev/claude_research/permissions-mastery/
  bash_commands.json           # 10,143 historical commands for benchmarking compound-approver
  interrogating-cc-logs.md     # notes on session-log schema
```

---

## Open / not-yet-done

Items from the new-project checklist and related automation ideas that have not been built:

### Hook / permissions

- **Red-before-green hook** — PostToolUse captures test-runner output, PreToolUse on source Write/Edit requires a recent failing test. v2 of the TDD enforcement story.
- **compound-approver v2 — `$(...)` subshell unwrap** — would lift approval rate +1.4%. Parser-level change.
- **Investigate the 162 `<untokenizable>` commands** in the benchmark log for cheap wins.
- **Adjacency-attack closure on plain-safe first tokens** (e.g. `ls ;rm -rf /` past the shlex-splittable boundary). Would need a real shell parser.

### Scaffold / per-language

- **Additional language bootstraps** — Rust, TypeScript, Next.js, Tauri are built (including BDD runner wiring). Python, Go, SvelteKit, and other stacks still need research + a `/bootstrap-<lang>` command + a `coding-standards-<lang>.md`. New language bootstraps should also wire the matching BDD runner (e.g. `behave` for Python, `godog` for Go, `@cucumber/cucumber` for SvelteKit).
- **`/feature` or `/tdd-feature` slash command** — structured new-feature entry that sequences behavior interview → gherkin → failing test → run-to-fail → implement → run-to-pass via TaskCreate.

### Meta

- **Always-current todo list** accessible without context regeneration — biggest open design question.

---

Last updated: 2026-07-11 (promoted to standalone repo; heliotrek CI/CD + workflow-rule port).
