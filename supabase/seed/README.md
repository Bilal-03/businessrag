# Reviewed obligation catalog

This CSV is the review/import manifest for the initial source-backed catalog. It is not a general checklist and must not be expanded from generated or secondary content. The matching controlled seed migration is `supabase/migrations/0005_seed_reviewed_obligations.sql`.

Before enabling `published=true`, a reviewer must verify each row against the official government source, record the source version/date and citation, confirm the jurisdiction, check the effective window, and assign a review owner. Import reviewed rows through a protected Supabase migration or an admin-only job; never expose the service-role key to the browser.

Required fields:

- `jurisdiction`: exact state/central scope used by the product.
- `title`, `description`: concise plain-language explanation, not legal advice.
- `source_url`: HTTPS official source URL.
- `source_version`: notice/circular/version date or identifier.
- `source_citation`: act/rule/section/circular/notice citation supporting the description.
- `effective_from`, `effective_to`: ISO dates; `effective_from` is required and `effective_to` may be blank for open-ended records.
- `review_status`: exactly `draft`, `reviewed`, or `published`.
- `review_owner`: accountable role/team for the review.
- `reviewed_at`: UTC ISO timestamp required for `reviewed` and `published` rows.
- `published`: must be `true` only when `review_status=published`; otherwise keep it `false`.

The API and Compliance Plan apply a second gate: a row must be `published`, have review evidence, have an HTTPS source and citation, and be active on the requested date. Central (`India`) rows are included with a selected state; state rows still require an exact jurisdiction match. An unpublished or expired row is never displayed.
