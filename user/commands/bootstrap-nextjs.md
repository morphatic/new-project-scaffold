---
description: Bootstrap a Next.js (App Router) project — runs the TypeScript bootstrap first, then adds Next.js on top
---

# /bootstrap-nextjs

Bootstrap a Next.js (App Router) project. **This command composes on top of TypeScript** — it runs the TypeScript bootstrap work first, then layers Next.js-specific setup.

## Ground rules

**Always check current stable versions at runtime.** Do not trust numbers from training data:

- Node LTS: check [nodejs.org](https://nodejs.org/).
- `next`, `react`, `react-dom`: `pnpm view next version`, `pnpm view react version`. Use matching peer versions.
- `eslint-config-next`: `pnpm view eslint-config-next version`.
- Always use the **latest stable Next major** unless the user explicitly pins an older one.

## Step 0 — Determine target directory

Decide where this bootstrap writes. Resolve `$TARGET` (a path relative to the repo root) **before any write**.

Decision inputs, in order:

1. **Explicit positional arg.** If the user invoked `/bootstrap-nextjs <path>`, use that path.
2. **Workspace markers at repo root.** Any of these means the root is claimed by a workspace and you MUST target a subdirectory:
   - `pnpm-workspace.yaml` exists.
   - Root `package.json` has a `"workspaces"` field.
   - Root `Cargo.toml` has a `[workspace]` section (hybrid monorepo).
3. **NLSpec signals.** Read `plinth/specs/*.nlspec.md`. Next.js specifically is almost always paired with another component (an API, a worker, a mobile app) when the NLSpec describes anything beyond a marketing site. Look for:
   - §2 Architecture naming Next.js + another runtime (Rust/Go/Python API, Cloudflare Worker, etc.).
   - Explicit mention of `apps/`, `crates/`, `packages/`, monorepo, or workspace.
4. **Existing monorepo layout.** `apps/`, `crates/`, `packages/` directories already present.

Decision:

| Inputs | Action |
|--------|--------|
| Explicit arg given | `TARGET=<arg>`. Skip detection. |
| Workspace markers present, no arg | Propose `apps/web/` (convention for the Next.js frontend in a multi-component repo). Ask the user to confirm before proceeding. |
| NLSpec clearly multi-component, no workspace markers yet | **Stop.** Tell the user to run `/bootstrap-monorepo` first. Do not write anything. |
| Ambiguous | Ask with a specific proposal based on NLSpec. |
| Clearly single-component (marketing site / standalone app / fresh repo with single-component NLSpec) | `TARGET=.` — proceed at repo root. Original single-app behavior. |

Workspace-mode flag: treat `$TARGET != "."` as "workspace mode." In workspace mode, some steps below write to repo-root files (release-please, CI jobs, shared configs) rather than `$TARGET`.

## Part A — TypeScript bootstrap (inlined)

Execute every step from `~/.claude/commands/bootstrap-typescript.md` first, **with these overrides**:

- **Pass `$TARGET` through.** Every step that writes to `$TARGET` in the TS bootstrap writes to the same `$TARGET` here.
- **Skip the TS bootstrap's Step 0.** You've already resolved `$TARGET` above.
- **Skip steps 13 (failing test), 14 (cucumber-js BDD), and 15 (release-please `node`)** — the Next-specific versions live in Part B. Next.js uses **`playwright-bdd`** (Gherkin against a real browser) instead of `@cucumber/cucumber`, because the behaviors worth pinning in Gherkin for a UI app are user-visible flows.
- **`tsconfig.json`**: Next.js generates its own on `next dev` first run. Don't pre-write it — let Next write the baseline, then we'll merge in `@tsconfig/strictest` extensions (Part B step 5).
- **Prettier + eslint**: install as described, but the ESLint config uses Next's preset (Part B step 6).
- **Default test runner**: `vitest` (still the right default for Next.js — App Router components can be tested with `@testing-library/react`).

## Part B — Next.js layer

### 1. Load the Next.js standards

Read `~/dev/new-project-scaffold/templates/coding-standards/coding-standards-nextjs.md`. Copy it to `plinth/coding-standards-nextjs.md` (always at repo root, not `$TARGET`). Note that `plinth/coding-standards-typescript.md` (copied by Part A) is its prerequisite — both apply.

### 2. Install Next.js into `$TARGET`

Look up current versions, then (from `$TARGET`):

```bash
pnpm add next@latest react@latest react-dom@latest
pnpm add -D @types/react @types/react-dom eslint-config-next
pnpm add zod server-only
```

### 3. Scaffold the App Router directory under `$TARGET`

Create:

```
$TARGET/
  app/
    layout.tsx           # root layout (required)
    page.tsx             # home
    loading.tsx          # Suspense fallback
    error.tsx            # "use client"
    not-found.tsx
    global-error.tsx
  public/
```

Keep content minimal and typed. Use `next/font` from the start (Geist or Inter).

### 4. Write `$TARGET/next.config.ts`

```ts
import type { NextConfig } from 'next';

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    typedRoutes: true,
  },
};

export default config;
```

### 5. Merge `$TARGET/tsconfig.json`

After `next dev` has run once and Next has generated its tsconfig, merge in:

```json
{
  "extends": [
    "./node_modules/next/tsconfig.json",
    "@tsconfig/strictest/tsconfig.json"
  ],
  "compilerOptions": {
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

**Workspace mode:** if repo root has `tsconfig.base.json`, add it to the `extends` array so shared compiler options apply. Paths like `@tsconfig/strictest/tsconfig.json` resolve from `$TARGET/node_modules`; add `../../node_modules/@tsconfig/strictest/tsconfig.json` only if node_modules is hoisted to root (pnpm hoists by default).

### 6. ESLint — use Next's flat config

Write `$TARGET/eslint.config.js`:

```js
import nextPlugin from 'eslint-config-next';
import tseslint from 'typescript-eslint';
import eslintConfigPrettier from 'eslint-config-prettier';

export default [
  ...nextPlugin.configs['core-web-vitals'],
  ...nextPlugin.configs.typescript,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  eslintConfigPrettier,
];
```

### 7. Environment variables

Create `$TARGET/.env.example` with placeholders. Ensure `.env`, `.env.local`, `.env*.local` are in the repo-root `.gitignore` (the global hook may cover; add eagerly). If the project will need secrets, install `@t3-oss/env-nextjs` in `$TARGET` and set up a `$TARGET/env.ts` module that validates on import.

### 8. Scripts in `$TARGET/package.json`

Split unit tests (fast, every run) from E2E (slower, run explicitly or in CI). `pnpm test` stays fast:

```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint",
  "typecheck": "tsc --noEmit",
  "format": "prettier --write .",
  "format:check": "prettier --check .",
  "test": "vitest run",
  "test:e2e": "playwright test",
  "test:e2e:ui": "playwright test --ui"
}
```

### 9. CI — add a Next.js job

**Single-app mode (`$TARGET == "."`):** replace the TS test block (left by Part A) with the Next.js test block:

```yaml
- uses: pnpm/action-setup@v6
- uses: actions/setup-node@v6
  with:
    node-version: <verified LTS>
    cache: pnpm
- run: pnpm install --frozen-lockfile
- run: pnpm typecheck
- run: pnpm lint
- run: pnpm format:check
- run: pnpm test
- run: pnpm build
- name: Install Playwright browsers
  run: pnpm exec playwright install --with-deps chromium
- run: pnpm test:e2e
```

**Workspace mode (`$TARGET != "."`):** Part A added a generic TS job for this target — replace its body with the Next.js version, keeping the `defaults.run.working-directory: $TARGET` line. Example for `$TARGET = apps/web`:

```yaml
  web:
    name: web
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v6
      - uses: pnpm/action-setup@v6
        with:
          version: 10
      - uses: actions/setup-node@v6
        with:
          node-version: <verified LTS>
          cache: pnpm
          cache-dependency-path: pnpm-lock.yaml  # single root lockfile in pnpm workspace
      - run: pnpm install --frozen-lockfile       # from apps/web; pnpm walks up to workspace root
      - run: pnpm typecheck
      - run: pnpm lint
      - run: pnpm format:check
      - run: pnpm test
      - run: pnpm build
      - name: Install Playwright browsers
        run: pnpm exec playwright install --with-deps chromium
      - run: pnpm test:e2e
```

`pnpm build` (i.e. `next build`) is a critical CI step — it catches prod-only type errors and caching misconfiguration that `tsc` misses. The Playwright install step is required; it downloads the browser binaries (cached between runs by `actions/setup-node` via `pnpm`). Consider scoping to `chromium` only in CI; add `firefox` / `webkit` if the NLSpec requires them.

Ensure this job is in the aggregate `ci` job's `needs:` list.

### 10. Scaffold a minimal failing test

Write one failing component test using `vitest` + `@testing-library/react`. Put it in `$TARGET/app/page.test.tsx` or `$TARGET/src/__tests__/` per the package's layout.

### 11. Wire up playwright-bdd

The scaffold already created `features/` **at the repo root** with `README.md` and `example.feature`. Make `pnpm test:e2e` run those scenarios against a real browser.

**Workspace mode:** the root `features/` is shared. Next.js web-facing BDD scenarios should live under `features/web/` or use a `@web` tag so other packages' scenarios aren't picked up.

1. Install in `$TARGET` (look up current versions first):

   ```bash
   pnpm add -D playwright-bdd @playwright/test
   pnpm exec playwright install --with-deps chromium
   ```

2. Create `$TARGET/playwright.config.ts`:

   ```ts
   import { defineConfig, devices } from '@playwright/test';
   import { defineBddConfig } from 'playwright-bdd';

   // In workspace mode, features live at repo root. The relative path from
   // $TARGET to repo root is typically '../../features' for apps/<name>.
   // In single-app mode, use 'features/**/*.feature' directly.
   const featuresGlob = 'FEATURES_GLOB_HERE'; // e.g., '../../features/web/**/*.feature'
   const stepsGlob = 'STEPS_GLOB_HERE';       // e.g., '../../features/steps/web/**/*.ts'

   const testDir = defineBddConfig({
     features: featuresGlob,
     steps: stepsGlob,
   });

   export default defineConfig({
     testDir,
     fullyParallel: true,
     forbidOnly: !!process.env.CI,
     retries: process.env.CI ? 2 : 0,
     reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
     use: {
       baseURL: 'http://localhost:3000',
       trace: 'on-first-retry',
     },
     projects: [
       { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
     ],
     webServer: {
       command: 'pnpm dev',
       url: 'http://localhost:3000',
       reuseExistingServer: !process.env.CI,
       timeout: 120_000,
     },
   });
   ```

3. Create `features/steps/web/example.steps.ts` (single-app: `features/steps/example.steps.ts`):

   ```ts
   import { createBdd } from 'playwright-bdd';

   const { Given, When, Then } = createBdd();

   Given('the project has been scaffolded', async () => {});
   When('the first real feature is designed', async () => {});
   Then('this file is replaced with a real feature file', async () => {});

   Given('the input {string}', async (_input: string) => {});
   When('the system processes it', async () => {});
   Then('the output is {string}', async (_output: string) => {});
   ```

   Real steps receive Playwright fixtures: `async ({ page }) => { await page.goto('/'); ... }`.

4. Add to the repo-root `.gitignore`:

   ```
   .features-gen/
   playwright-report/
   test-results/
   blob-report/
   ```

   (`.features-gen/` is where `playwright-bdd` compiles `.feature` files to spec files before Playwright runs them.)

5. In workspace mode, update `features/README.md` to document the tag convention (`@web`, `@api`, etc.) so other packages know how to scope their steps.

6. Verify: `cd $TARGET && pnpm test:e2e` runs the example scenarios against the dev server.

### 12. Update release-please config

**Single-app mode:** edit `.github/release-please-config.json` — set `"release-type": "node"` at the top level.

**Workspace mode:** ADD a `packages.<TARGET>` entry with `"release-type": "node"` (do NOT overwrite any existing top-level release-type). Add `"<TARGET>": "0.0.0"` to `.github/.release-please-manifest.json`. See the TS bootstrap step 15 for the concrete config shape.

### 13. Remind the user about caching

Print a reminder: **Next 15+ defaults to uncached fetches.** Every `fetch` needs explicit caching intent (`{ cache: 'force-cache' }` or `{ next: { revalidate, tags } }`). Nothing silently caches.

### 14. Summarize

Print: `$TARGET`, Next.js version installed, Node LTS targeted, file layout created, what to build next.
