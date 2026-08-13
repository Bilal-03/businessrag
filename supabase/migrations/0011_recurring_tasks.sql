-- Deterministic recurring-task regeneration and immutable occurrence history.

alter table public.tasks
  add column if not exists recurrence_rule jsonb,
  add column if not exists series_id uuid,
  add column if not exists occurrence_number integer not null default 1;

alter table public.tasks
  drop constraint if exists tasks_recurrence_rule_check,
  drop constraint if exists tasks_occurrence_number_check;
alter table public.tasks
  add constraint tasks_recurrence_rule_check check (
    recurrence_rule is null or (
      jsonb_typeof(recurrence_rule) = 'object'
      and recurrence_rule ? 'frequency'
      and recurrence_rule->>'frequency' in ('monthly', 'quarterly', 'yearly')
      and (recurrence_rule - 'frequency') = '{}'::jsonb
    )
  ),
  add constraint tasks_occurrence_number_check check (occurrence_number > 0);

update public.tasks set series_id = id where series_id is null;
alter table public.tasks alter column series_id set not null;
create unique index if not exists tasks_series_occurrence_unique
  on public.tasks(series_id, occurrence_number);

create or replace function public.prepare_task_series()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if new.series_id is null then
    new.series_id = new.id;
  end if;
  return new;
end;
$$;
drop trigger if exists tasks_prepare_series on public.tasks;
create trigger tasks_prepare_series before insert on public.tasks
for each row execute function public.prepare_task_series();

create or replace function public.record_task_status_change()
returns trigger language plpgsql security definer set search_path = public as $$
declare
  next_due date;
begin
  if old.status is distinct from new.status then
    insert into public.task_completion_events(task_id, owner_id, from_status, to_status)
    values (new.id, new.owner_id, old.status, new.status);
  end if;

  if old.status is distinct from 'done' and new.status = 'done'
     and new.recurrence_rule is not null and new.due_date is not null then
    next_due := case new.recurrence_rule->>'frequency'
      when 'monthly' then (new.due_date + interval '1 month')::date
      when 'quarterly' then (new.due_date + interval '3 months')::date
      when 'yearly' then (new.due_date + interval '1 year')::date
    end;
    insert into public.tasks(
      owner_id, business_id, obligation_id, title, status, due_date,
      recurrence_rule, series_id, occurrence_number
    ) values (
      new.owner_id, new.business_id, new.obligation_id, new.title, 'todo', next_due,
      new.recurrence_rule, new.series_id, new.occurrence_number + 1
    ) on conflict (series_id, occurrence_number) do nothing;
  end if;
  return new;
end;
$$;

comment on column public.tasks.recurrence_rule is 'Reviewed/user-confirmed task recurrence; completion creates exactly one next occurrence.';
