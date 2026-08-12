# Phase 1 rollout runbook

Phase 1 code is not production-complete until these external steps are done. They require Supabase/Vercel/Render access and are intentionally not executed by the coding agent.

## 1. Supabase staging

1. Create a staging Supabase project or a point-in-time backup of production.
2. Apply `supabase/migrations/0001_core_workflow_schema.sql`, then `0002_publish_gate_and_catalog_checks.sql`, then `0003_async_document_jobs.sql` when enabling asynchronous ingestion.
3. Confirm RLS is enabled on every table and test with two separate authenticated users: each user must see only their own businesses, documents, conversations, messages, and tasks.
4. Run `python scripts/validate_source_catalog.py supabase/seed/obligations.csv` after adding reviewed rows. Keep `published=false` until a domain reviewer signs off.
5. Publish only reviewed records with `published=true`; verify the UI returns zero records for an unpublished catalog.

## 2. Backend configuration

Set these server-only variables on Render (never `VITE_*`):

- `ENVIRONMENT=production`
- `FRONTEND_URL=https://businessrag.vercel.app`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (server-only; required by the background document worker)
- `SUPABASE_JWT_SECRET` for legacy HS256 signing, or `SUPABASE_JWKS_URL` for asymmetric signing keys
- `GROQ_API_KEY`, `GEMINI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`
- `REDIS_URL` for multi-instance rate limiting
- `ASYNC_DOCUMENT_INGESTION_ENABLED=true` after migration `0003` and Storage bucket policy verification
- `DOCUMENT_STORAGE_BUCKET=documents`
- `DOCUMENT_JOB_MAX_ATTEMPTS=3`
- `DOCUMENT_JOB_LEASE_SECONDS=900`
- `METRICS_ENABLED=true`

Deploy the backend first. Verify `/health`, `/ready`, and `/metrics`; then verify `POST /api/chat/stream`, `GET /api/documents`, `GET /api/documents/{document_id}/status`, and `GET /api/workflow/obligations` with a real authenticated staging user. Run a separate worker with `cd api && python -m src.ingestion.worker` when the Render deployment uses a dedicated worker service.

## 3. Frontend configuration

Set only public client variables on Vercel:

- `VITE_API_URL=https://businessrag.onrender.com`
- `VITE_SUPABASE_URL=https://<project>.supabase.co`
- `VITE_SUPABASE_ANON_KEY=<public-anon-key>`

Deploy the frontend after the backend can answer the authenticated health smoke tests. Do not put Groq, Gemini, Pinecone, JWT, or service-role keys in Vercel client variables.

## 4. Canary acceptance gates

- No P0/P1 console errors in a fresh signed-in session.
- A business can be created, edited, selected, and deleted; a second user cannot read it.
- A PDF upload appears in server-side document inventory and can be removed without leaving retrievable vectors.
- With asynchronous ingestion enabled, an upload returns `queued` quickly, progress advances through extraction/chunking/indexing, transient failures retry, and a permanently invalid PDF becomes `failed` with a safe user-facing message.
- A streamed answer renders, preserves citations, and falls back to JSON when streaming is unavailable.
- Compliance Plan shows only reviewed, published, effective obligations; empty/unavailable source state remains explicit.
- Rate limits return `429` with `Retry-After` under load; Redis failure is visible in logs/alerts.
- `/metrics` reports request/error/latency counters without user content or tokens.
- Verify at 375px, 768px, and 1440px widths with keyboard-only navigation and reduced motion enabled.

Keep the previous deployment available until the canary has passed for at least one business day. Promote only after error rate, p95 latency, upload success, and auth failure dashboards meet the agreed thresholds.
