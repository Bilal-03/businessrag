-- Asynchronous document ingestion queue and private source-object storage.
-- Apply after 0001 and 0002. Background workers use the server-only
-- SUPABASE_SERVICE_ROLE_KEY; the browser never receives that credential.

alter table public.documents
  add column if not exists processing_progress integer not null default 0,
  add column if not exists processing_stage text,
  add column if not exists error_message text;

alter table public.documents
  drop constraint if exists documents_processing_progress_check;

alter table public.documents
  add constraint documents_processing_progress_check
  check (processing_progress between 0 and 100);

create table if not exists public.document_jobs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  document_id uuid not null,
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 120),
  status text not null default 'queued' check (status in ('queued', 'processing', 'indexed', 'failed')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  processing_progress integer not null default 0 check (processing_progress between 0 and 100),
  processing_stage text,
  last_error text,
  available_at timestamptz not null default now(),
  lease_expires_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, owner_id),
  unique (owner_id, idempotency_key),
  unique (document_id, owner_id),
  foreign key (document_id, owner_id) references public.documents(id, owner_id) on delete cascade
);

create index if not exists document_jobs_queue_idx
  on public.document_jobs(status, available_at, created_at);
create index if not exists document_jobs_owner_created_idx
  on public.document_jobs(owner_id, created_at desc);

drop trigger if exists document_jobs_set_updated_at on public.document_jobs;
create trigger document_jobs_set_updated_at before update on public.document_jobs
for each row execute function public.set_updated_at();

alter table public.document_jobs enable row level security;

drop policy if exists document_jobs_owner_access on public.document_jobs;
create policy document_jobs_owner_access on public.document_jobs
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());

-- The bucket is private. Object paths must begin with the authenticated
-- owner's UUID, preventing cross-tenant reads/writes through Storage RLS.
insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do update set public = false;

drop policy if exists documents_storage_insert on storage.objects;
create policy documents_storage_insert on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = (select auth.uid()::text)
  );

drop policy if exists documents_storage_read on storage.objects;
create policy documents_storage_read on storage.objects
  for select to authenticated
  using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = (select auth.uid()::text)
  );

drop policy if exists documents_storage_delete on storage.objects;
create policy documents_storage_delete on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = (select auth.uid()::text)
  );
