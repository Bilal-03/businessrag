# P2-04 reviewed compliance source catalog

P2-04 replaces the empty compliance catalog with a controlled, source-backed import manifest. The catalog is an educational product input, not legal or tax advice. A domain owner must re-check each source before a production publish or after an authority updates the source.

## Catalog lifecycle

Each obligation carries an explicit lifecycle state:

- `draft`: captured for review; never user-visible.
- `reviewed`: source, citation, jurisdiction, owner, and effective window have been checked; still not user-visible until deliberately published.
- `published`: the reviewed row is approved for the user-facing plan.

The database keeps the legacy `published` boolean for compatibility, but `published=true` is accepted only when `review_status=published`. Existing boolean-only rows are reset to draft/unpublished by migration `0004_reviewed_obligation_catalog.sql`.

## Initial source slice

The controlled seed migration and CSV manifest include these official sources:

| Scope | Source | Catalog treatment |
| --- | --- | --- |
| India | [FSSAI licensing page](https://fssai.gov.in/cms/licensing.php) | Published central obligation; cite the FSS Act section 31(1) and the 2011 licensing/registration regulations. |
| India | [CBIC CGST Rules, 2017](https://cbic-gst.gov.in/pdf/10112020_CGST-Rules-2017_Part-A_Rules.pdf) | Published central obligation; cite section 39, rule 61, and Form GSTR-3B. |
| Delhi | [Delhi Labour Department inspectorate summary](https://labour.delhi.gov.in/labour/inspectorate) | Published state obligation for the listed employment-condition provisions, with the department’s 1 Feb 1955 commencement date and subject to exemptions. |
| Maharashtra | [Maharashtra Shops and Establishments Act, 2017](https://mahakamgar.maharashtra.gov.in/Site/Upload/Pdf/Shops_Establishment_Regulation_of_Employment_Conditions_Eng_27.02.2018.pdf) | Reviewed but unpublished until commencement and current exemptions are separately verified. |

`India` rows are included alongside an exact state match when a business has a state jurisdiction. A state row must still use the exact state name captured by the business profile.

## Publish and display gates

The catalog validator rejects missing citations, non-official URLs, invalid dates, unknown lifecycle states, mismatched `published` flags, missing review ownership/timestamps, duplicate source versions, and expired published rows.

The API and UI independently require all of the following before display:

1. `published=true` and `review_status=published`.
2. A non-empty HTTPS official source URL and citation.
3. A non-empty review owner and review timestamp not in the future.
4. A non-null `effective_from` that is not later than the requested date.
5. No `effective_to`, or an `effective_to` on or after the requested date.

If the schema is unavailable, the catalog response fails validation, or no record passes these checks, Compliance Plan shows an explicit unavailable/empty state and does not fall back to the legacy checklist.

## Verification and rollout

```text
./venv/bin/python scripts/validate_source_catalog.py supabase/seed/obligations.csv
./venv/bin/python -m pytest -q api/tests
cd web && npm run lint && npm run build && npm run test:e2e
```

Apply migrations in order through `0005_seed_reviewed_obligations.sql` in staging first. Verify the source query with an authenticated business in Maharashtra and Delhi, then repeat with an unpublished, expired, and schema-missing row to confirm the fail-closed behavior before production promotion.
