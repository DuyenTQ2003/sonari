# apps/web

Next.js 15 App Router (TypeScript, Tailwind v4). One page, `/`: it shows a practice sentence, records
the learner with MediaRecorder, and prints the speech service's answer as raw JSON. No accounts, no
progress, no gamification. Learner-facing copy is only in `messages/vi.json` (a test fails on a
Vietnamese letter in the source and on a key with no copy).

```
browser ── /api/speaking-items ──> core   GET  /v1/speaking-items
        └─ /api/score ───────────> speech POST /v1/score   (multipart: audio, referenceText)
```

The route handlers (`app/api/*/route.ts`, `lib/proxy.ts`) are the only thing that knows the service
URLs, so the browser talks to one origin. They return the services' answers unchanged (status, body,
`Retry-After`), forward nothing from the browser but the two form fields, and answer 502 or 500 in the
services' own error envelope when a service is down or `CORE_URL` / `SPEECH_URL` is unset.

## Run it

Node 22 must be installed where you run make; in WSL, inside the distro (the Windows node does not count).

```bash
make dev                      # infra (Docker) + core :8000 + speech :8001 + web :3000
make ingest-sources           # once: the 724 passages into content.sources (needs `make voa-trim` first)
make ingest-speaking-items    # once: the 20 sentences
```

Open http://localhost:3000 (`localhost` counts as a secure context, so the microphone works; another
host name needs HTTPS). By hand: `cp .env.example .env.local && npm ci && npm run dev`.

| Variable | Used by | Meaning |
|---|---|---|
| `CORE_URL` | `/api/speaking-items` | base URL of the core service |
| `SPEECH_URL` | `/api/score` | base URL of the speech service |

`npm run typecheck`, `npm test` (vitest) and `npm run build` are what CI runs (`make typecheck-web
test-web build-web`).

## Dependencies, and why

| Package | Why it is here |
|---|---|
| `next`, `react`, `react-dom` | the framework; Next 15 per CLAUDE.md |
| `tailwindcss`, `@tailwindcss/postcss` | styling; CLAUDE.md names Tailwind |
| `typescript`, `@types/*` | typecheck; pinned to 5.x because TypeScript 7 is the native rewrite and Next 15 reads the 5.x API |
| `vitest` | the proxy-route tests: it runs TypeScript as is, so the handlers are tested without a bundler |

Not added on purpose: shadcn, Zustand, TanStack Query, Framer Motion, next-intl (one locale and a
16-line `t()` do the job), ESLint (no task asked for it), a DOM test library (the page is checked in a
real browser instead).

## Known limits

- The proxy is open: no auth and no rate limit, as the brief says. The speech service's gate answers
  503 under load, but anyone who can reach the page can send audio to the model.
- The raw JSON is long (about 30 phonemes per sentence); that is the point of this page.
- Recorded format: whatever `MediaRecorder` offers, WebM/Opus first, then Ogg/Opus, then MP4. The
  service decodes all three.
