-- Source-catalog publication gate.
-- Apply after 0001. Existing obligations remain unpublished until a reviewer
-- confirms the authority, version, jurisdiction, and effective date window.

alter table public.obligations
  add column if not exists published boolean not null default false;

create index if not exists obligations_published_jurisdiction_idx
  on public.obligations(published, jurisdiction, effective_from);

comment on column public.obligations.published is
  'Only reviewed, source-backed records may be shown to end users.';

-- The application intentionally has no guessed legal records. Populate this
-- table through a controlled review/import job, then set published=true only
-- after source QA and effective-date verification.
