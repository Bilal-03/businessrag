-- Prevent duplicate delivery of the same reminder alert window.

alter table public.reminders
  drop constraint if exists reminders_alert_offsets_check;
alter table public.reminders add constraint reminders_alert_offsets_check check (
  cardinality(alert_offsets_days) between 1 and 12
  and 0 <= all(alert_offsets_days)
  and 365 >= all(alert_offsets_days)
);

create unique index if not exists reminder_events_unique_delivery_offset
  on public.reminder_events(reminder_id, ((metadata->>'alert_offset_days')::integer))
  where event_type = 'delivered' and metadata ? 'alert_offset_days';

comment on index public.reminder_events_unique_delivery_offset is
  'Each configured alert offset may be delivered at most once per reminder.';
