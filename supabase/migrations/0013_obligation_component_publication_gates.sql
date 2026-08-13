-- Deadline formulas and evidence checklists can be user-facing claims too.
-- Require the same active reviewed evidence chain before publication.

create or replace function public.enforce_obligation_component_publication()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if tg_op = 'UPDATE' and old.lifecycle = 'published' and new.lifecycle = 'published' then
    raise exception 'Published obligation components are immutable; supersede them with a new version';
  end if;
  if new.lifecycle = 'published' and (tg_op = 'INSERT' or old.lifecycle is distinct from 'published') then
    if not public.is_active_reviewer('catalog_admin') then
      raise exception 'Only an active catalog admin can publish obligation components';
    end if;
    if not exists (
      select 1 from public.reviewed_claims c
      join public.source_passages p on p.id = c.source_passage_id
      join public.source_versions v on v.id = p.source_version_id
      join public.source_documents d on d.id = v.source_document_id
      where c.id = new.supporting_claim_id and c.obligation_id = new.obligation_id
        and c.lifecycle = 'published' and c.current and not c.kill_switch
        and c.revalidate_by >= current_date
        and v.review_status = 'approved' and v.fetch_status = 'healthy'
        and v.last_checked_at >= now() - interval '90 days' and d.active
        and (
          (tg_table_name = 'obligation_due_date_rules' and c.claim_type = 'deadline' and c.claim_value = to_jsonb(new)->'formula')
          or
          (tg_table_name = 'obligation_evidence_items' and c.claim_type in ('duty', 'procedure') and c.claim_value->>'evidence_label' = to_jsonb(new)->>'label')
        )
    ) then
      raise exception 'Published obligation component requires a current, verified supporting claim';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists obligation_due_date_rules_publication_gate on public.obligation_due_date_rules;
create trigger obligation_due_date_rules_publication_gate
before insert or update on public.obligation_due_date_rules
for each row execute function public.enforce_obligation_component_publication();

drop trigger if exists obligation_evidence_items_publication_gate on public.obligation_evidence_items;
create trigger obligation_evidence_items_publication_gate
before insert or update on public.obligation_evidence_items
for each row execute function public.enforce_obligation_component_publication();
