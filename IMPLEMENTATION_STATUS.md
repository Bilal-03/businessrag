# BizGuide implementation status

Last updated: 2026-08-12

This is the working status list for the implementation plan. Update it whenever a slice is completed; do not mark a task complete until its verification checks pass.

Status legend: `[x]` implementation verified in the repository; `[ ]` blocked on external rollout or unfinished code. External gates are listed separately below.

## Completed

- [x] **P0-01 — Safety gate and truthful product language**
  - Hidden the legacy hard-coded checklist navigation and route.
  - Replaced overclaiming copy with India-focused educational-beta language.
  - Added source/professional verification disclosures and corrected the primary CTA.
- [x] **P0-02 — Accessibility and destructive-action safeguards**
  - Added focus-visible/reduced-motion styles, keyboard activation, labelled controls, dialog semantics, Escape handling, live status regions, and two-step deletion confirmation.
- [x] **P0-03 — Frontend security baseline**
  - Added Vercel CSP, HSTS, clickjacking, MIME, referrer, permissions, COOP, and static-asset caching headers.
  - Added `web/.env.example` and documented public-vs-server secret boundaries.
- [x] **P1-01 — API/data contract foundation**
  - Added bounded chat history, business/conversation context IDs, grounding state, citation contracts, and document identity metadata.
  - Added additive Supabase workflow migration with RLS for businesses, documents, conversations, messages, sources, obligations, and tasks.
- [x] **P1-02 — Source-aware AI and streaming**
  - Added user/business-scoped retrieval metadata, prompt-injection boundaries, citations, grounding states, SSE token streaming, and legacy JSON fallback.
  - Added citation rendering and bounded conversation history in the UI.
- [x] **P1-03 — Entity-scoped onboarding foundation**
  - Added stable active-business context, jurisdiction/state capture, business-scoped uploads and chat payloads, and Pinecone business filters.
  - Kept obligation claims gated until the source-backed dataset is live.
- [x] **P1-04 — Performance and release hardening**
  - Added lazy-loaded panels/Markdown, a render error boundary, system-font fallback, immutable asset caching, and vendor code splitting.
  - Reduced the initial JavaScript chunk from roughly 735 KB to 23 KB; no built chunk exceeds 205 KB.

## In progress / next

- [x] **P1-05 — Authenticated obligations/tasks API and dashboard foundation**
  - Added RLS-backed obligations reads and task CRUD endpoints with validated identifiers, owner-token forwarding, effective-date filtering, and fail-closed storage errors.
  - Added the Compliance Plan dashboard with source status, jurisdiction gating, published obligation citations, user planning tasks, status updates, deletion confirmation, and mobile layout.
  - The migration still must be applied before this view can show live records; the legacy checklist remains hidden.
- [x] **P1-06 — Persistence cutover implementation**
  - Live browser writes now use normalized `businesses`, `conversations`, `messages`, and `message_sources` tables behind Supabase RLS.
  - Documents now use a server-side owner-scoped inventory with processing/indexed/failed/deleted status.
  - Added one-time migration of valid legacy businesses/conversations; stale checklist state and browser upload history are intentionally discarded.
  - **External gate:** apply migrations in staging and verify RLS before exposing the new live path.
- [x] **P1-07 — Observability and scale baseline**
  - Added privacy-safe request/error/latency metrics, request IDs, stream rate-limit coverage, token-fingerprint limiting, and optional Redis shared rate limiting.
  - Added production configuration/runbook for Redis and metrics.
  - **Deferred to Phase 2:** asynchronous document queue/worker and full Sentry/PostHog product analytics.
- [x] **P1-08 — Responsive/product polish baseline**
  - Added mobile drawer backdrop, touch-sized controls, safe-area chat composer, modal focus trapping, document inventory states, and persistence status messaging.
  - **Deferred to Phase 2:** full visual rebrand and real-device WCAG audit.
- [x] **P1-09 — Verification and rollout**
  - User-confirmed production checks passed for Render health/readiness, Vercel-to-Render connectivity, Supabase migrations/RLS, authentication, chat streaming/fallback, uploads, business context switching, task CRUD/deletion confirmation, rate limiting, responsive layouts, and keyboard/reduced-motion behavior.
  - The live deployment was canaried and promoted after the user verified the critical flows; the previous deployment remains available for rollback.

- [x] **P2-01 — Browser smoke tests and CI guardrails**
  - Added six Playwright smoke tests covering sign-in, source-aware chat streaming, AI error recovery, PDF validation/upload, business switching/task deletion, and mobile navigation.
  - Tests use deterministic Supabase/API route fixtures and never require production credentials or mutate production data.
  - Added Chromium test configuration, local test commands, and a GitHub Actions workflow running lint, build, and browser tests on pushes and pull requests to `main`.

- [x] **P2-02 — Asynchronous document ingestion**
  - Implemented behind `ASYNC_DOCUMENT_INGESTION_ENABLED` with a backward-compatible synchronous path when disabled.
  - Added private Supabase Storage source objects, Redis-backed queueing with an in-process development fallback, crash recovery, leases, retries, deterministic Pinecone vector IDs, idempotent upload keys, job/document progress fields, and a status endpoint.
  - Added frontend progress polling, processing stages, safe failure messages, and source cleanup on document deletion.
  - **External gate complete:** user verified the Supabase migration, Render service-role/Redis configuration, live deployment, queued-to-indexed PDF canary, and deletion flow.

- [x] **P2-02 hotfix — Redis worker polling timeout**
  - Fixed the Redis client socket timeout being shorter than the blocking `BRPOP` interval, which caused repeated `redis.exceptions.TimeoutError` worker failures on an idle queue.
  - Added recoverable timeout handling and connection health checks so transient Redis read timeouts do not kill document processing.

- [x] **P2-02 hotfix — Upload CORS preflight**
  - Allowed the `X-Idempotency-Key` header used by async uploads so browser preflight requests no longer fail with `400 Bad Request` before the upload reaches the API.

- [x] **P2-03a — Privacy-safe observability integration**
  - Added Sentry browser error capture with PII disabled, zero tracing/replay sampling, request/error scrubbing, and coarse source tags.
  - Added PostHog Product Analytics with explicit allow-listed workflow events, autocapture/pageview/replay disabled, and anonymous-only profiles until an explicit identity policy is approved.
  - Added Vercel CSP allowlist entries, public environment documentation, regional ingest compatibility, and lazy SDK loading so monitoring does not inflate the initial bundle when disabled.
  - Verification: frontend lint, production build, diff integrity, and all six deterministic Chromium smoke tests pass (with the local server run outside the restricted sandbox).

- [ ] **P2-03 — Product intelligence, accessibility, and design-system upgrade**
  - Observability implementation is complete in P2-03a; remaining work is event dashboards, real-device WCAG 2.2 AA checks, and the design-system upgrade.
  - Run real-device WCAG 2.2 AA checks across iOS Safari, Android Chrome, tablet, keyboard-only, screen-reader, contrast, focus, and reduced-motion flows.
  - Replace the MVP visual layer with a documented token-based design system, premium responsive components, and measured performance budgets.
  - **External gate:** validate analytics events without leaking document contents or tokens, complete the device matrix, and approve the visual regression baseline.

## Verification baseline

- Backend: `./venv/bin/python -m pytest -q api/tests` — 25 passing.
- Frontend: `npm run lint` — passing.
- Frontend: `npm run build` — passing with split chunks.
- Browser: `npm run test:e2e` — 6 passing (Chromium; deterministic route fixtures).
- Source catalog: `./venv/bin/python scripts/validate_source_catalog.py` — passing (0 rows; no obligations are published by default).
- Integrity: `git diff --check` — passing.

## Post-rollout fixes

- [x] **Compliance Plan business context selector**
  - Added an explicit business workspace selector to the Compliance Plan header so users with multiple businesses can switch context without leaving the page.
  - Switching the workspace refreshes jurisdiction-scoped obligations and owner-scoped planning tasks.
- [x] **Compliance Plan task-row layout and deletion confirmation**
  - Fixed the status select width overriding the task layout, which collapsed task titles and due dates.
  - Added a visible `Confirm delete` state while retaining the two-step destructive-action safeguard.

## Operational follow-ups

- [x] User confirmed the Supabase migrations, production environment variables, backend-first deployment, and authenticated canary checks described in `docs/PHASE_1_ROLLOUT.md`.
- [ ] Populate and domain-review `supabase/seed/obligations.csv`; publish only reviewed rows. The current empty catalog is an intentional fail-closed state, not a complete compliance dataset.
- [x] Finish the P2-02 external migration/worker canary; user verified the live queued-to-indexed document flow.
- [ ] Start P2-03 product analytics, real-device WCAG audit, and design-system upgrade.
