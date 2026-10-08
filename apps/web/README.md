# apps/web

Next.js 15 App Router (TypeScript, Tailwind v4). One page, `/`: it shows a practice sentence, records
the learner with MediaRecorder, and shows the speech service's answer word by word (below). No accounts,
no progress, no gamification. Learner-facing copy is only in `messages/vi.json` (a test fails on a
Vietnamese letter in the source and on a key with no copy).

```
browser ── /api/speaking-items ──> core   GET  /v1/speaking-items
        └─ /api/score ───────────> speech POST /v1/score   (multipart: audio, referenceText)
```

The route handlers (`app/api/*/route.ts`, `lib/proxy.ts`) are the only thing that knows the service
URLs, so the browser talks to one origin. They return the services' answers unchanged (status, body,
`Retry-After`), forward nothing from the browser but the two form fields, and answer 502 or 500 in the
services' own error envelope when a service is down or `CORE_URL` / `SPEECH_URL` is unset.

## The result view

`app/result.tsx` (a pure view) and `lib/score.ts` (types, `pieces`, `fixText`) turn `POST /v1/score`
into what a learner reads:

- The sentence word by word, from the response's character offsets, so punctuation stays. A word with
  a `wrong` phoneme is underlined solid and bold ("needs work"); an `unclear` word is underlined with
  dots and is never styled as an error (the model is not sure); a correct word has no underline. Phoneme
  rows carry a glyph (✓ ~ ✗) and a word (Đúng, Chưa rõ, Cần luyện), so the three verdicts never rest on
  colour alone. A legend line explains the underlines.
- Tapping a word shows its phonemes; each wrong one shows `pronunciation.fix.<rule>.why` and `.how`
  from `messages/vi.json`. A rule this app has no copy for falls back to `generic`, which claims no cause.
- No percentage, no number, no overall score: the thresholds (v2, wrong below -5.0) are calibrated on
  native speakers only. A test fails if a digit or `%` reaches the rendered result.
- A line says scoring is experimental. Previous, next and "try this sentence again" move through the 20
  sentences.
- The raw response shows only behind `?debug` (`/?debug`).

Tests (`tests/result.test.tsx`) render the view with `react-dom/server` (no DOM library) from fixtures
that `tests/fixtures.ts` builds and validates against `packages/contracts/schema/score-response.schema.json`.
Clicking, the picker and the layout were checked in headless Chromium against a stand-in for the services.

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
| `vitest` | the proxy-route and view tests: it runs TypeScript as is, so the handlers are tested without a bundler (`vitest.config.ts` only turns JSX on; Next compiles it itself) |
| `ajv` (dev only) | the view tests validate every fixture against the contract's JSON Schema (2020-12); no runtime use |

Not added on purpose: shadcn, Zustand, TanStack Query, Framer Motion, next-intl (one locale and a
16-line `t()` do the job), ESLint (no task asked for it), a DOM test library (the page is checked in a
real browser instead).

## Known limits

- The proxy is open: no auth and no rate limit, as the brief says. The speech service's gate answers
  503 under load, but anyone who can reach the page can send audio to the model.
- The view does not check the response against the schema at run time: an answer without `words` is
  refused with the generic error, and nothing else is validated.
- Recorded format: whatever `MediaRecorder` offers, WebM/Opus first, then Ogg/Opus, then MP4. The
  service decodes all three.
