-- Human-reviewed bilingual terminology and consistency status.

alter table public.reviewed_claims
  add column if not exists bilingual_consistency_status text not null default 'not_checked';
update public.reviewed_claims c
set bilingual_consistency_status = 'passed'
where c.lifecycle = 'published' and c.statement_hi is not null
  and exists (
    select 1 from public.claim_reviews r
    where r.claim_id = c.id and r.reviewer_role = 'bilingual_reviewer' and r.decision = 'approve'
  );
alter table public.reviewed_claims
  drop constraint if exists reviewed_claims_bilingual_consistency_check;
alter table public.reviewed_claims add constraint reviewed_claims_bilingual_consistency_check check (
  bilingual_consistency_status in ('not_checked', 'passed', 'failed')
  and (statement_hi is null or lifecycle <> 'published' or bilingual_consistency_status = 'passed')
);

create table if not exists public.bilingual_glossary_terms (
  id uuid primary key default gen_random_uuid(),
  term_en text not null check (char_length(btrim(term_en)) between 1 and 240),
  term_hi text not null check (char_length(btrim(term_hi)) between 1 and 240),
  context_notes text,
  lifecycle text not null default 'draft' check (lifecycle in ('draft','in_review','published','superseded')),
  reviewer_user_id uuid references auth.users(id) on delete set null,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (term_en, term_hi),
  check (lifecycle <> 'published' or (reviewer_user_id is not null and reviewed_at is not null))
);
alter table public.bilingual_glossary_terms enable row level security;
create policy bilingual_glossary_published_read on public.bilingual_glossary_terms
  for select to authenticated using (lifecycle = 'published' or public.is_active_reviewer());
create policy bilingual_glossary_reviewer_write on public.bilingual_glossary_terms
  for all to authenticated using (public.is_active_reviewer('bilingual_reviewer'))
  with check (public.is_active_reviewer('bilingual_reviewer'));

create or replace function public.record_bilingual_consistency_review()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if new.reviewer_role = 'bilingual_reviewer' then
    update public.reviewed_claims
      set bilingual_consistency_status = case when new.decision = 'approve' then 'passed' else 'failed' end
      where id = new.claim_id and lifecycle <> 'published';
  end if;
  return new;
end;
$$;
drop trigger if exists claim_reviews_bilingual_consistency on public.claim_reviews;
create trigger claim_reviews_bilingual_consistency after insert on public.claim_reviews
for each row execute function public.record_bilingual_consistency_review();

comment on table public.bilingual_glossary_terms is
  'Approved English/Hindi statutory terminology. Empty until a bilingual reviewer publishes terms.';
