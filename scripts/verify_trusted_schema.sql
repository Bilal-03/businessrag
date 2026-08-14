-- Read-only post-migration verification for Supabase SQL Editor.
-- This verifies the safety baseline. It does not approve or publish content.

do $$
declare
  coverage_count integer;
  malformed_published integer;
  malformed_claims integer;
  missing_rls text;
begin
  select count(*) into coverage_count
  from public.compliance_coverage_cells;

  if coverage_count < 210 then
    raise exception 'Expected at least 210 launch coverage cells; found %', coverage_count;
  end if;

  select count(*) into malformed_published
  from public.obligations o
  where o.published
    and (
      o.applicability_rule is null
      or jsonb_typeof(o.applicability_rule) <> 'object'
      or o.applicability_version is distinct from 2
      or o.primary_claim_id is null
    );

  if malformed_published > 0 then
    raise exception 'Found % published obligations without the trust publication contract', malformed_published;
  end if;

  select count(*) into malformed_claims
  from public.reviewed_claims c
  where c.lifecycle = 'published'
    and (
      c.support_excerpt is null
      or c.claim_value is null
      or c.source_passage_id is null
      or c.kill_switch
    );

  if malformed_claims > 0 then
    raise exception 'Found % malformed or kill-switched published claims', malformed_claims;
  end if;

  select string_agg(t.table_name, ', ' order by t.table_name)
    into missing_rls
  from (
    values
      ('businesses'),
      ('business_compliance_profiles'),
      ('business_compliance_profile_versions'),
      ('source_documents'),
      ('source_versions'),
      ('source_passages'),
      ('reviewed_claims'),
      ('claim_reviews'),
      ('compliance_coverage_cells'),
      ('reminders'),
      ('task_evidence')
  ) as t(table_name)
  left join pg_class c on c.relname = t.table_name
  left join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
  where c.relrowsecurity is distinct from true;

  if missing_rls is not null then
    raise exception 'RLS is not enabled on: %', missing_rls;
  end if;

  raise notice 'Trusted schema verification passed: % coverage cells; % published obligations; % published claims.',
    coverage_count,
    (select count(*) from public.obligations where published),
    (select count(*) from public.reviewed_claims where lifecycle = 'published');
end;
$$;

select 'coverage_cells' as check_name, count(*)::bigint as value
from public.compliance_coverage_cells
union all
select 'published_obligations', count(*)::bigint
from public.obligations
where published
union all
select 'published_claims', count(*)::bigint
from public.reviewed_claims
where lifecycle = 'published'
union all
select 'blocked_coverage_cells', count(*)::bigint
from public.compliance_coverage_cells
where status = 'blocked';
