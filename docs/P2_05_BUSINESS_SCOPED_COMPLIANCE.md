# Business-scoped, industry-aware Compliance Plan

The Compliance Plan is now built from a user-owned business ID. The backend loads the business and its versioned compliance profile through Supabase RLS, applies reviewed effective-date and jurisdiction gates, and then evaluates a constrained declarative applicability rule. Client-supplied industry, state, and entity values are never trusted.

## Applicability contract

- `GET /api/workflow/plan?business_id=<uuid>&as_of=<date>` returns confirmed obligations, unanswered catalog questions, central/state coverage, and the profile version.
- `PATCH /api/workflow/businesses/{business_id}/compliance-profile` validates and stores questionnaire answers.
- `PATCH /api/workflow/businesses/{business_id}/applicability` validates server-mediated primary-industry and regulated-activity changes; the existing RLS-backed business form persists the same fields during the staged cutover.
- `GET /api/workflow/obligations` is retained only as a business-scoped compatibility route. A jurisdiction-only request is rejected.
- Rule evaluation supports only `all`, `any`, `not`, `eq`, `neq`, `in`, `contains_any`, and `contains_all` over approved fields. Missing facts return `unknown`; malformed or unsupported rules fail closed.

## Rollout

1. Apply every migration in `supabase/migrations/` through `0014_bilingual_review_controls.sql` in filename order. Applying the migrations alone does not publish a legal catalog; it installs fail-closed gates.
2. Run `scripts/verify_trusted_schema.sql` in Supabase and confirm the 210 coverage cells exist, RLS is enabled, and no malformed/unqualified legacy row is published.
3. Bootstrap a real `catalog_admin`, assign qualified reviewers, and stage source snapshots, exact passages, claims, applicability rules, due-date rules, and evidence items. Publish only after the required human approvals are recorded.
4. Deploy the backend and verify the authenticated plan/profile endpoints. Then deploy the frontend with only public `VITE_*` variables.
5. Edit each existing business and explicitly select regulated activities. Complete remaining “Needs your input” questions in Compliance Plan. Existing incomplete profiles should show a verified partial plan plus questions—not guessed obligations.
6. Canary a food business and a Technology/IT business. Their returned obligation IDs must differ; Technology/IT must not receive FSSAI unless food activity was explicitly selected. Unknown GST status must return a question, not GSTR-3B.

### Why an empty plan can be correct

After the trust migrations, `No confirmed applicable obligations` means the database is reachable but no record has simultaneously passed publication, source freshness, qualified review, effective-date, jurisdiction, applicability, and profile-answer checks. It is not evidence that the migration failed. Do not “fix” the empty state by turning on legacy rows or by making industry a universal match.

The coverage registry contains routing declarations for all ten primary industries. `partial` is a disclosure, not a claim of completeness. New legal rows remain unpublished until a human domain owner completes record-level source review.
