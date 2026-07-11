---
description: Bootstrap a Tauri v2 project — runs the Rust and TypeScript bootstraps first, then adds Tauri on top
---

# /bootstrap-tauri

Bootstrap a Tauri v2 project (desktop + optional mobile). **This command composes on top of both Rust and TypeScript** — it runs those bootstraps first, then layers Tauri-specific setup.

## Ground rules

**Always check current stable versions at runtime.** Do not trust numbers from training data:

- Tauri: `pnpm view @tauri-apps/cli version`, `cargo search tauri`. The Cargo `tauri` + `tauri-build` versions and the npm `@tauri-apps/cli` + `@tauri-apps/api` versions **must share a minor**. Confirm this before installing.
- Node LTS, Rust toolchain: as per the Rust and TypeScript bootstraps.
- Frontend framework (React / Svelte / Vue / vanilla TS): per the NLSpec. Default to `react-ts` if unspecified.

## Step 0 — Confirm single-app, not monorepo

Tauri apps are inherently single-deployable desktop (and optionally mobile) apps. The Tauri scaffolding tool (`create-tauri-app`) writes a rigid root-level structure (`src-tauri/`, `package.json`, `vite.config.ts`, `index.html`, etc.) that assumes it owns the project root.

**Check before proceeding:**

1. **Workspace markers at repo root.** If any of these exist, **stop**:
   - `pnpm-workspace.yaml`
   - Root `package.json` with a `"workspaces"` field
   - Root `Cargo.toml` with a `[workspace]` section

2. **If workspace markers are present**, tell the user:
   > "This repo is a monorepo workspace, and Tauri's scaffolding assumes root ownership. If you want a Tauri desktop app alongside other components (e.g., an API server), bootstrap them separately: run `/bootstrap-tauri` inside a dedicated subdirectory like `apps/desktop/` (by `cd apps/desktop && <this command>`), and use `/bootstrap-rust crates/<name>` for server-side Rust crates. Then wire each into the workspace's `pnpm-workspace.yaml` and root `Cargo.toml` manually."
   > "Do you want to continue at the repo root anyway (NOT recommended), or stop?"
   Do not proceed without explicit user confirmation.

3. **If no workspace markers**, proceed at the repo root. This is the expected path for a Tauri app.

The rest of this command assumes root-level scaffolding. An explicit positional arg (`/bootstrap-tauri <path>`) is not supported — run this command from inside the target directory instead.

## Part A — Rust bootstrap (inlined, with Tauri overrides)

Execute every step from `~/.claude/commands/bootstrap-rust.md` first, **with these overrides**:

- **Do NOT run `cargo init` at the project root.** Tauri scaffolds its own Rust crate under `src-tauri/`. Skip Rust steps 4-5 for the root; apply them inside `src-tauri/` after step B-1 below.
- **`Cargo.lock`**: always commit (Tauri apps are binary crates).
- **Do NOT uncomment a Rust-only CI block.** Tauri has its own CI pattern (Part D).
- **Failing test**: skip for now; add after Tauri scaffold exists.
- **Skip Rust step 11 (cucumber-rs).** For Tauri apps, the `features/` directory at project root is owned by the JS cucumber runner (Part B step 14). Rust-side BDD inside `src-tauri/tests/` is a valid future addition but out of scope for this bootstrap.

## Part B — TypeScript bootstrap (inlined, with Tauri overrides)

Execute every step from `~/.claude/commands/bootstrap-typescript.md`, **with these overrides**:

- **Do NOT pre-init `package.json`.** `create-tauri-app` handles frontend scaffolding in step C-2.
- **Skip step 14 (cucumber-js BDD).** Tauri uses **`playwright-bdd`** against the webview frontend (with Tauri IPC mocked) — Part C step 11 handles this. Plain `@cucumber/cucumber` is the wrong fit because the behaviors worth pinning in Gherkin are user-visible flows.
- **Ordering:** TS steps 5 (install deps) and 9 (scripts) must run **after** Part C step 2 (`create-tauri-app`), because `package.json` doesn't exist until then. Their content is unchanged.
- **Test runner**: `vitest` for frontend unit tests; `playwright-bdd` for Gherkin scenarios in `features/`.
- **CI block**: skip; Tauri has its own (Part D).

## Part C — Tauri scaffold

### 1. Load the Tauri standards

Read `~/dev/claude_research/new-projects/templates/coding-standards/coding-standards-tauri.md`. Copy it to `plinth/coding-standards-tauri.md`. The Rust and TypeScript standards docs (already in `plinth/` from Parts A and B) also apply.

### 2. Scaffold the app

Run:

```bash
pnpm create tauri-app@latest . --manager pnpm --template <react-ts|svelte-ts|vue-ts|vanilla-ts>
```

Pass `.` to scaffold into the current directory. If the directory is not empty, `create-tauri-app` will error — in that case scaffold to a temp dir and merge, or explicitly confirm with the user first.

Pick the template per the NLSpec. React-TS is the default.

### 3. Verify version alignment

After scaffolding, check that `@tauri-apps/cli`, `@tauri-apps/api`, Cargo `tauri`, and Cargo `tauri-build` all share a minor version. If they don't (happens when `create-tauri-app` is newer than the Cargo crates.io state), align them manually.

### 4. Add Tauri prerequisites per platform

Ensure the user has the OS-specific prerequisites per [tauri.app/start/prerequisites](https://v2.tauri.app/start/prerequisites/):

- macOS: Xcode Command Line Tools
- Windows: Microsoft C++ Build Tools + WebView2 (pre-installed on Windows 11)
- Linux: webkit2gtk-4.1-dev, libappindicator3-dev, librsvg2-dev, etc.

If prerequisites are missing, stop and tell the user to install them.

### 5. Write the capabilities starter

`src-tauri/capabilities/default.json`:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Default permissions for main window",
  "windows": ["main"],
  "permissions": ["core:default"]
}
```

If the NLSpec indicates mobile support, also write `src-tauri/capabilities/mobile.json`:

```json
{
  "$schema": "../gen/schemas/mobile-schema.json",
  "identifier": "mobile",
  "description": "Mobile-only permissions",
  "windows": ["main"],
  "platforms": ["android", "iOS"],
  "permissions": []
}
```

### 6. `tauri.conf.json` tightening

Starting from the default generated by `create-tauri-app`:

- Set `app.security.csp` to a restrictive starter: `"default-src 'self'; img-src 'self' asset: https://asset.localhost; style-src 'self' 'unsafe-inline'"`.
- **Leave `plugins.updater` out entirely** — add only after code-signing keys are set up.
- Confirm `identifier` is valid reverse-DNS (required for Android package name).
- `bundle.targets`: `"all"` or the specific formats the NLSpec calls for.

### 7. Structure the entry point for mobile-readiness

Even if mobile isn't in the initial scope, write `src-tauri/src/main.rs` as a two-liner calling `lib::run()`:

```rust
// main.rs
fn main() {
    app_lib::run();
}
```

```rust
// lib.rs
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::new().build())
        .setup(|app| {
            // ...
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

Reason: code in `main.rs` is not compiled for mobile targets. Getting this right from day one avoids a painful refactor later.

### 8. Add blessed plugins per NLSpec

For each capability the NLSpec requires, add the Rust + JS plugin pair. Examples:

```bash
# File access
cargo add tauri-plugin-fs
pnpm add @tauri-apps/plugin-fs

# Dialog
cargo add tauri-plugin-dialog
pnpm add @tauri-apps/plugin-dialog

# HTTP (bypasses CSP, avoids CORS)
cargo add tauri-plugin-http
pnpm add @tauri-apps/plugin-http

# Logging (wire to tracing)
cargo add tauri-plugin-log
pnpm add @tauri-apps/plugin-log
```

Then register each in `lib.rs` via `.plugin(...)` and add permissions to `capabilities/default.json` (scoped — never wildcards for `fs`/`shell`).

### 9. `.gitignore` additions

Ensure present:

```
src-tauri/target/
src-tauri/gen/
src-tauri/WixTools/
src-tauri/.cargo/
*.key
*.keystore
```

### 10. Scripts in `package.json`

```json
"scripts": {
  "tauri": "tauri",
  "dev": "tauri dev",
  "build": "tauri build",
  "android:dev": "tauri android dev",
  "android:build": "tauri android build",
  "typecheck": "tsc --noEmit",
  "lint": "eslint .",
  "test": "vitest run",
  "test:e2e": "playwright test",
  "test:e2e:ui": "playwright test --ui"
}
```

Only include `android:*` scripts if mobile is in the NLSpec's scope. `test:e2e` is wired up in step 11 below.

### 11. Wire up playwright-bdd (frontend-only)

The `features/` directory is at the project root and is owned by `playwright-bdd`, which drives the frontend in a real browser with Tauri IPC **mocked**. Full desktop E2E (real Tauri window) is a separate, heavier concern — see the note at the end of this step.

1. Install:

   ```bash
   pnpm add -D playwright-bdd @playwright/test
   pnpm exec playwright install --with-deps chromium
   ```

2. Determine the frontend dev-server port. `create-tauri-app` sets this in the frontend template's Vite config — usually `1420`. Confirm by reading `vite.config.ts`. Use that port as the Playwright `baseURL`.

3. Create `playwright.config.ts` at the project root:

   ```ts
   import { defineConfig, devices } from '@playwright/test';
   import { defineBddConfig } from 'playwright-bdd';

   const testDir = defineBddConfig({
     features: 'features/**/*.feature',
     steps: 'features/steps/**/*.ts',
   });

   const DEV_PORT = 1420; // verify against vite.config.ts

   export default defineConfig({
     testDir,
     fullyParallel: true,
     forbidOnly: !!process.env.CI,
     retries: process.env.CI ? 2 : 0,
     reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
     use: {
       baseURL: `http://localhost:${DEV_PORT}`,
       trace: 'on-first-retry',
     },
     projects: [
       { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
     ],
     webServer: {
       // Run only the frontend dev server — NOT `tauri dev` — so Playwright
       // drives a plain browser window with IPC mocked.
       command: 'pnpm exec vite',
       url: `http://localhost:${DEV_PORT}`,
       reuseExistingServer: !process.env.CI,
       timeout: 120_000,
     },
   });
   ```

4. Create `features/support/tauri-mocks.ts` to stub the Tauri IPC surface:

   ```ts
   import { mockIPC, clearMocks } from '@tauri-apps/api/mocks';

   export function installTauriMocks() {
     mockIPC((cmd, args) => {
       // Default: every invoke returns null. Override per-step as needed.
       return null;
     });
   }

   export function resetTauriMocks() {
     clearMocks();
   }
   ```

5. Create `features/steps/example.steps.ts`:

   ```ts
   import { createBdd } from 'playwright-bdd';
   import { installTauriMocks } from '../support/tauri-mocks';

   const { Given, When, Then, Before } = createBdd();

   Before(async ({ page }) => {
     await page.addInitScript(installTauriMocks.toString() + '; installTauriMocks();');
   });

   Given('the project has been scaffolded', async () => {});
   When('the first real feature is designed', async () => {});
   Then('this file is replaced with a real feature file', async () => {});

   Given('the input {string}', async (_input: string) => {});
   When('the system processes it', async () => {});
   Then('the output is {string}', async (_output: string) => {});
   ```

   Per-scenario IPC overrides use `mockIPC` inside the step body — scope overrides tightly and call `clearMocks()` in an `After` hook.

6. Add to `.gitignore`:

   ```
   .features-gen/
   playwright-report/
   test-results/
   blob-report/
   ```

**Future: real-desktop E2E.** Driving a live Tauri window (native menus, tray, OS dialogs) requires `tauri-driver` + WebdriverIO; Playwright can't attach to a Tauri webview. If the NLSpec calls for that level of coverage, add it as a separate suite — don't try to retrofit it into `playwright-bdd`.

## Part D — CI

Tauri desktop CI is a platform matrix. Replace the default CI test block with:

```yaml
- uses: pnpm/action-setup@v4
- uses: actions/setup-node@v5
  with:
    node-version: <verified LTS>
    cache: pnpm
- uses: dtolnay/rust-toolchain@stable
- uses: Swatinem/rust-cache@v2
  with:
    workspaces: './src-tauri -> target'
- name: install Linux deps
  if: matrix.platform == 'ubuntu-latest'
  run: |
    sudo apt-get update
    sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf
- run: pnpm install --frozen-lockfile
- run: pnpm typecheck
- run: pnpm lint
- run: pnpm test
- name: Install Playwright browsers
  if: matrix.platform == 'ubuntu-latest'
  run: pnpm exec playwright install --with-deps chromium
- name: Run frontend E2E (BDD)
  if: matrix.platform == 'ubuntu-latest'
  run: pnpm test:e2e
- run: pnpm tauri build
```

The frontend E2E suite runs on Linux only — it drives a plain Chromium against the dev server with IPC mocked, so there's no platform-specific behavior being tested. `tauri build` still runs on all three platforms.

Wrap in a matrix: `platform: [macos-latest, ubuntu-latest, windows-latest]`.

**Android CI is a separate concern.** It requires JDK 17 (not 21), Android SDK + NDK, and all four Android Rust targets. Leave a commented stub with a TODO; don't wire it up until the user explicitly needs mobile CI.

## Part E — Release-please

Edit `.github/release-please-config.json` — set `"release-type": "node"` (Tauri apps version via `package.json`; the Cargo version in `src-tauri/Cargo.toml` can be kept in sync by a release-please extra file or a small sync step).

## Part F — Summarize

Print:

- Tauri version and matched Cargo/npm version alignment
- Platforms scaffolded (desktop always; mobile if requested)
- Plugins installed
- The top-3 gotchas to watch for (from `coding-standards-tauri.md`): forgetting capabilities, `anyhow` across the boundary, listener leaks

## What NOT to do

- Do not put business logic in `main.rs`. It won't compile for mobile.
- Do not use wildcard `fs` or `shell` scopes in capabilities.
- Do not wire up the updater in the first commit. Do it after signing keys are proven in CI.
- Do not return `anyhow::Error` from `#[tauri::command]`. It won't serialize.
- Do not use `tauri-plugin-localhost` in production.
