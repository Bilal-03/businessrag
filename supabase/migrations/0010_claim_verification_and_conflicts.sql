-- Strengthen claim-to-passage support and contradiction handling.
-- This is additive because 0008 may already be deployed in an environment.

drop policy if exists reviewer_assignments_admin_write on public.reviewer_assignments;
create policy reviewer_assignments_admin_write on public.reviewer_assignments
  for all to authenticated using (public.is_active_reviewer('catalog_admin')) with check (public.is_active_reviewer('catalog_admin'));

alter table public.reviewed_claims
  add column if not exists support_excerpt text,
  add column if not exists claim_value jsonb,
  add column if not exists search_terms text[] not null default '{}'::text[],
  add column if not exists approval_count integer;

alter table public.reviewed_claims
  drop constraint if exists reviewed_claims_support_excerpt_check,
  drop constraint if exists reviewed_claims_claim_value_check,
  drop constraint if exists reviewed_claims_verified_payload_check;
alter table public.reviewed_claims
  add constraint reviewed_claims_support_excerpt_check check (
    support_excerpt is null or char_length(btrim(support_excerpt)) between 5 and 1200
  ),
  add constraint reviewed_claims_claim_value_check check (
    claim_value is null or jsonb_typeof(claim_value) in ('string', 'number', 'boolean', 'object', 'array')
  ),
  add constraint reviewed_claims_verified_payload_check check (
    lifecycle <> 'published' or (support_excerpt is not null and claim_value is not null)
  ),
  add constraint reviewed_claims_approval_count_check check (
    approval_count is null or approval_count between 1 and 3
  );

alter table public.obligations
  add column if not exists primary_claim_id uuid references public.reviewed_claims(id) on delete restrict;

alter table public.obligation_due_date_rules
  add column if not exists supporting_claim_id uuid references public.reviewed_claims(id) on delete restrict;
alter table public.obligation_evidence_items
  add column if not exists supporting_claim_id uuid references public.reviewed_claims(id) on delete restrict;

alter table public.obligations
  drop constraint if exists obligations_primary_claim_publish_check;
alter table public.obligations add constraint obligations_primary_claim_publish_check
  check (not published or primary_claim_id is not null);
alter table public.obligation_due_date_rules
  drop constraint if exists obligation_due_date_claim_publish_check;
alter table public.obligation_due_date_rules add constraint obligation_due_date_claim_publish_check
  check (lifecycle <> 'published' or supporting_claim_id is not null);
alter table public.obligation_evidence_items
  drop constraint if exists obligation_evidence_claim_publish_check;
alter table public.obligation_evidence_items add constraint obligation_evidence_claim_publish_check
  check (lifecycle <> 'published' or supporting_claim_id is not null);

create index if not exists reviewed_claims_search_terms_idx
  on public.reviewed_claims using gin(search_terms);

create table if not exists public.claim_conflicts (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.reviewed_claims(id) on delete restrict,
  conflicting_claim_id uuid not null references public.reviewed_claims(id) on delete restrict,
  detected_at timestamptz not null default now(),
  resolution_status text not null default 'open' check (resolution_status in ('open', 'resolved', 'not_a_conflict')),
  resolved_by uuid references auth.users(id) on delete set null,
  resolved_at timestamptz,
  resolution_notes text,
  unique (claim_id, conflicting_claim_id),
  check (claim_id::text < conflicting_claim_id::text),
  check (claim_id <> conflicting_claim_id),
  check (resolution_status = 'open' or (resolved_by is not null and resolved_at is not null and char_length(btrim(resolution_notes)) > 0))
);

alter table public.claim_conflicts enable row level security;
drop policy if exists claim_conflicts_reviewer_access on public.claim_conflicts;
create policy claim_conflicts_reviewer_access on public.claim_conflicts
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
drop policy if exists claim_conflicts_published_read on public.claim_conflicts;
create policy claim_conflicts_published_read on public.claim_conflicts
  for select to authenticated using (
    exists (
      select 1 from public.reviewed_claims c
      where c.id in (claim_id, conflicting_claim_id)
        and c.lifecycle = 'published' and c.current and not c.kill_switch
    )
  );

create or replace function public.detect_claim_conflicts()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.claim_conflicts(claim_id, conflicting_claim_id)
  select least(new.id::text, other.id::text)::uuid,
         greatest(new.id::text, other.id::text)::uuid
  from public.reviewed_claims other
  where other.id <> new.id
    and other.claim_key = new.claim_key
    and other.jurisdiction = new.jurisdiction
    and other.applicability_rule = new.applicability_rule
    and other.current and new.current
    and other.lifecycle not in ('rejected', 'superseded', 'quarantined')
    and new.lifecycle not in ('rejected', 'superseded', 'quarantined')
    and other.claim_value is distinct from new.claim_value
    and daterange(other.effective_from, coalesce(other.effective_to, 'infinity'::date), '[]')
        && daterange(new.effective_from, coalesce(new.effective_to, 'infinity'::date), '[]')
  on conflict (claim_id, conflicting_claim_id) do nothing;
  return new;
end;
$$;
drop trigger if exists reviewed_claims_detect_conflicts on public.reviewed_claims;
create trigger reviewed_claims_detect_conflicts after insert or update of claim_key, claim_value, effective_from, effective_to, lifecycle, current
on public.reviewed_claims for each row execute function public.detect_claim_conflicts();

create or replace function public.enforce_claim_publication()
returns trigger language plpgsql security invoker set search_path = public as $$
declare
  approval_count integer;
  has_required_role boolean;
  has_bilingual_role boolean;
  source_ok boolean;
begin
  if tg_op = 'UPDATE' and old.lifecycle = 'published' and new.lifecycle = 'published' and (
      old.claim_key is distinct from new.claim_key
      or old.jurisdiction is distinct from new.jurisdiction
      or old.claim_type is distinct from new.claim_type
      or old.statement_en is distinct from new.statement_en
      or old.statement_hi is distinct from new.statement_hi
      or old.support_excerpt is distinct from new.support_excerpt
      or old.claim_value is distinct from new.claim_value
      or old.search_terms is distinct from new.search_terms
      or old.risk_level is distinct from new.risk_level
      or old.required_reviewer_role is distinct from new.required_reviewer_role
      or old.required_approvals is distinct from new.required_approvals
      or old.source_passage_id is distinct from new.source_passage_id
      or old.applicability_version is distinct from new.applicability_version
      or old.applicability_rule is distinct from new.applicability_rule
      or old.effective_from is distinct from new.effective_from
      or old.effective_to is distinct from new.effective_to
      or old.revalidate_by is distinct from new.revalidate_by
    ) then
    raise exception 'Published claim evidence is immutable; supersede it with a new claim version';
  end if;
  if new.lifecycle = 'published' and (tg_op = 'INSERT' or old.lifecycle is distinct from 'published') then
    if not public.is_active_reviewer('catalog_admin') then
      raise exception 'Only an active catalog admin can publish a claim';
    end if;
    select count(distinct reviewer_user_id),
           bool_or(reviewer_role = new.required_reviewer_role),
           bool_or(reviewer_role = 'bilingual_reviewer')
      into approval_count, has_required_role, has_bilingual_role
    from public.claim_reviews
    where claim_id = new.id and decision = 'approve';

    select exists (
      select 1 from public.source_passages p
      join public.source_versions v on v.id = p.source_version_id
      join public.source_documents d on d.id = v.source_document_id
      where p.id = new.source_passage_id
        and v.review_status = 'approved' and v.fetch_status = 'healthy'
        and d.active and d.source_tier <= 3 and v.last_checked_at >= now() - interval '90 days'
        and d.canonical_url ~* '^https://([^/]+\.)?(gov\.in|nic\.in|org\.in)(/|$)'
        and position(lower(btrim(new.support_excerpt)) in lower(p.passage_text)) > 0
    ) into source_ok;

    if not source_ok or new.revalidate_by < current_date or new.kill_switch then
      raise exception 'Claim source is not current, approved, healthy, and textually supporting';
    end if;
    if approval_count < greatest(new.required_approvals, case when new.risk_level in ('high', 'critical') or new.claim_type in ('deadline','rate','threshold','penalty','eligibility') then 2 else 1 end)
       or not coalesce(has_required_role, false) then
      raise exception 'Claim lacks required qualified approvals';
    end if;
    if new.statement_hi is not null and not coalesce(has_bilingual_role, false) then
      raise exception 'Hindi claim text requires bilingual reviewer approval';
    end if;
    if exists (
      select 1 from public.reviewed_claims other
      where other.id <> new.id and other.claim_key = new.claim_key
        and other.jurisdiction = new.jurisdiction
        and other.applicability_rule = new.applicability_rule
        and other.lifecycle = 'published' and other.current and not other.kill_switch
        and other.claim_value is distinct from new.claim_value
        and daterange(other.effective_from, coalesce(other.effective_to, 'infinity'::date), '[]')
            && daterange(new.effective_from, coalesce(new.effective_to, 'infinity'::date), '[]')
    ) then
      raise exception 'Claim contradicts an active published claim';
    end if;
    if exists (
      select 1 from public.claim_conflicts cc
      where cc.resolution_status = 'open'
        and (cc.claim_id = new.id or cc.conflicting_claim_id = new.id)
    ) then
      raise exception 'Claim has an unresolved contradiction';
    end if;
    select coalesce(array_agg(distinct reviewer_role order by reviewer_role), '{}'::text[])
      into new.reviewer_roles from public.claim_reviews where claim_id = new.id and decision = 'approve';
    new.approval_count = approval_count;
    new.published_at = now();
  end if;
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.enforce_obligation_publication()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if new.published and (tg_op = 'INSERT' or not old.published) then
    if not public.is_active_reviewer('catalog_admin') then
      raise exception 'Only an active catalog admin can publish an obligation';
    end if;
    if not exists (
      select 1 from public.reviewed_claims c
      where c.id = new.primary_claim_id and c.obligation_id = new.id
        and c.lifecycle = 'published' and c.current and not c.kill_switch
        and c.revalidate_by >= current_date
    ) then
      raise exception 'Obligation publication requires its active primary reviewed claim';
    end if;
  end if;
  return new;
end;
$$;

comment on table public.claim_conflicts is 'Reviewer-resolved contradictions; open conflicts suppress publication and retrieval.';
