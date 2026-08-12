# Reviewed obligation catalog

This CSV is deliberately empty in the repository. Do not manufacture compliance records or publish an LLM-generated list.

Before enabling `published=true`, a reviewer must verify each row against the official government source, record the source version/date, confirm the jurisdiction, and check the effective window. Import reviewed rows through a protected Supabase migration or an admin-only job; never expose the service-role key to the browser.

Required fields:

- `jurisdiction`: exact state/central scope used by the product.
- `title`, `description`: concise plain-language explanation, not legal advice.
- `source_url`: HTTPS official source URL.
- `source_version`: notice/circular/version date or identifier.
- `effective_from`, `effective_to`: ISO dates; leave `effective_to` blank for open-ended records.
- `published`: keep `false` until review is complete.
