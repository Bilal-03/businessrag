# Trusted BizGuide release control

The code platform is designed to fail closed. That does **not** make the legal catalog complete. Production promotion requires both technical checks and external professional review.

## Implemented safeguards

- Legal/tax questions cannot fall back to model memory. They resolve to active reviewed claim evidence or `cannot_verify` with a professional brief.
- Official sources and private uploaded-document evidence are separate response modes and citation types.
- Source content is versioned by SHA-256 with immutable snapshot fields, effective dates, last-checked dates, fetch health, and reviewer status.
- Atomic claims carry declarative applicability rules, risk, source-passage IDs, freshness deadlines, and qualified-review requirements.
- Publication is database-gated. High-risk, deadline, rate, threshold, penalty, and eligibility claims require two distinct approvals.
- Changed or unavailable source monitoring records a review event and quarantines affected high/critical claims.
- Business profiles and answers are owner-scoped and versioned. Legal applicability is never inferred from a name or description.
- Compliance plans disclose central/state module gaps, explain applicability, refuse malformed due-date formulas, and expose evidence requirements.
- In-app reminders have timezone, default 30/14/7/1-day offsets, snooze/dismiss state, recurrence storage, and immutable events.
- Reviewer APIs/UI cover source and claim creation, review decisions, publishing/quarantine transitions, source-change queues, and audit history.

## External launch blockers

These cannot honestly be completed by software or by AI:

1. Assign real CA, CS, lawyer, sector-specialist, bilingual-reviewer, and catalog-admin user IDs in `reviewer_assignments`.
2. Capture immutable source snapshots and pinpoint passages. A source-family URL alone is not evidence.
3. Draft and professionally approve every common/activity claim, due-date rule, evidence item, and coverage cell for India, Delhi, and Maharashtra.
4. Run the generated 2,000-case evaluation manifest. Reviewers must approve every case; generated `pending_qualified_review` rows do not count.
5. Complete security review, backup/restore drill, accessibility and real-device bilingual QA, and a pilot with at least 20 representative SME owners.
6. Run `scripts/check_release_gates.py`. Production promotion is blocked unless it exits zero.

## Required rollout order

1. Back up Supabase and apply migrations `0008` then `0009` in staging.
2. Configure reviewer identities. Validate RLS with two unrelated users and every reviewer role.
3. Run source ingestion and monitoring in a private worker. Review all source versions before claim work.
4. Complete and approve coverage cells; never replace `blocked` with `covered` based on row count.
5. Run API, browser, injection, stale/change, and 2,000-case evaluations.
6. Canary food, technology, retail, and finance businesses in both states. Their applicable obligation/claim IDs must differ when facts differ.
7. Promote only after the release-gate command passes and reviewers record launch approval.

## Useful commands

```bash
python scripts/generate_trust_evaluations.py
.venv/bin/pytest -q api/tests
cd web && npm run lint && npm run build && npm run test:e2e
python scripts/monitor_sources.py
python scripts/check_release_gates.py
```
