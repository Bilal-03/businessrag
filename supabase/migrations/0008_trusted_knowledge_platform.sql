-- Evidence-first knowledge, review, reminders, and audit platform.
-- This migration creates publication gates; it deliberately does not publish
-- legal claims. Qualified reviewers must approve records through the review
-- workflow before chat can use them.

create table if not exists public.reviewer_assignments (
  reviewer_user_id uuid not null references auth.users(id) on delete cascade,
  reviewer_role text not null check (reviewer_role in ('CA', 'CS', 'lawyer', 'sector_specialist', 'bilingual_reviewer', 'catalog_admin')),
  active boolean not null default true,
  assigned_by uuid references auth.users(id) on delete set null,
  assigned_at timestamptz not null default now(),
  primary key (reviewer_user_id, reviewer_role)
);

alter table public.business_compliance_profiles
  drop constraint if exists business_compliance_profiles_profile_version_check;
alter table public.business_compliance_profiles
  add column if not exists gst_scheme text check (gst_scheme is null or gst_scheme in ('regular','composition','qrmp','not_known','not_applicable')),
  add column if not exists incorporation_stage text check (incorporation_stage is null or incorporation_stage in ('pre_incorporation','incorporated','operating','winding_down')),
  add column if not exists premises_status text check (premises_status is null or premises_status in ('none','owned','leased','shared','virtual')),
  add column if not exists uses_contractors boolean,
  add column if not exists handles_personal_data boolean,
  add column if not exists operating_state_codes text[];
alter table public.business_compliance_profiles
  add column if not exists date_answers jsonb not null default '{}'::jsonb check (jsonb_typeof(date_answers) = 'object');
update public.business_compliance_profiles set profile_version = 2 where profile_version <> 2;
alter table public.business_compliance_profiles alter column profile_version set default 2;
alter table public.business_compliance_profiles add constraint business_compliance_profiles_profile_version_check check (profile_version = 2);

alter table public.obligations drop constraint if exists obligations_published_applicability_check;
update public.obligations set applicability_version = 2 where applicability_version = 1;
alter table public.obligations add constraint obligations_published_applicability_check check (
  not published or (applicability_version = 2 and applicability_rule is not null and jsonb_typeof(applicability_rule) = 'object')
);

create table if not exists public.business_compliance_profile_versions (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  profile_version integer not null,
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  recorded_at timestamptz not null default now(),
  foreign key (business_id, owner_id) references public.businesses(id, owner_id) on delete cascade
);
create index if not exists business_profile_versions_history_idx on public.business_compliance_profile_versions(business_id, recorded_at desc);

create or replace function public.record_compliance_profile_version()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.business_compliance_profile_versions(business_id, owner_id, profile_version, snapshot)
  values (new.business_id, new.owner_id, new.profile_version, to_jsonb(new) - 'created_at' - 'updated_at');
  return new;
end;
$$;
drop trigger if exists business_profiles_record_version on public.business_compliance_profiles;
create trigger business_profiles_record_version after insert or update on public.business_compliance_profiles
for each row execute function public.record_compliance_profile_version();

create table if not exists public.source_documents (
  id uuid primary key default gen_random_uuid(),
  authority_name text not null check (char_length(btrim(authority_name)) between 2 and 240),
  jurisdiction text not null check (char_length(btrim(jurisdiction)) between 2 and 120),
  source_tier integer not null check (source_tier between 1 and 5),
  source_type text not null check (source_type in ('gazette', 'statute', 'rules', 'notification', 'circular', 'order', 'master_direction', 'form', 'official_guidance', 'official_faq', 'institutional_guidance')),
  canonical_url text not null unique check (canonical_url ~* '^https://'),
  title text not null check (char_length(btrim(title)) between 2 and 500),
  language text not null default 'en' check (language in ('en', 'hi', 'bilingual')),
  active boolean not null default true,
  monitoring_frequency text not null default 'weekly' check (monitoring_frequency in ('daily', 'weekly', 'monthly', 'manual')),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into storage.buckets (id, name, public, file_size_limit)
values ('compliance-sources', 'compliance-sources', false, 52428800)
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit;

create table if not exists public.source_versions (
  id uuid primary key default gen_random_uuid(),
  source_document_id uuid not null references public.source_documents(id) on delete restrict,
  version_label text not null check (char_length(btrim(version_label)) between 1 and 240),
  publication_date date,
  effective_from date,
  effective_to date,
  retrieved_at timestamptz not null,
  last_checked_at timestamptz not null,
  content_hash text not null check (content_hash ~ '^[a-f0-9]{64}$'),
  snapshot_path text not null check (char_length(btrim(snapshot_path)) between 1 and 1000),
  extracted_text text,
  fetch_status text not null check (fetch_status in ('healthy', 'changed', 'unavailable', 'error')),
  review_status text not null default 'draft' check (review_status in ('draft', 'in_review', 'approved', 'superseded', 'quarantined')),
  created_at timestamptz not null default now(),
  unique (source_document_id, content_hash),
  check (effective_to is null or effective_from is null or effective_to >= effective_from)
);

create table if not exists public.source_passages (
  id uuid primary key default gen_random_uuid(),
  source_version_id uuid not null references public.source_versions(id) on delete restrict,
  anchor text not null check (char_length(btrim(anchor)) between 1 and 500),
  heading text,
  page_number integer check (page_number is null or page_number > 0),
  passage_text text not null check (char_length(btrim(passage_text)) between 1 and 12000),
  content_hash text not null check (content_hash ~ '^[a-f0-9]{64}$'),
  created_at timestamptz not null default now(),
  unique (source_version_id, anchor, content_hash)
);

create table if not exists public.reviewed_claims (
  id uuid primary key default gen_random_uuid(),
  claim_key text not null check (claim_key ~ '^[a-z0-9][a-z0-9._-]{2,119}$'),
  obligation_id uuid references public.obligations(id) on delete set null,
  jurisdiction text not null check (char_length(btrim(jurisdiction)) between 2 and 120),
  claim_type text not null check (claim_type in ('duty', 'deadline', 'rate', 'threshold', 'penalty', 'eligibility', 'definition', 'procedure', 'exemption')),
  statement_en text not null check (char_length(btrim(statement_en)) between 1 and 4000),
  statement_hi text,
  risk_level text not null check (risk_level in ('low', 'medium', 'high', 'critical')),
  required_reviewer_role text not null check (required_reviewer_role in ('CA', 'CS', 'lawyer', 'sector_specialist')),
  required_approvals integer not null default 1 check (required_approvals between 1 and 3),
  source_passage_id uuid not null references public.source_passages(id) on delete restrict,
  applicability_version integer not null check (applicability_version > 0),
  applicability_rule jsonb not null check (jsonb_typeof(applicability_rule) = 'object'),
  effective_from date not null,
  effective_to date,
  revalidate_by date not null,
  lifecycle text not null default 'draft' check (lifecycle in ('draft', 'in_review', 'published', 'superseded', 'quarantined', 'rejected')),
  current boolean not null default true,
  reviewer_roles text[] not null default '{}'::text[],
  kill_switch boolean not null default false,
  supersedes_claim_id uuid references public.reviewed_claims(id) on delete set null,
  created_by uuid references auth.users(id) on delete set null,
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (effective_to is null or effective_to >= effective_from),
  check (statement_hi is null or char_length(btrim(statement_hi)) between 1 and 4000),
  check (lifecycle <> 'published' or (current and not kill_switch and published_at is not null))
);

create unique index if not exists reviewed_claims_one_current_published_idx
  on public.reviewed_claims(claim_key, jurisdiction)
  where lifecycle = 'published' and current and not kill_switch;
create index if not exists reviewed_claims_active_lookup_idx
  on public.reviewed_claims(lifecycle, current, jurisdiction, effective_from, effective_to, revalidate_by);

create table if not exists public.claim_reviews (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.reviewed_claims(id) on delete restrict,
  reviewer_user_id uuid not null references auth.users(id) on delete restrict,
  reviewer_role text not null check (reviewer_role in ('CA', 'CS', 'lawyer', 'sector_specialist', 'bilingual_reviewer')),
  decision text not null check (decision in ('approve', 'reject', 'request_changes')),
  comments text not null check (char_length(btrim(comments)) between 1 and 4000),
  reviewed_at timestamptz not null default now(),
  unique (claim_id, reviewer_user_id, reviewer_role)
);

create table if not exists public.review_events (
  id bigint generated always as identity primary key,
  actor_id uuid references auth.users(id) on delete set null,
  entity_type text not null check (entity_type in ('source_version', 'claim', 'coverage')),
  entity_id uuid not null,
  action text not null check (action in ('created', 'submitted', 'approved', 'changes_requested', 'rejected', 'published', 'superseded', 'quarantined', 'rolled_back')),
  from_state text,
  to_state text,
  reason text,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now()
);

create table if not exists public.source_change_events (
  id uuid primary key default gen_random_uuid(),
  source_document_id uuid not null references public.source_documents(id) on delete restrict,
  previous_version_id uuid references public.source_versions(id) on delete restrict,
  observed_hash text,
  event_type text not null check (event_type in ('content_changed', 'unavailable', 'restored', 'link_error')),
  severity text not null check (severity in ('low', 'medium', 'high', 'critical')),
  detected_at timestamptz not null default now(),
  resolution_status text not null default 'open' check (resolution_status in ('open', 'triaged', 'resolved', 'ignored')),
  assigned_to uuid references auth.users(id) on delete set null,
  details jsonb not null default '{}'::jsonb check (jsonb_typeof(details) = 'object'),
  resolved_at timestamptz
);

create table if not exists public.compliance_coverage_cells (
  id uuid primary key default gen_random_uuid(),
  jurisdiction text not null,
  industry_code text not null check (industry_code in (
    'food_beverage', 'technology_it', 'healthcare', 'education', 'manufacturing',
    'retail_ecommerce', 'consulting_services', 'real_estate', 'finance', 'other'
  )),
  module_code text not null,
  activity_code text not null default 'common',
  status text not null check (status in ('covered', 'not_applicable', 'blocked', 'in_review')),
  reviewer_user_id uuid references auth.users(id) on delete set null,
  reviewed_at timestamptz,
  notes text not null,
  updated_at timestamptz not null default now(),
  unique (jurisdiction, industry_code, module_code, activity_code),
  check (status not in ('covered', 'not_applicable') or (reviewer_user_id is not null and reviewed_at is not null))
);

create table if not exists public.obligation_due_date_rules (
  id uuid primary key default gen_random_uuid(),
  obligation_id uuid not null references public.obligations(id) on delete restrict,
  rule_version integer not null check (rule_version > 0),
  formula jsonb not null check (jsonb_typeof(formula) = 'object'),
  required_input_keys text[] not null default '{}'::text[],
  source_passage_id uuid not null references public.source_passages(id) on delete restrict,
  lifecycle text not null default 'draft' check (lifecycle in ('draft','in_review','published','superseded','quarantined')),
  revalidate_by date not null,
  current boolean not null default true,
  created_at timestamptz not null default now(),
  unique (obligation_id, rule_version)
);

create table if not exists public.obligation_evidence_items (
  id uuid primary key default gen_random_uuid(),
  obligation_id uuid not null references public.obligations(id) on delete restrict,
  label text not null check (char_length(btrim(label)) between 1 and 240),
  description text,
  required boolean not null default true,
  source_passage_id uuid references public.source_passages(id) on delete restrict,
  lifecycle text not null default 'draft' check (lifecycle in ('draft','in_review','published','superseded','quarantined')),
  revalidate_by date not null,
  current boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.answer_feedback (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  conversation_id uuid,
  message_id uuid,
  rating text not null check (rating in ('helpful', 'not_helpful', 'report')),
  reason_code text check (reason_code is null or reason_code in ('incorrect', 'outdated', 'citation_problem', 'applicability_problem', 'unsafe', 'other')),
  comments text check (comments is null or char_length(comments) <= 4000),
  answer_status text not null check (answer_status in ('verified', 'partially_supported', 'general_guidance', 'cannot_verify')),
  evidence_ids text[] not null default '{}'::text[],
  created_at timestamptz not null default now(),
  foreign key (conversation_id, owner_id) references public.conversations(id, owner_id) on delete cascade,
  foreign key (message_id, owner_id) references public.messages(id, owner_id) on delete cascade
);

alter table public.tasks
  add constraint tasks_id_owner_unique unique (id, owner_id);

create table if not exists public.reminders (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  business_id uuid not null,
  task_id uuid,
  title text not null check (char_length(btrim(title)) between 1 and 240),
  remind_at timestamptz not null,
  timezone text not null check (char_length(btrim(timezone)) between 1 and 100),
  status text not null default 'scheduled' check (status in ('scheduled', 'snoozed', 'delivered', 'dismissed')),
  alert_offsets_days integer[] not null default array[30,14,7,1],
  recurrence_rule jsonb check (recurrence_rule is null or jsonb_typeof(recurrence_rule) = 'object'),
  snoozed_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (business_id, owner_id) references public.businesses(id, owner_id) on delete cascade,
  foreign key (task_id, owner_id) references public.tasks(id, owner_id) on delete cascade,
  check (task_id is not null or business_id is not null)
);
create index if not exists reminders_owner_due_idx on public.reminders(owner_id, status, remind_at);

create table if not exists public.reminder_events (
  id bigint generated always as identity primary key,
  reminder_id uuid not null references public.reminders(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  event_type text not null check (event_type in ('created', 'snoozed', 'delivered', 'dismissed', 'rescheduled')),
  event_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object')
);

create table if not exists public.task_evidence (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  business_id uuid not null,
  task_id uuid not null,
  document_id uuid,
  evidence_type text not null check (evidence_type in ('document', 'reference', 'note')),
  title text not null check (char_length(btrim(title)) between 1 and 240),
  reference_url text check (reference_url is null or reference_url ~* '^https://'),
  note text check (note is null or char_length(note) <= 4000),
  created_at timestamptz not null default now(),
  foreign key (business_id, owner_id) references public.businesses(id, owner_id) on delete cascade,
  foreign key (task_id, owner_id) references public.tasks(id, owner_id) on delete cascade,
  foreign key (document_id, owner_id) references public.documents(id, owner_id) on delete set null
);

create table if not exists public.task_completion_events (
  id bigint generated always as identity primary key,
  task_id uuid not null references public.tasks(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  from_status text,
  to_status text not null,
  changed_at timestamptz not null default now()
);

alter table public.obligations
  add column if not exists due_date_rule jsonb,
  add column if not exists evidence_requirements jsonb not null default '[]'::jsonb,
  add column if not exists risk_level text not null default 'medium',
  add column if not exists revalidate_by date,
  add column if not exists kill_switch boolean not null default false;

alter table public.messages
  add column if not exists schema_version integer not null default 1,
  add column if not exists answer_mode text,
  add column if not exists evidence_status text,
  add column if not exists trust_metadata jsonb not null default '{}'::jsonb;

alter table public.messages
  drop constraint if exists messages_answer_mode_check,
  drop constraint if exists messages_evidence_status_check,
  drop constraint if exists messages_trust_metadata_check;
alter table public.messages
  add constraint messages_answer_mode_check check (answer_mode is null or answer_mode in ('reviewed_compliance','user_document_analysis','general_business_guidance','professional_escalation')),
  add constraint messages_evidence_status_check check (evidence_status is null or evidence_status in ('verified','partially_supported','general_guidance','cannot_verify')),
  add constraint messages_trust_metadata_check check (jsonb_typeof(trust_metadata) = 'object');

alter table public.obligations
  drop constraint if exists obligations_due_date_rule_check,
  drop constraint if exists obligations_evidence_requirements_check,
  drop constraint if exists obligations_risk_level_check;
alter table public.obligations
  add constraint obligations_due_date_rule_check check (due_date_rule is null or jsonb_typeof(due_date_rule) = 'object'),
  add constraint obligations_evidence_requirements_check check (jsonb_typeof(evidence_requirements) = 'array'),
  add constraint obligations_risk_level_check check (risk_level in ('low', 'medium', 'high', 'critical'));

create or replace function public.prevent_snapshot_mutation()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if old.source_document_id is distinct from new.source_document_id
     or old.content_hash is distinct from new.content_hash
     or old.snapshot_path is distinct from new.snapshot_path
     or old.extracted_text is distinct from new.extracted_text
     or old.retrieved_at is distinct from new.retrieved_at then
    raise exception 'Source snapshots are immutable';
  end if;
  return new;
end;
$$;
drop trigger if exists source_versions_immutable_snapshot on public.source_versions;
create trigger source_versions_immutable_snapshot before update on public.source_versions
for each row execute function public.prevent_snapshot_mutation();

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
        and d.active and v.last_checked_at >= now() - interval '90 days'
    ) into source_ok;

    if not source_ok or new.revalidate_by < current_date or new.kill_switch then
      raise exception 'Claim source is not current, approved, and healthy';
    end if;
    if approval_count < greatest(new.required_approvals, case when new.risk_level in ('high', 'critical') or new.claim_type in ('deadline','rate','threshold','penalty','eligibility') then 2 else 1 end)
       or not coalesce(has_required_role, false) then
      raise exception 'Claim lacks required qualified approvals';
    end if;
    if new.statement_hi is not null and not coalesce(has_bilingual_role, false) then
      raise exception 'Hindi claim text requires bilingual reviewer approval';
    end if;
    select coalesce(array_agg(distinct reviewer_role order by reviewer_role), '{}'::text[])
      into new.reviewer_roles from public.claim_reviews where claim_id = new.id and decision = 'approve';
    new.published_at = now();
  end if;
  new.updated_at = now();
  return new;
end;
$$;
drop trigger if exists reviewed_claims_publication_gate on public.reviewed_claims;
create trigger reviewed_claims_publication_gate before insert or update on public.reviewed_claims
for each row execute function public.enforce_claim_publication();

create or replace function public.enforce_source_version_approval()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if new.review_status = 'approved' and (tg_op = 'INSERT' or old.review_status is distinct from 'approved')
     and not public.is_active_reviewer('catalog_admin') then
    raise exception 'Only an active catalog admin can approve a source version';
  end if;
  return new;
end;
$$;
drop trigger if exists source_versions_approval_gate on public.source_versions;
create trigger source_versions_approval_gate before insert or update on public.source_versions
for each row execute function public.enforce_source_version_approval();

create or replace function public.prevent_evidence_mutation()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  raise exception 'Evidence and review records are append-only';
end;
$$;
drop trigger if exists source_passages_append_only on public.source_passages;
create trigger source_passages_append_only before update or delete on public.source_passages
for each row execute function public.prevent_evidence_mutation();
drop trigger if exists claim_reviews_append_only on public.claim_reviews;
create trigger claim_reviews_append_only before update or delete on public.claim_reviews
for each row execute function public.prevent_evidence_mutation();
drop trigger if exists review_events_append_only on public.review_events;
create trigger review_events_append_only before update or delete on public.review_events
for each row execute function public.prevent_evidence_mutation();
drop trigger if exists source_versions_no_delete on public.source_versions;
create trigger source_versions_no_delete before delete on public.source_versions
for each row execute function public.prevent_evidence_mutation();

create or replace function public.enforce_obligation_publication()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if new.published and (tg_op = 'INSERT' or not old.published) then
    if not public.is_active_reviewer('catalog_admin') then
      raise exception 'Only an active catalog admin can publish an obligation';
    end if;
    if not exists (
      select 1 from public.reviewed_claims c
      where c.obligation_id = new.id and c.lifecycle = 'published' and c.current
        and not c.kill_switch and c.revalidate_by >= current_date
    ) then
      raise exception 'Obligation publication requires an active reviewed claim';
    end if;
  end if;
  return new;
end;
$$;
drop trigger if exists obligations_qualified_publication_gate on public.obligations;
create trigger obligations_qualified_publication_gate before insert or update on public.obligations
for each row execute function public.enforce_obligation_publication();

create or replace function public.record_task_status_change()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if old.status is distinct from new.status then
    insert into public.task_completion_events(task_id, owner_id, from_status, to_status)
    values (new.id, new.owner_id, old.status, new.status);
  end if;
  return new;
end;
$$;
drop trigger if exists tasks_record_status_change on public.tasks;
create trigger tasks_record_status_change after update on public.tasks
for each row execute function public.record_task_status_change();

drop trigger if exists source_documents_set_updated_at on public.source_documents;
create trigger source_documents_set_updated_at before update on public.source_documents
for each row execute function public.set_updated_at();
drop trigger if exists reminders_set_updated_at on public.reminders;
create trigger reminders_set_updated_at before update on public.reminders
for each row execute function public.set_updated_at();

alter table public.reviewer_assignments enable row level security;
alter table public.business_compliance_profile_versions enable row level security;
alter table public.source_documents enable row level security;
alter table public.source_versions enable row level security;
alter table public.source_passages enable row level security;
alter table public.reviewed_claims enable row level security;
alter table public.claim_reviews enable row level security;
alter table public.review_events enable row level security;
alter table public.source_change_events enable row level security;
alter table public.compliance_coverage_cells enable row level security;
alter table public.obligation_due_date_rules enable row level security;
alter table public.obligation_evidence_items enable row level security;
alter table public.answer_feedback enable row level security;
alter table public.reminders enable row level security;
alter table public.reminder_events enable row level security;
alter table public.task_evidence enable row level security;
alter table public.task_completion_events enable row level security;

create or replace function public.is_active_reviewer(required_role text default null)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.reviewer_assignments
    where reviewer_user_id = auth.uid() and active
      and (required_role is null or reviewer_role in (required_role, 'catalog_admin'))
  );
$$;

create policy reviewer_assignments_self_read on public.reviewer_assignments
  for select to authenticated using (reviewer_user_id = auth.uid() or public.is_active_reviewer('catalog_admin'));
create policy business_profile_versions_owner_read on public.business_compliance_profile_versions
  for select to authenticated using (owner_id = auth.uid());
create policy source_documents_authenticated_read on public.source_documents
  for select to authenticated using (active or public.is_active_reviewer());
create policy source_documents_reviewer_write on public.source_documents
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
create policy source_versions_published_read on public.source_versions
  for select to authenticated using (review_status = 'approved' or public.is_active_reviewer());
create policy source_versions_reviewer_write on public.source_versions
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
create policy source_passages_published_read on public.source_passages
  for select to authenticated using (
    public.is_active_reviewer() or exists (
      select 1 from public.reviewed_claims c
      where c.source_passage_id = source_passages.id and c.lifecycle = 'published' and c.current and not c.kill_switch
    )
  );
create policy source_passages_reviewer_write on public.source_passages
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
create policy reviewed_claims_published_read on public.reviewed_claims
  for select to authenticated using ((lifecycle = 'published' and current and not kill_switch) or public.is_active_reviewer());
create policy reviewed_claims_reviewer_write on public.reviewed_claims
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
create policy claim_reviews_reviewer_access on public.claim_reviews
  for all to authenticated using (public.is_active_reviewer())
  with check (reviewer_user_id = auth.uid() and public.is_active_reviewer(reviewer_role));
create policy review_events_reviewer_read on public.review_events
  for select to authenticated using (public.is_active_reviewer());
create policy review_events_reviewer_insert on public.review_events
  for insert to authenticated with check (actor_id = auth.uid() and public.is_active_reviewer());
create policy source_change_events_reviewer_access on public.source_change_events
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
create policy coverage_cells_authenticated_read on public.compliance_coverage_cells
  for select to authenticated using (true);
create policy coverage_cells_reviewer_write on public.compliance_coverage_cells
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
create policy due_date_rules_active_read on public.obligation_due_date_rules
  for select to authenticated using ((lifecycle = 'published' and current and revalidate_by >= current_date) or public.is_active_reviewer());
create policy due_date_rules_reviewer_write on public.obligation_due_date_rules
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
create policy obligation_evidence_active_read on public.obligation_evidence_items
  for select to authenticated using ((lifecycle = 'published' and current and revalidate_by >= current_date) or public.is_active_reviewer());
create policy obligation_evidence_reviewer_write on public.obligation_evidence_items
  for all to authenticated using (public.is_active_reviewer()) with check (public.is_active_reviewer());
create policy answer_feedback_owner_access on public.answer_feedback
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy reminders_owner_access on public.reminders
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy reminder_events_owner_read on public.reminder_events
  for select to authenticated using (owner_id = auth.uid());
create policy reminder_events_owner_insert on public.reminder_events
  for insert to authenticated with check (
    owner_id = auth.uid() and exists (
      select 1 from public.reminders r where r.id = reminder_events.reminder_id and r.owner_id = auth.uid()
    )
  );
create policy task_evidence_owner_access on public.task_evidence
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy task_completion_events_owner_read on public.task_completion_events
  for select to authenticated using (owner_id = auth.uid());

-- Existing obligation records must be revalidated every 90 days before they
-- remain eligible for a user-facing plan.
update public.obligations
set revalidate_by = reviewed_at::date + 90
where reviewed_at is not null and revalidate_by is null;

-- Legacy team-label reviews are not equivalent to the qualified, identified
-- review records introduced above. They remain research candidates but stop
-- supporting user-facing obligations until migrated and re-approved.
update public.obligations
set published = false,
    review_status = case when review_status = 'published' then 'reviewed' else review_status end,
    metadata = metadata || '{"publish_blocker":"qualified reviewer approval and active reviewed claim required"}'::jsonb
where published = true;

comment on table public.reviewed_claims is 'Atomic user-facing claims. Publication requires approved source evidence and qualified human reviews.';
comment on table public.review_events is 'Append-only reviewer audit history; end-user sessions cannot mutate it.';
comment on table public.reminders is 'Owner-scoped in-app reminders. External email/SMS delivery is intentionally out of scope.';
