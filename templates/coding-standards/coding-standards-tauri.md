# Tauri coding standards

Binding guidelines for Tauri v2 code. Composes on top of [coding-standards-rust.md](./coding-standards-rust.md) and [coding-standards-typescript.md](./coding-standards-typescript.md) — this doc only owns the IPC boundary and Tauri-specific concerns.

**Primary sources:**

1. [Tauri v2 docs](https://v2.tauri.app/) — authoritative. Especially:
   - [Capabilities](https://v2.tauri.app/security/capabilities/), [Permissions](https://v2.tauri.app/security/permissions/), [Capability reference](https://v2.tauri.app/reference/acl/capability/)
   - [Calling Rust from the frontend](https://v2.tauri.app/develop/calling-rust/), [Calling the frontend from Rust](https://v2.tauri.app/develop/calling-frontend/)
   - [State management](https://v2.tauri.app/develop/state-management/), [IPC concept](https://v2.tauri.app/concept/inter-process-communication/), [Isolation pattern](https://v2.tauri.app/concept/inter-process-communication/isolation/)
   - [CSP](https://v2.tauri.app/security/csp/), [tauri.conf.json reference](https://v2.tauri.app/reference/config/)
2. [plugins-workspace](https://github.com/tauri-apps/plugins-workspace) — source of truth for blessed plugins and their permission names.

## Capabilities + permissions (the ACL)

Tauri 2 is **default-deny**. No command is callable from JS unless a capability grants its permission. Core APIs like `core:default` must still be opted into.

- Capability files live in `src-tauri/capabilities/*.json`. Every file is auto-loaded unless `app.security.capabilities` in `tauri.conf.json` names a subset.
- Permission IDs are `${plugin-name}:${permission-name}` (e.g. `fs:allow-read-text-file`), or bare `${permission-name}` for app-defined commands.
- Scope per window via `windows: ["main", "settings-*"]` (glob matching).
- Scope per platform via `platforms: ["macOS", "windows", "linux", "android", "iOS"]`.
- **Never use wildcard scopes for `fs` / `shell`.** Use typed scopes (`$APPDATA/*`, `$RESOURCE/*`). Deny rules win.

## Command design

- `#[tauri::command]` on `pub fn` / `pub async fn`. Register with `.invoke_handler(tauri::generate_handler![...])`.
- Every argument type must `Deserialize`; every return type must `Serialize`.
- **Error types across the boundary**: do NOT return `anyhow::Error` or `Box<dyn Error>` — neither implements `Serialize`. Options:
  - Quick: `Result<T, String>`.
  - Proper: a `thiserror`-derived enum with a manual `Serialize` impl that produces a tagged string. See [Error handling](https://v2.tauri.app/develop/calling-rust/#error-handling).
  - For rich TS discrimination: `#[serde(tag = "kind", content = "message")]`.
- Async commands run on Tauri's async runtime. Don't block it with `std::thread::sleep` or heavy sync work — use `tauri::async_runtime::spawn_blocking`.
- `AppHandle`, `Window`, `State<'_, T>` arguments are injected — they don't appear in the TS signature.

## State management

- Register with `.manage(MyState::default())`. Access via `state: State<'_, MyState>`. Tauri wraps it in `Arc` for you — **do not wrap again**.
- For sync commands use `std::sync::Mutex<T>` (per Tauri docs, per Tokio's own guidance).
- Use `tokio::sync::Mutex` **only** when you must hold the guard across an `.await`. Otherwise `std::sync::Mutex` and drop the guard before awaiting.
- For hot channels / notifiers, prefer `tokio::sync::{mpsc, broadcast, watch}` stored inside state.

## Events vs commands vs channels

| Use | Pattern |
|-----|---------|
| Request / response, typed, ACL-gated | `#[tauri::command]` |
| Fire-and-forget, multi-consumer, small payloads | `app.emit` / `app.emit_to(label, ...)` + `listen` on JS side |
| Streaming from Rust to JS (progress, logs, token streams) | `tauri::ipc::Channel<T>` passed as a command argument |

**JS listener hygiene:** `listen` returns an `UnlistenFn`. Always call it on component unmount (React `useEffect` cleanup, Svelte `onDestroy`, Vue `onUnmounted`). Forgetting this is the #1 memory-leak bug in Tauri apps.

## IPC boundary hygiene

- Every boundary crossing costs JSON / serde. Batch, don't chatter.
- Binary data: `tauri::ipc::Response` with raw bytes, or `ArrayBuffer` via `Channel`. Don't base64-encode large buffers.
- Avoid crossing giant structs, cyclic graphs, or (on Windows) `PathBuf` with UTF-16 edge cases. Prefer IDs + paginated fetches over "load everything".
- Prefer typed TS via `specta` / `tauri-specta`, or hand-maintain a `bindings.ts` generated from Rust types.

## Security

- **CSP**: set `app.security.csp` in `tauri.conf.json`. Keep restrictive. `style-src 'unsafe-inline'` is sometimes unavoidable for CSS-in-JS — document why. CSP is auto-augmented with hashes for Tauri's runtime scripts.
- **Isolation pattern**: `app.security.pattern: { "use": "isolation", "options": { "dir": "../dist-isolation" } }`. Sandboxed iframe validates every IPC message before it reaches core. Use when the frontend loads third-party content.
- **`asset:` / `convertFileSrc`**: load local files in `<img>` / `<video>` via `convertFileSrc(path)` — never embed `file://`.
- **Never** use `tauri-plugin-localhost` in production.

## Mobile (Android / iOS)

- Business logic lives in `src-tauri/src/lib.rs`, exposed as a `run()` function with `#[cfg_attr(mobile, tauri::mobile_entry_point)]`. `main.rs` is a two-liner that calls `lib::run()`.
- **Code in `main.rs` is not compiled for mobile.** Silent bug — always put logic in `lib.rs`.
- Android `AndroidManifest.xml` permissions (`READ_EXTERNAL_STORAGE`, `INTERNET`, etc.) are separate from Tauri capabilities.
- iOS: `PrivacyInfo.xcprivacy` in `src-tauri/gen/apple/` for `fs` timestamp access.
- Not all plugins work on mobile. Check each plugin page's platform matrix. `shell` (spawn), `global-shortcut`, `tray-icon`, `window-state`, `autostart` are desktop-only.
- `src-tauri/gen/android` and `src-tauri/gen/apple` are **generated** — gitignore them. Regenerate via `tauri android init` / `tauri ios init`.
- Use per-platform capability files (`capabilities/mobile.json` with `"platforms": ["android", "iOS"]`) instead of `cfg` branching.

## Updater

- `tauri-plugin-updater`. Generate keys with `pnpm tauri signer generate -w ~/.tauri/<app>.key` (password-protected).
- Public key → `tauri.conf.json` → `plugins.updater.pubkey`. Safe to commit.
- Private key + password → env at build time: `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`. CI secrets only; never commit the `.key` file.
- Private key loss strands installed users. Don't wire up updater in first commit; enable after CI signing is proven.

## Project layout

```
./                       # frontend (package.json, vite.config, etc.)
./src/                   # frontend source
./src-tauri/
  Cargo.toml             # tauri + tauri-build pinned to same minor
  Cargo.lock             # commit this
  build.rs               # tauri_build::build()
  tauri.conf.json        # main config
  src/main.rs            # two lines: call lib::run()
  src/lib.rs             # #[cfg_attr(mobile, tauri::mobile_entry_point)] run()
  capabilities/          # *.json ACL files
  icons/
  gen/                   # mobile scaffolds — GITIGNORE
  target/                # GITIGNORE
```

**Pin `tauri` and `tauri-build` (Cargo) to the same minor version as `@tauri-apps/cli` (npm).** Mismatches break silently.

## Blessed plugins

Reach for these from `tauri-apps/plugins-workspace` before rolling your own:

- **fs** — scoped filesystem. Use permission scopes, not wildcards.
- **dialog** — native open/save/message.
- **shell** — spawn / `open`. ACL-scope the allowed commands list.
- **http** — fetch from Rust (bypasses CSP, avoids CORS). Prefer over `window.fetch` for third-party APIs.
- **store** — JSON key-value persistence.
- **log** — structured logging with rotation; wire to `tracing`.
- **notification** — OS notifications.
- **updater** — see above.
- **os** — platform info.
- Desktop-only: `clipboard-manager`, `global-shortcut`, `window-state`, `autostart`, `single-instance`.
- Mobile-focused: `deep-link`, `barcode-scanner`, `biometric`, `nfc`, `haptics`.

## Top gotchas

1. **Forgetting the capability.** New commands need an entry in `capabilities/*.json`. Agents routinely "fix" this by loosening CSP or disabling isolation — don't.
2. **App logic in `main.rs`.** Not compiled for mobile. Always put logic in `lib.rs`.
3. **`anyhow` across the boundary.** Won't compile. Define a typed error enum with `thiserror` + manual `Serialize` once; reuse everywhere.
4. **Wildcard `fs` scopes.** `"fs:allow-read-file"` without scope = read-any-file. A malicious page in the webview can exfiltrate SSH keys. Always scope to `$APPDATA/*`, `$RESOURCE/*`, etc.
5. **Listener leaks.** `listen(...)` without calling `UnlistenFn` on unmount. Under HMR or route changes, dozens of handlers fire per event.
6. **Dev/prod path drift.** `devUrl` is Vite; prod is custom protocol. Anything depending on absolute URLs, `file://`, or localhost behaves differently. Use `convertFileSrc` and relative fetches.
7. **Version mismatch.** `@tauri-apps/cli` 2.3 with Cargo `tauri` 2.1 produces confusing runtime errors. Pin and upgrade together.
