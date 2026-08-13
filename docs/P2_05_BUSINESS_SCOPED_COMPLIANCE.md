# Business-scoped, industry-aware Compliance Plan

The Compliance Plan is now built from a user-owned business ID. The backend loads the business and its versioned compliance profile through Supabase RLS, applies reviewed effective-date and jurisdiction gates, and then evaluates a constrained declarative applicability rule. Client-supplied industry, state, and entity values are never trusted.

## Applicability contract

- `GET /api/workflow/plan?business_id=<uuid>&as_of=<date>` returns confirmed obligations, unanswered catalog questions, central/state coverage, and the profile version.
- `PATCH /api/workflow/businesses/{business_id}/compliance-profile` validates and stores questionnaire answers.
- `PATCH /api/workflow/businesses/{business_id}/applicability` validates server-mediated primary-industry and regulated-activity changes; the existing RLS-backed business form persists the same fields during the staged cutover.
- `GET /api/workflow/obligations` is retained only as a business-scoped compatibility route. A jurisdiction-only request is rejected.
- Rule evaluation supports only `all`, `any`, `not`, `eq`, `neq`, `in`, `contains_any`, and `contains_all` over approved fields. Missing facts return `unknown`; malformed or unsupported rules fail closed.

## Rollout

1. Apply `0006_business_scoped_applicability.sql`.
2. Apply `0007_industry_catalog_coverage.sql`.
3. Deploy the backend and verify the new plan/profile endpoints with an authenticated user.
4. Deploy the frontend.
5. Edit each existing business and explicitly select regulated activities. Complete remaining “Needs your input” questions in Compliance Plan.
6. Canary a food business and a Technology/IT business. Their plan IDs must differ, and the technology business must not receive FSSAI unless a food activity was explicitly selected.

The coverage registry contains routing declarations for all ten primary industries. `partial` is a disclosure, not a claim of completeness. New legal rows remain unpublished until a human domain owner completes record-level source review.
