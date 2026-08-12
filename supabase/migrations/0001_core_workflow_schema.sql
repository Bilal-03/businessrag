-- BizGuide core workflow schema
-- Apply through the Supabase migration runner before enabling the normalized
-- application persistence path. Existing user_data rows are retained for the
-- one-time cutover and rollback window; they are not the new source of truth.

create extension if not exists pgcrypto;

create table if not exists public.businesses (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  legal_name text not null check (char_length(legal_name) between 1 and 200),
  entity_type text not null check (char_length(entity_type) between 1 and 80),
  industry text check (industry is null or char_length(industry) <= 120),
  state_code text check (state_code is null or state_code ~ '^[A-Z]{2,8}$'),
  status text not null default 'planning' check (status in ('planning', 'registered', 'operating', 'on_hold')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, owner_id)
);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  business_id uuid,
  file_name text not null check (char_length(file_name) between 1 and 255),
  mime_type text not null default 'application/pdf',
  byte_size bigint check (byte_size is null or byte_size between 1 and 52428800),
  sha256 text check (sha256 is null or sha256 ~ '^[a-f0-9]{64}$'),
  storage_path text,
  status text not null default 'uploaded' check (status in ('uploaded', 'processing', 'indexed', 'failed', 'deleted')),
  error_code text,
  created_at timestamptz not null default now(),
  indexed_at timestamptz,
  unique (id, owner_id),
  foreign key (business_id, owner_id) references public.businesses(id, owner_id) on delete cascade
);

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  business_id uuid,
  title text not null default 'New conversation' check (char_length(title) between 1 and 200),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz,
  unique (id, owner_id),
  foreign key (business_id, owner_id) references public.businesses(id, owner_id) on delete cascade
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  conversation_id uuid not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null check (char_length(content) between 1 and 30000),
  agent_type text,
  grounding text not null default 'general' check (grounding in ('document', 'mixed', 'general', 'insufficient')),
  client_message_id text,
  created_at timestamptz not null default now(),
  unique (id, owner_id),
  unique (conversation_id, client_message_id),
  foreign key (conversation_id, owner_id) references public.conversations(id, owner_id) on delete cascade
);

create table if not exists public.message_sources (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  message_id uuid not null,
  document_id uuid not null,
  page_number integer check (page_number is null or page_number > 0),
  snippet text not null check (char_length(snippet) between 1 and 1200),
  score numeric(6,5) check (score is null or score between -1 and 1),
  created_at timestamptz not null default now(),
  foreign key (message_id, owner_id) references public.messages(id, owner_id) on delete cascade,
  foreign key (document_id, owner_id) references public.documents(id, owner_id) on delete cascade
);

create table if not exists public.obligations (
  id uuid primary key default gen_random_uuid(),
  jurisdiction text not null check (char_length(jurisdiction) between 2 and 120),
  title text not null check (char_length(title) between 1 and 240),
  description text not null,
  source_url text not null,
  source_version text not null,
  effective_from date,
  effective_to date,
  published boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (effective_to is null or effective_from is null or effective_to >= effective_from)
);

create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  business_id uuid not null,
  obligation_id uuid references public.obligations(id) on delete restrict,
  title text not null check (char_length(title) between 1 and 240),
  status text not null default 'todo' check (status in ('todo', 'in_progress', 'blocked', 'done', 'dismissed')),
  due_date date,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (business_id, owner_id) references public.businesses(id, owner_id) on delete cascade
);

create index if not exists businesses_owner_updated_idx on public.businesses(owner_id, updated_at desc);
create index if not exists documents_owner_created_idx on public.documents(owner_id, created_at desc);
create index if not exists conversations_owner_updated_idx on public.conversations(owner_id, updated_at desc);
create index if not exists messages_conversation_created_idx on public.messages(conversation_id, created_at);
create index if not exists tasks_business_status_due_idx on public.tasks(business_id, status, due_date);
create index if not exists obligations_jurisdiction_effective_idx on public.obligations(jurisdiction, effective_from, effective_to);
create index if not exists obligations_published_jurisdiction_idx on public.obligations(published, jurisdiction, effective_from);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists businesses_set_updated_at on public.businesses;
create trigger businesses_set_updated_at before update on public.businesses
for each row execute function public.set_updated_at();

drop trigger if exists conversations_set_updated_at on public.conversations;
create trigger conversations_set_updated_at before update on public.conversations
for each row execute function public.set_updated_at();

drop trigger if exists obligations_set_updated_at on public.obligations;
create trigger obligations_set_updated_at before update on public.obligations
for each row execute function public.set_updated_at();

drop trigger if exists tasks_set_updated_at on public.tasks;
create trigger tasks_set_updated_at before update on public.tasks
for each row execute function public.set_updated_at();

alter table public.businesses enable row level security;
alter table public.documents enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.message_sources enable row level security;
alter table public.obligations enable row level security;
alter table public.tasks enable row level security;

create policy businesses_owner_access on public.businesses
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy documents_owner_access on public.documents
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy conversations_owner_access on public.conversations
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy messages_owner_access on public.messages
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy message_sources_owner_access on public.message_sources
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy obligations_authenticated_read on public.obligations
  for select to authenticated using (true);
create policy tasks_owner_access on public.tasks
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
