-- Reviewed compliance source catalog.
-- Apply after 0001, 0002, and 0003. Legacy obligations are deliberately
-- moved back to draft/unpublished because their review evidence is unknown.

alter table public.obligations
  add column if not exists review_status text not null default 'draft',
  add column if not exists source_citation text,
  add column if not exists review_owner text,
  add column if not exists reviewed_at timestamptz;

-- A pre-P2-04 row cannot be treated as reviewed merely because it was marked
-- published under the old boolean-only gate.
update public.obligations
set published = false,
    review_status = 'draft'
where published = true
  and review_status <> 'published';

alter table public.obligations
  drop constraint if exists obligations_review_status_check,
  drop constraint if exists obligations_source_url_https_check,
  drop constraint if exists obligations_source_url_authority_check,
  drop constraint if exists obligations_review_metadata_check,
  drop constraint if exists obligations_publish_state_check;

alter table public.obligations
  add constraint obligations_review_status_check
    check (review_status in ('draft', 'reviewed', 'published')),
  add constraint obligations_source_url_https_check
    check (source_url ~* '^https://') not valid,
  add constraint obligations_source_url_authority_check
    check (source_url ~* '^https://[^/?#]+(\.gov\.in|\.nic\.in|\.org\.in)([/?:#]|$)') not valid,
  add constraint obligations_review_metadata_check
    check (
      review_status = 'draft'
      or (
        effective_from is not null
        and source_citation is not null
        and char_length(btrim(source_citation)) between 1 and 2000
        and review_owner is not null
        and char_length(btrim(review_owner)) between 1 and 160
        and reviewed_at is not null
      )
    ),
  add constraint obligations_publish_state_check
    check (published = (review_status = 'published'));

create index if not exists obligations_reviewed_current_idx
  on public.obligations(review_status, published, jurisdiction, effective_from, effective_to);

comment on column public.obligations.review_status is
  'Catalog lifecycle: draft, reviewed, or published. Only published rows can enter the user-facing plan.';
comment on column public.obligations.source_citation is
  'Human-readable citation to the controlling act, rule, section, circular, or official notice.';
comment on column public.obligations.review_owner is
  'Role or team accountable for the source review; not a browser-controlled user field.';
comment on column public.obligations.reviewed_at is
  'Timestamp at which the source, jurisdiction, citation, and effective window were reviewed.';
