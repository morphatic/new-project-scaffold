# Next.js coding standards

Binding guidelines for Next.js (App Router) code. Composes on top of [coding-standards-typescript.md](./coding-standards-typescript.md) — the TS rules still apply.

**Primary sources:**

1. [Next.js official docs](https://nextjs.org/docs/app) — especially [Production Checklist](https://nextjs.org/docs/app/guides/production-checklist), [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components), [Route Handlers](https://nextjs.org/docs/app/api-reference/file-conventions/route), [Caching guide](https://nextjs.org/docs/app/guides/caching-without-cache-components).
2. [Vercel — Security in Next.js Server Components / Actions](https://nextjs.org/blog/security-nextjs-server-components-actions).
3. [React — Server Components reference](https://react.dev/reference/rsc/server-components).

> **Version note.** Next.js 15 changed default caching semantics. Anything written for Next ≤14 is misleading on `fetch` defaults. If the project is on an older major, flag it — don't silently apply the old rules.

## Server vs Client Components

- Everything is a Server Component by default.
- Add `"use client"` **only** when the file needs: `useState` / `useReducer` / `useEffect` / other hooks, event handlers (`onClick`, `onChange`), browser-only APIs (`window`, `localStorage`), custom hooks, or React Context.
- Push `"use client"` boundaries **as deep as possible**. Pass Server Components as `children` props into Client Components to keep most of the tree server-rendered.
- Props passed from Server → Client must be serializable. No functions, no class instances, no `Date` (use ISO strings).

## Data fetching

- Fetch in Server Components, as close to the data as possible. Call the DB/ORM directly.
- Never call your own Route Handlers from Server Components — that's a double hop.
- Import `server-only` in any module that references secrets or server-only code; leaks throw at build time.
- Use `React.cache(fn)` to dedupe non-fetch data access within a render.
- Use the `preload(id)` pattern to kick off fetches before awaits.

## Caching (Next 15+ — opt in explicitly)

Next 15+ defaults are **uncached**. Every cache decision must be written intentionally.

- `fetch(url)` defaults to `cache: 'no-store'`. Opt in with:
  - `fetch(url, { cache: 'force-cache' })` — static; or
  - `fetch(url, { next: { revalidate: 3600, tags: ['user'] } })` — time + tag based.
- Route handler GETs default to dynamic — add `export const dynamic = 'force-static'` or per-request `revalidate` for caching.
- For non-fetch caching: `unstable_cache(fn, keys, { tags, revalidate })`.
- Route-segment config: `export const dynamic | revalidate` at the top of `page.tsx` / `layout.tsx` / `route.ts`.
- On-demand invalidation from Server Actions / Route Handlers: `revalidateTag('user')` or `revalidatePath('/profile')`.
- `cookies()`, `headers()`, and dynamic `searchParams` opt the route into dynamic rendering. Wrap in `<Suspense>` to keep the rest static.

## File conventions (App Router)

| File | Purpose |
|------|---------|
| `app/layout.tsx` | Required root layout |
| `app/page.tsx` | Route leaf (a URL) |
| `app/loading.tsx` | Suspense fallback for the segment |
| `app/error.tsx` | Error boundary — must be a Client Component |
| `app/global-error.tsx` | Replaces root layout on unhandled error; required for production accessibility |
| `app/not-found.tsx` | 404 UI |
| `app/template.tsx` | Re-rendered-per-navigation layout |
| `app/*/route.ts` | API endpoint; cannot coexist with `page.tsx` at the same path |
| `middleware.ts` | Project root, Edge runtime |

## Metadata

- Static: `export const metadata: Metadata = { title, description }`. Included in the initial HTML.
- Dynamic: `export async function generateMetadata({ params, searchParams }, parent): Promise<Metadata>`. May stream; use only when metadata depends on request data.
- Use `generateStaticParams` to prerender known dynamic segments.

## Route Handlers vs Server Actions

- **Server Actions**: default for internal mutations triggered by React (forms, buttons). Tree-shaken, typed, integrate with `revalidatePath` / `revalidateTag`.
- **Route Handlers**: webhooks, external/third-party clients, public cacheable GET endpoints, non-UI responses (RSS, sitemap).
- Server Actions are **public HTTP endpoints**. Every action must:
  - Validate input with zod (or equivalent).
  - Check auth / authz inside the action — don't trust the caller.
  - Live in a `server-only` data-access layer.

## Middleware

- Single `middleware.ts` at project root. Edge runtime.
- Keep minimal: auth checks, redirects, header rewrites. No DB queries, no heavy compute.
- Scope with `export const config = { matcher: [...] }`.

## Images and fonts

- `next/image` always. Never raw `<img>`. Set `width`/`height` or `fill`. Set `priority` on the LCP / above-the-fold image (default is lazy).
- `next/font/google` or `next/font/local` always. Zero layout shift, self-hosted, auto-subset. Import at the highest shared layout to avoid multiple instances.

## Environment variables

- `.env.local` is gitignored. Never commit.
- Only `NEXT_PUBLIC_*` is embedded client-side. Everything else is server-only.
- Validate env at startup with zod (`@t3-oss/env-nextjs` is the idiomatic wrapper).
- Import `server-only` in any file that references secrets.

## Config baseline

`next.config.ts` kept minimal:

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

Add `images.remotePatterns` for any off-origin images. Resist adding more options — most Next.js footguns come from over-configuration.

## Judgment calls this doc has already made

- App Router only (Pages Router is legacy; don't scaffold it).
- Server Actions for internal mutations, Route Handlers for external-facing APIs.
- `typedRoutes` on by default.
- Explicit caching intent on every `fetch` (no relying on defaults).
