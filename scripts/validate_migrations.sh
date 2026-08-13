#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
validation_root="$(mktemp -d /tmp/bizguide-migrations.XXXXXX)"
socket_dir="$validation_root/socket"
data_dir="$validation_root/data"
port="${BIZGUIDE_TEST_PG_PORT:-55439}"
pg_bin="$(pg_config --bindir)"
mkdir -p "$socket_dir"

cleanup() {
  if [[ -f "$data_dir/postmaster.pid" ]]; then
    "$pg_bin/pg_ctl" -D "$data_dir" -m fast stop >/dev/null 2>&1 || true
  fi
  rm -rf "$validation_root"
}
trap cleanup EXIT

"$pg_bin/initdb" -D "$data_dir" -A trust >/dev/null
"$pg_bin/pg_ctl" -D "$data_dir" -l "$validation_root/postgres.log" -o "-k $socket_dir -p $port" start >/dev/null

psql_args=(-h "$socket_dir" -p "$port" -d postgres -v ON_ERROR_STOP=1 -X -q)
"$pg_bin/psql" "${psql_args[@]}" <<'SQL'
create role authenticated;
create role anon;
create role service_role;
create schema auth;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
create schema storage;
create table storage.buckets(id text primary key, name text, public boolean, file_size_limit bigint);
create table storage.objects(id uuid primary key default gen_random_uuid(), bucket_id text, name text);
create function storage.foldername(text) returns text[] language sql immutable as 'select string_to_array($1, ''/'')';
SQL

for migration in "$repo_root"/supabase/migrations/*.sql; do
  "$pg_bin/psql" "${psql_args[@]}" -f "$migration"
done

"$pg_bin/psql" "${psql_args[@]}" <<'SQL'
do $$
begin
  if (select count(*) from public.compliance_coverage_cells) <> 210 then
    raise exception 'Expected 210 launch coverage cells';
  end if;
  if exists (select 1 from public.obligations where published) then
    raise exception 'Legacy obligations remained published after trust migration';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'reviewed_claims'
      and column_name = 'support_excerpt'
  ) then
    raise exception 'Claim support evidence column is missing';
  end if;
end;
$$;

grant usage on schema public, auth to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to authenticated;

insert into auth.users(id) values
  ('10000000-0000-4000-8000-000000000001'),
  ('10000000-0000-4000-8000-000000000002');
insert into public.businesses(id, owner_id, legal_name, entity_type, industry_code, state_code) values
  ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'Tenant One', 'proprietorship', 'technology_it', 'DL'),
  ('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000002', 'Tenant Two', 'proprietorship', 'food_beverage', 'MH');
insert into public.documents(id, owner_id, business_id, file_name) values
  ('30000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 'one.pdf'),
  ('30000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000002', 'two.pdf');

set role authenticated;
set request.jwt.claim.sub = '10000000-0000-4000-8000-000000000001';
do $$
declare affected integer;
begin
  if (select count(*) from public.businesses) <> 1 then raise exception 'Business RLS leaked another tenant'; end if;
  if (select count(*) from public.business_compliance_profiles) <> 1 then raise exception 'Profile RLS leaked another tenant'; end if;
  if (select count(*) from public.documents) <> 1 then raise exception 'Document RLS leaked another tenant'; end if;
  update public.businesses set legal_name = 'Forbidden' where id = '20000000-0000-4000-8000-000000000002';
  get diagnostics affected = row_count;
  if affected <> 0 then raise exception 'Cross-tenant business update succeeded'; end if;
end;
$$;
reset role;
SQL

echo "Migration chain valid: schema, 210 blocked coverage cells, fail-closed legacy catalog, and tenant RLS isolation."
