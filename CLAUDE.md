# new-project-scaffold

Morgan's infrastructure for starting new projects: the `new-project` scaffold script, the templates it copies, the user-level Claude Code hooks and slash commands that support the workflow, and an installer that syncs the user-level pieces into `~/.claude/`.

This is a meta-repo: most files here are **templates consumed by other projects**, not code that runs in this repo. When editing, always be clear which layer you are touching:

- Repo root (`.gitignore`, `cspell.json`, `.github/`, `lefthook.yml`, …) — this repo's own config.
- `templates/` — what `new-project` copies into freshly scaffolded projects.
- `user/` — versioned sources for `~/.claude/hooks/` and `~/.claude/commands/`. Editing a file here does nothing until `install.sh` syncs it. Conversely, never hand-edit the live copies in `~/.claude/` — edit here and re-run `bash install.sh`.

## Working in this project

- **`plinth/`** holds agent-facing context: the original design checklist (`plinth/planning/new-project-checklist.md`) and rationale research. Load from here for background on why the scaffold works the way it does.
- `README.md` is the user-facing documentation for the whole system. Keep it in sync with any behavioral change to the script, templates, hooks, or commands.
- Template changes only affect **future** scaffolded projects. If a change should also land in existing projects (e.g. heliotrek), say so explicitly in the PR description — it's a manual port.

## Git workflow

Branching model: trunk-based (`main` only).

- **Never commit or push directly to `main`.** lefthook hooks block both. Use `feat/<slug>`, `fix/<slug>`, `chore/`, `docs/`, etc., and open a PR with `gh pr create --base main --fill`.
- **Conventional Commits**, enforced by the commit-msg hook. See `.gitmessage`.
- **Wait for CI to pass before merging.** `gh pr checks --watch <num>`. Never use `--admin` to bypass.
- After the repo has a GitHub remote, `bash .github/setup-github.sh --trunk-only` applies branch protection and squash-only merges.

## Testing discipline

There is no test suite here (bash script + markdown/YAML templates). The equivalent discipline:

- After changing the `new-project` script or templates, **smoke-test a real scaffold run** in a temp directory (`mkdir /tmp/scaffold-test && cd /tmp/scaffold-test && ~/dev/new-project-scaffold/new-project --desc test --without-staging`) and inspect the output before declaring done.
- After changing anything in `user/hooks/`, re-run the relevant harness: `python3 tools/benchmark_hook.py` for compound-approver (needs the corpus — see note inside the file), `python3 tools/check_tdd_guard.py` for tdd-guard.
- Workflow YAML changes should be validated with `gh workflow view` after push, or at minimum a YAML parse.
