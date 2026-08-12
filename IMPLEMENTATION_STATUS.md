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
- [ ] **P1-09 — Verification and rollout**
  - Add browser-level smoke tests for auth, chat fallback/streaming, upload, business context, deletion confirmation, and error recovery.
  - Canary the new backend while the current public app remains online, then promote by measured success/error/latency thresholds.
  - Local browser verification was blocked by the browser sandbox's localhost network boundary; production inspection confirmed the public URL is still the pre-cutover deployment.

## Verification baseline

- Backend: `./venv/bin/python -m pytest -q api/tests` — 20 passing.
- Frontend: `npm run lint` — passing.
- Frontend: `npm run build` — passing with split chunks.
- Source catalog: `./venv/bin/python scripts/validate_source_catalog.py` — passing (0 rows; no obligations are published by default).
- Integrity: `git diff --check` — passing.

## External gates still required

- Apply `supabase/migrations/0001_core_workflow_schema.sql` and `0002_publish_gate_and_catalog_checks.sql` in staging, then production after backup/RLS verification.
- Populate and domain-review `supabase/seed/obligations.csv`; publish only reviewed rows.
- Set Render/Vercel environment variables and deploy backend before frontend.
- Run authenticated canary/e2e tests on staging and promote the deployment only after the gates in `docs/PHASE_1_ROLLOUT.md` pass.
