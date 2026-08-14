# Phase 1 rollout runbook

Phase 1 code is not production-complete until these external steps are done. They require Supabase/Vercel/Render access and are intentionally not executed by the coding agent.

## 1. Supabase schema and safety verification

1. Create a staging Supabase project or a point-in-time backup of production.
2. Apply every file in `supabase/migrations/` in filename order, through `0014_bilingual_review_controls.sql`. Do not skip `0003` if document ingestion is enabled. Migrations `0008`–`0014` add the evidence, reviewer, contradiction, reminder, publication-gate, and historical language controls; they intentionally do not publish new legal claims. The current product surface is English-only.
3. Run `scripts/verify_trusted_schema.sql` in the Supabase SQL Editor. It checks the 210 launch coverage cells, RLS, publication gates, and absence of malformed published records.
4. Confirm RLS with two separate authenticated users: each user must see only their own businesses, profiles, documents, conversations, messages, reminders, evidence, and tasks.
5. Run `python scripts/validate_source_catalog.py supabase/seed/obligations.csv` after every catalog change. The validator requires official URLs, citations, review ownership, lifecycle state, effective dates, and valid applicability rules.
6. Do not bulk-publish the legacy seed. A plan with zero obligations is expected until a source snapshot, pinpoint passage, qualified review, applicability rule, and catalog-admin publication gate have all passed.

## 2. Reviewer bootstrap and catalog staging

1. In the Supabase SQL Editor, bootstrap one real authenticated user as the first catalog administrator. Replace the UUID with the user’s Supabase Auth user ID:

   ```sql
   insert into public.reviewer_assignments (reviewer_user_id, reviewer_role, active)
   values ('<AUTH_USER_UUID>', 'catalog_admin', true)
   on conflict (reviewer_user_id, reviewer_role)
   do update set active = true;
   ```

2. From the review console, assign real CA, CS, lawyer, and sector-specialist users. Never use placeholder reviewer names for publishable records.
3. Seed source candidates only as registry metadata. Fetch an immutable source snapshot, approve its source version, extract an exact passage/anchor, create the reviewed claim and applicability rule, collect the required reviewer approvals, and publish through the catalog-admin workflow.
4. Mark each central/Delhi/Maharashtra coverage cell `covered` or `not_applicable` only after the responsible reviewer has signed it. Leave unreviewed cells `blocked` or `in_review`; blocked cells must remain visible as coverage gaps.
5. Keep source monitor credentials server-side. `scripts/monitor_sources.py` needs `SUPABASE_SERVICE_ROLE_KEY`, creates draft versions, and must never be treated as an approval or publishing job.

## 3. Backend configuration

Set these server-only variables on Render (never `VITE_*`):

- `ENVIRONMENT=production`
- `FRONTEND_URL=https://businessrag.vercel.app`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (server-only; required by the background document worker)
- `SUPABASE_JWT_SECRET` for legacy HS256 signing, or `SUPABASE_JWKS_URL` for asymmetric signing keys
- `GEMINI_API_KEY`, `GEMINI_MODEL`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`
- `REDIS_URL` for multi-instance rate limiting
- `ASYNC_DOCUMENT_INGESTION_ENABLED=true` after migration `0003` and Storage bucket policy verification
- `DOCUMENT_STORAGE_BUCKET=documents`
- `DOCUMENT_JOB_MAX_ATTEMPTS=3`
- `DOCUMENT_JOB_LEASE_SECONDS=900`
- `METRICS_ENABLED=true`

Deploy the backend first. Verify `/health`, `/ready`, and `/metrics`; then verify `POST /api/chat/stream`, `GET /api/documents`, `GET /api/documents/{document_id}/status`, `GET /api/workflow/plan?business_id=<uuid>&as_of=YYYY-MM-DD`, and `PATCH /api/workflow/businesses/{business_id}/compliance-profile` with a real authenticated staging user. Run a separate worker with `cd api && python -m src.ingestion.worker` when the Render deployment uses a dedicated worker service.

## 4. Frontend configuration

Set only public client variables on Vercel:

- `VITE_API_URL=https://businessrag.onrender.com`
- `VITE_SUPABASE_URL=https://<project>.supabase.co`
- `VITE_SUPABASE_ANON_KEY=<public-anon-key>`

Deploy the frontend after the backend can answer the authenticated health smoke tests. Do not put Gemini, Pinecone, JWT, or service-role keys in Vercel client variables.

## 5. Canary acceptance gates

- No P0/P1 console errors in a fresh signed-in session.
- A business can be created, edited, selected, and deleted; a second user cannot read it.
- A PDF upload appears in server-side document inventory and can be removed without leaving retrievable vectors.
- With asynchronous ingestion enabled, an upload returns `queued` quickly, progress advances through extraction/chunking/indexing, transient failures retry, and a permanently invalid PDF becomes `failed` with a safe user-facing message.
- A streamed answer renders, preserves citations, and falls back to JSON when streaming is unavailable.
- Compliance Plan shows only reviewed, published, effective obligations with source citations and applicability reasons; `No confirmed applicable obligations`, unanswered questions, and state coverage gaps remain separate and explicit.
- A Technology/IT business does not receive FSSAI; a food business with confirmed food activity can receive only the reviewed FSSAI record; unknown GST status produces a question, while confirmed GST registration can expose GSTR-3B.
- Switching from one business to another refreshes the plan, questions, coverage, and task list without stale obligation cards. A second user cannot read or update the selected business or its compliance profile.
- Legal/tax chat answers are either verified against reviewed evidence or fail closed with missing inputs/coverage/escalation guidance. Citationless model-memory answers are not accepted.
- Rate limits return `429` with `Retry-After` under load; Redis failure is visible in logs/alerts.
- `/metrics` reports request/error/latency counters without user content or tokens.
- Verify at 375px, 768px, and 1440px widths with keyboard-only navigation and reduced motion enabled.

Keep the previous deployment available until the canary has passed for at least one business day. Promote only after error rate, p95 latency, upload success, and auth failure dashboards meet the agreed thresholds.

## 6. Release gate

Run the gate from a trusted operator machine with the production Supabase URL and service-role key loaded only in the shell environment:

```bash
PYTHONPATH=api .venv/bin/python scripts/check_release_gates.py
```

It is expected to fail until the 1,000 English-only evaluation scenarios, coverage cells, source-change queue, and published-record freshness gates are approved. Do not bypass a failed gate; resolve the named review or coverage blocker first.
