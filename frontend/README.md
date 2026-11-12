# PROJECT VOICE — frontend

**Your voice. Your words.** The web app for PROJECT VOICE: create a personal voice once, then
use it to speak any text. Built to `docs/DESIGN.md` against the API in `docs/API_DOCUMENTATION.md`.

## Stack

Next.js 15 (App Router, standalone output) · React 19 · TypeScript (strict) · Tailwind CSS v4
(`@theme inline` over the tokens in `src/styles/tokens.css`) · Radix primitives · TanStack Query ·
Zustand (selected voice + mode, persisted) · framer-motion (introduction only) · lucide-react ·
Vitest + Testing Library. Fonts are self-hosted from npm: `geist` (Sans/Mono) and
`@fontsource/instrument-serif` (display). No external network is needed at build or run time
apart from the npm registry during `pnpm install`.

## Routes

| Route | What it is |
|---|---|
| `/` | Introduction (≤ 2.2 s sequence; static under `prefers-reduced-motion`) |
| `/login`, `/register` | Minimal auth forms; redirect to `/app` (or `?next=`) |
| `/app` | Simple mode: selected voice → text → **Run** → player |
| `/app/voices` | Voice library: select, preview, rename, delete, revoke / re-grant consent |
| `/app/voices/create` | Wizard: record or upload → name + language → consent → upload → processing → ready |
| `/app/history` | Generations newest first, inline play, download, delete, load more |
| `/app/settings` | Display name, preferences (language, format, speed, theme, mode), sign out, delete account |
| `/app/advanced` | Composer with language / speed / format / quality / engine controls and reference-audio panel |
| `/app/developer` | Models, hardware, queue, API keys, curl examples, audit (polls every 5 s) |
| `/app/conversation` | Turn-based conversation over the WebSocket (16 kHz PCM16 up, PCM16 down) |

Everything under `/app/**` is guarded by `GET /users/me` in `src/components/navigation/AppShell.tsx`.

## Plumbing

* `src/lib/api/client.ts` — typed `fetch` against same-origin `/api/v1` with `credentials: include`.
  Reads the `pv_csrf` cookie and sends `X-CSRF-Token` on every mutating request (fetching
  `GET /auth/csrf` once if the cookie is missing). Parses the `{error:{code,message,details}}`
  envelope into `ApiError`. On `401` it performs one `POST /auth/refresh` (with CSRF) and retries;
  if that fails it redirects to `/login?next=…`. `upload()` is the XHR variant with real upload
  progress for `POST /voices`.
* `src/lib/api/types.ts` mirrors the API doc plus the backend's contract clarifications
  (`speech_seconds` nullable while processing, `Job.kind` includes `conversation_turn`, …).
* `src/lib/api/resources.ts` + `hooks.ts` — one TanStack Query hook per resource. Polling:
  generations every 1.5 s while queued/processing, voices every 2 s while processing, developer
  panels every 5 s.
* `next.config.ts` rewrites `/api/:path*` → `${API_INTERNAL_URL ?? http://localhost:8000}/api/:path*`,
  sets `output: "standalone"` and security headers.
* Theme: `data-theme` on `<html>` with a no-flash inline script (`src/lib/theme.ts`); the user's
  saved preference is applied after `/users/me` loads.

### Environment

| Variable | Where | Meaning |
|---|---|---|
| `API_INTERNAL_URL` | server (runtime) | Backend origin for the `/api/*` rewrite. Default `http://localhost:8000`. |
| `NEXT_PUBLIC_WS_BASE` | build time | Optional absolute `ws(s)://` origin for the conversation socket. Default: same origin. |

## Commands

```bash
pnpm install
pnpm dev          # http://localhost:3000 (expects the API on :8000)
pnpm lint
pnpm typecheck
pnpm test
pnpm build && pnpm start
```

## Docker

```bash
docker build -t project-voice-frontend ./frontend
docker run --rm -p 3000:3000 -e API_INTERNAL_URL=http://api:8000 project-voice-frontend
```

Multi-stage `node:22-alpine`, pnpm via corepack, Next standalone output, runs as the non-root
`nextjs` user on port 3000.

## Design notes

Restraint is the brief. One accent colour (the Run button, the selected voice, live recording),
hairline borders instead of shadows, Instrument Serif only for display moments, Geist Mono for
numbers and developer surfaces. Progress is always real: the Run button shows the backend's
`progress.stage` text ("Synthesising 2 of 4") and a 1 px bar sized `current / total`; when the
backend sends no progress it says "Queued" or "Processing" — never a fabricated percentage.
