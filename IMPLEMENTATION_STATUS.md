# BizGuide implementation status

Last updated: 2026-08-13

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
  - **External gate complete:** user confirmed PostHog live events and a production Sentry test issue in the `bizguide-web` project.

- [x] **P2-03 — Product intelligence, accessibility, and design-system upgrade**
  - Observability implementation is complete in P2-03a. The repository now includes the first product/design-system slice plus a visible product-surface redesign: a clearer source-first hero, workspace context signal, workflow-oriented quick actions, refreshed navigation shell, stronger chat composer, premium panel/card surfaces, responsive tablet/mobile treatment, documented CSS tokens, stronger focus/forced-colors behavior, skip-link/main landmark, semantic business expanders, keyboard-operable custom selects, 44px touch targets, and privacy-safe workspace/auth funnel events.
  - The secondary-screen slice is now implemented: business and source-library context badges, explicit upload empty states, two-step document deletion confirmation, visible confirmation guidance, and Settings sections exposed as keyboard-operable ARIA tabs.
  - The visible redesign is intentionally presentation-only; existing API contracts, upload behavior, business switching, task CRUD, and observability behavior remain unchanged.
  - [x] Added a dedicated accessibility device-preflight config and 12 checks across desktop Chrome, iPhone, Pixel, and iPad profiles. The latest run is 12/12 passing.
  - [x] Removed chat-composer autofocus, standardized the skip link/sidebar collapse control to 44px, restored a valid global focus token, and verified reduced-motion behavior.
  - [x] Added deterministic desktop/tablet/mobile visual baselines. The latest approval run is 3/3 passing with no diffs.
  - [x] Completed the code-owned contrast review and mapped legacy color aliases/gradients to canonical design tokens.
  - [x] Added the exact PostHog dashboard build sheet and privacy acceptance checks in `docs/P2_03_POSTHOG_DASHBOARDS.md`.
  - [x] **External gate:** user confirmed the signed-in PostHog dashboard setup and production accessibility checks were completed, including physical iPhone Safari/VoiceOver, Android Chrome/TalkBack, iPad, and keyboard-only desktop verification. Emulated browser profiles remain regression evidence, not a substitute for the physical-device checks.

- [x] **P2-04 — Reviewed compliance source catalog and obligation publishing**
  - Added explicit draft/reviewed/published lifecycle metadata, citations, review ownership, review timestamps, official-source constraints, and publish-state checks in migrations `0004` and `0005`.
  - Added an initial reviewed source slice for FSSAI, CBIC GST, and Delhi Labour; kept the Maharashtra row reviewed-but-unpublished until its commencement notification is separately verified.
  - Strengthened the CSV validator and API/UI gates so only current, cited, reviewed, published records can reach Compliance Plan; malformed, unreviewed, future, expired, or unavailable records remain hidden.
  - Documented source review and staging rollout in `docs/P2_04_SOURCE_CATALOG.md`.

## Verification baseline

- Backend: `./venv/bin/python -m pytest -q api/tests` — 26 passing.
- Frontend: `npm run lint` — passing.
- Frontend: `npm run build` — passing with split chunks.
- Browser: `npm run test:e2e` — 8 passing (Chromium; deterministic route fixtures).
- Accessibility: `npm run test:e2e:accessibility` — 12 passing across four device profiles.
- Visual regression: `npm run test:e2e:visual` — 3 passing with approved desktop/tablet/mobile baselines.
- Source catalog: `./venv/bin/python scripts/validate_source_catalog.py supabase/seed/obligations.csv` — passing (4 rows; 3 published, 1 reviewed-but-unpublished).
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
- [x] Populate and domain-review the initial `supabase/seed/obligations.csv`; publish only rows with complete review evidence. The catalog remains intentionally narrow and does not claim to be a complete compliance dataset.
- [x] Finish the P2-02 external migration/worker canary; user verified the live queued-to-indexed document flow.
- [x] Complete the P2-03 external gate: user confirmed the PostHog saved insights/dashboard and physical-device accessibility results.
- [ ] External gate: apply migrations `0004` and `0005` in staging, verify RLS/authenticated reads and central-plus-state jurisdiction behavior, then promote the catalog only after domain owners confirm the source slice.
