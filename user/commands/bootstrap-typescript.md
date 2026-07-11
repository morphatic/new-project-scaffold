---
description: Bootstrap a TypeScript stack in the current project — installs tooling, writes configs, copies the TypeScript coding standards into plinth/, adds a TS CI job
---

# /bootstrap-typescript

Bootstrap a TypeScript stack. Run this after the NLSpec has identified TypeScript as the chosen language.

## Ground rules

**Always check current stable versions at runtime.** Do not trust version numbers from training data or from any doc in this repo. Before installing, look up:

- Node LTS: `pnpm node -v` for installed; [nodejs.org](https://nodejs.org/) for current LTS.
- Package versions: `pnpm view <pkg> version`.
- `typescript`, `eslint`, `typescript-eslint`, `prettier`, `@tsconfig/strictest`, `@tsconfig/node-lts` — always latest stable.

## Step 0 — Determine target directory

Decide where this bootstrap writes. Resolve `$TARGET` (a path relative to the repo root) **before any write**. The later steps use `$TARGET` everywhere that would have previously meant "repo root."

Decision inputs, in order:

1. **Explicit positional arg.** If the user invoked `/bootstrap-typescript <path>`, use that path. Skip to the "decision" below.
2. **Workspace markers at repo root.** Any of these means the root is already claimed by a workspace and you MUST target a subdirectory:
   - `pnpm-workspace.yaml` exists.
   - Root `package.json` has a `"workspaces"` field.
   - Root `Cargo.toml` has a `[workspace]` section (the repo is a hybrid monorepo).
3. **NLSpec signals.** Read `plinth/specs/*.nlspec.md` (prefer the top-level spec; if multiple, identify which is the product spec). Look for:
   - §2 Architecture describing more than one deployable (web app + API, frontend + worker, app + library).
   - Stack declarations naming multiple runtimes (e.g., Next.js AND a Rust Worker).
   - Explicit mentions of monorepo / workspace / `apps/` / `crates/` / `packages/`.
4. **Existing monorepo layout.** `apps/`, `crates/`, `packages/` directories already present at repo root.

Decision:

| Inputs | Action |
|--------|--------|
| Explicit arg given | `TARGET=<arg>`. Skip detection. |
| Workspace markers present, no arg | Propose `packages/<name>` or `apps/<name>` informed by the NLSpec. Ask the user to confirm before proceeding. |
| NLSpec clearly multi-component, no workspace markers yet | **Stop.** Tell the user to run `/bootstrap-monorepo` first, which sets up the workspace scaffolding. Do not write anything. |
| Ambiguous | Ask the user with a specific proposal. Do not guess silently. |
| Clearly single-component (fresh repo, single-language NLSpec, no markers, no `apps/`/`crates/`/`packages/`) | `TARGET=.` — proceed at repo root. Original single-app behavior. |

Workspace-mode flag: treat `$TARGET != "."` as "workspace mode." In workspace mode, some steps below write to repo-root files (shared configs, release-please, CI) rather than `$TARGET`.

## Steps

### 1. Load the standards

Read `~/dev/claude_research/new-projects/templates/coding-standards/coding-standards-typescript.md`. Binding style guide for TS in this project.

### 2. Copy the standards into the project

Copy the file to `plinth/coding-standards-typescript.md`. (Always at repo root — the standards are shared regardless of `$TARGET`.)

### 3. Check prerequisites

Run `pnpm -v`, `node -v`. If missing, stop and tell the user to install pnpm via `npm i -g pnpm` or `winget`, and Node via nvm / fnm / winget.

### 4. Initialize

Create `$TARGET` if it doesn't exist. `cd $TARGET` for the commands below.

If there's no `$TARGET/package.json`, run `pnpm init` in `$TARGET`. Set `"type": "module"` for ESM (default for new projects unless NLSpec says CJS).

In workspace mode: give the package a real `"name"` (e.g., `"@<repo>/<target-leaf>"`) so `pnpm add --filter` works later.

### 5. Install dev dependencies

Look up current versions, then install (inside `$TARGET`):

```bash
pnpm add -D typescript @tsconfig/strictest @tsconfig/node-lts \
  eslint @eslint/js typescript-eslint \
  prettier eslint-config-prettier \
  eslint-plugin-import \
  @types/node
```

In workspace mode, run from repo root with `pnpm add -D --filter <target-package-name> ...` OR `cd $TARGET && pnpm add -D ...` — both work.

**Prettier-specific note (workspace mode):** if a root `package.json` already declares `prettier` as a workspace-shared dev-dep (e.g., installed by `/bootstrap-monorepo`), skip it here to avoid version drift.

### 6. Write `$TARGET/tsconfig.json`

```json
{
  "extends": [
    "@tsconfig/strictest/tsconfig.json",
    "@tsconfig/node-lts/tsconfig.json"
  ],
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src",
    "verbatimModuleSyntax": true,
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"]
}
```

Adjust `rootDir` / `include` / `paths` to match the package's actual layout.

**Workspace mode:** if the repo root has a `tsconfig.base.json` (written by `/bootstrap-monorepo`), extend from it instead of (or in addition to) the `@tsconfig/*` packages to keep per-package configs uniform:

```json
{
  "extends": ["../../tsconfig.base.json"],
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

### 7. Write `$TARGET/eslint.config.js` (flat config)

```js
import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';
import eslintConfigPrettier from 'eslint-config-prettier';

export default tseslint.config(
  eslint.configs.recommended,
  tseslint.configs.strictTypeChecked,
  tseslint.configs.stylisticTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      'no-console': 'warn',
    },
  },
  eslintConfigPrettier,
);
```

### 8. Write `.prettierrc.json` at REPO ROOT (never per-package)

```json
{
  "singleQuote": true,
  "semi": true,
  "trailingComma": "all",
  "printWidth": 100
}
```

Skip if `.prettierrc.json` already exists — one style across the repo.

### 9. Add scripts to `$TARGET/package.json`

```json
"scripts": {
  "build": "tsc",
  "typecheck": "tsc --noEmit",
  "lint": "eslint .",
  "lint:fix": "eslint . --fix",
  "format": "prettier --write .",
  "format:check": "prettier --check .",
  "test": "<pick: vitest | node --test>"
}
```

Default to `vitest` unless the NLSpec picks a different runner; look up its current version and add as a dev dep.

### 10. `.gitignore` (repo root)

Ensure present at the repo-root `.gitignore`: `node_modules/`, `dist/`, `.env`, `.env.local`, `*.tsbuildinfo`. The global gitignore hook handles most of these after first run; add eagerly.

In workspace mode, root-level entries (`node_modules/`, `dist/`, `*.tsbuildinfo`) suffice — they apply to every subdirectory.

### 11. Add a TypeScript CI job

Open `.github/workflows/ci.yml`.

**Single-app mode (`$TARGET == "."`):** uncomment the TS block in the existing `test` job. Pin `actions/setup-node` to the verified Node LTS:

```yaml
- uses: pnpm/action-setup@v6
- uses: actions/setup-node@v6
  with:
    node-version: <verified current LTS>
    cache: pnpm
- run: pnpm install --frozen-lockfile
- run: pnpm typecheck
- run: pnpm lint
- run: pnpm format:check
- run: pnpm test
```

**Workspace mode (`$TARGET != "."`):** add a new named job (derive the job name from the target leaf, e.g., `cli` for `packages/cli`). Do NOT modify the generic `test` job; `/bootstrap-monorepo` replaced that with a comment placeholder.

```yaml
  <target-leaf>:
    name: <target-leaf>
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: <TARGET>
    steps:
      - uses: actions/checkout@v6
      - uses: pnpm/action-setup@v6
        with:
          version: 10
      - uses: actions/setup-node@v6
        with:
          node-version: <verified current LTS>
          cache: pnpm
          cache-dependency-path: pnpm-lock.yaml  # single root lockfile in pnpm workspace
      - run: pnpm install --frozen-lockfile      # from $TARGET; pnpm walks up to the workspace root
      - run: pnpm typecheck
      - run: pnpm lint
      - run: pnpm format:check
      - run: pnpm test
```

Then append the new job name to the aggregate `ci` job's `needs:` list. Required-check protection already points at `CI (required check)`, so adding a package = one `needs:` edit.

### 12. Enable dependabot npm updates

Edit `.github/dependabot.yml` — uncomment the `npm` block. In workspace mode, npm ecosystem scans the whole tree and picks up every `package.json`; config unchanged.

### 13. Scaffold a minimal failing test

Write one failing test in the conventional location for the chosen runner (`$TARGET/src/*.test.ts` for vitest by default).

### 14. Wire up @cucumber/cucumber for BDD

The scaffold already created a `features/` directory **at the repo root** with `README.md` and `example.feature`. Gherkin scenarios are always repo-root-owned, regardless of `$TARGET`.

**Single-app mode:** make `pnpm test` execute scenarios alongside unit tests.

**Workspace mode:** the root `features/` is shared across packages (see `plinth/monorepo.md`). Each package registers its own steps with a unique tag prefix (e.g., `@cli`) so runs can filter. This package's step files go in `features/steps/$TARGET/` to keep ownership visible.

1. Install (look up current versions first):

   ```bash
   # inside $TARGET
   pnpm add -D @cucumber/cucumber tsx
   ```

2. Create `$TARGET/cucumber.json`:

   ```json
   {
     "default": {
       "import": ["../../features/steps/<target-leaf>/**/*.ts"],
       "loader": ["tsx/esm"],
       "paths": ["../../features/**/*.feature"],
       "format": ["progress"],
       "publishQuiet": true
     }
   }
   ```

   In single-app mode, adjust paths to remove the `../../` prefix.

3. Create `features/steps/<target-leaf>/example.steps.ts` (single-app: `features/steps/example.steps.ts`):

   ```ts
   import { Given, When, Then } from '@cucumber/cucumber';

   Given('the project has been scaffolded', () => {});
   When('the first real feature is designed', () => {});
   Then('this file is replaced with a real feature file', () => {});

   Given('the input {string}', (_input: string) => {});
   When('the system processes it', () => {});
   Then('the output is {string}', () => {});
   ```

4. Update `$TARGET/package.json` scripts so `pnpm test` runs both suites:

   ```json
   "test:unit": "vitest run",
   "test:bdd": "cucumber-js",
   "test": "pnpm test:unit && pnpm test:bdd"
   ```

5. Verify: `pnpm test:bdd` in `$TARGET` executes the example scenarios.

> **If this is a browser-facing TS project** (standalone React/Vue/Svelte app, not a CLI or library), swap `@cucumber/cucumber` for `playwright-bdd` — behaviors worth pinning in Gherkin for a UI are user-visible flows, not pure domain logic. See `/bootstrap-nextjs` step 11 for the playwright-bdd pattern. `/bootstrap-nextjs` and `/bootstrap-tauri` already make this swap automatically.

### 15. Update release-please config

**Single-app mode:** edit `.github/release-please-config.json` — set `"release-type": "node"` at the top level.

**Workspace mode:** edit `.github/release-please-config.json` to ADD a `packages.<TARGET>` entry (do NOT overwrite any existing `release-type`):

```json
{
  "packages": {
    "<TARGET>": {
      "release-type": "node",
      "changelog-sections": [ /* same as single-app default */ ]
    }
  },
  "separate-pull-requests": true,
  "include-v-in-tag": true,
  "include-component-in-tag": true
}
```

Also add `"<TARGET>": "0.0.0"` to `.github/.release-please-manifest.json`.

### 16. Summarize

Print: `$TARGET`, what was installed, version numbers pinned, what the user does next.

## What NOT to do

- Do not install packages without looking up current versions first.
- Do not disable `strict` or any flag from `@tsconfig/strictest` without an explicit reason recorded in a comment.
- Do not use `any`, default exports (except framework-required), or `enum`. See the standards doc.
- Do not write anything at repo root that should be per-package in workspace mode (or vice versa). If in doubt, check the plan in Step 0 before writing.
