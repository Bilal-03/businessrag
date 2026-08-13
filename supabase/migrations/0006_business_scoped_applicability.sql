-- Business-scoped, versioned compliance applicability.
-- Rollout order: this migration, reviewed rule seeds below, backend, frontend.

alter table public.businesses
  add column if not exists industry_code text;

update public.businesses
set industry_code = case industry
  when 'Food & Beverage' then 'food_beverage'
  when 'Technology/IT' then 'technology_it'
  when 'Healthcare' then 'healthcare'
  when 'Education' then 'education'
  when 'Manufacturing' then 'manufacturing'
  when 'Retail & E-Commerce' then 'retail_ecommerce'
  when 'Consulting/Services' then 'consulting_services'
  when 'Real Estate' then 'real_estate'
  when 'Finance' then 'finance'
  else 'other'
end
where industry_code is null;

alter table public.businesses
  alter column industry_code set default 'other',
  alter column industry_code set not null,
  drop constraint if exists businesses_industry_code_check;

alter table public.businesses
  add constraint businesses_industry_code_check check (industry_code in (
    'food_beverage', 'technology_it', 'healthcare', 'education', 'manufacturing',
    'retail_ecommerce', 'consulting_services', 'real_estate', 'finance', 'other'
  ));

create table if not exists public.business_compliance_profiles (
  business_id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  profile_version integer not null default 1 check (profile_version = 1),
  regulated_activities text[],
  gst_registration_status text check (gst_registration_status is null or gst_registration_status in ('registered', 'not_registered', 'not_applicable')),
  turnover_band text check (turnover_band is null or turnover_band in ('under_20_lakh', '20_lakh_to_1_crore', '1_to_5_crore', 'over_5_crore')),
  employee_count_band text check (employee_count_band is null or employee_count_band in ('0', '1_to_9', '10_to_19', '20_to_49', '50_to_99', '100_plus')),
  has_physical_establishment boolean,
  operates_multiple_states boolean,
  imports_goods_services boolean,
  exports_goods_services boolean,
  answers jsonb not null default '{}'::jsonb check (jsonb_typeof(answers) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (business_id, owner_id),
  foreign key (business_id, owner_id) references public.businesses(id, owner_id) on delete cascade
);

alter table public.business_compliance_profiles
  drop constraint if exists business_compliance_profiles_activities_check;
alter table public.business_compliance_profiles
  add constraint business_compliance_profiles_activities_check check (
    regulated_activities is null or regulated_activities <@ array[
      'food_handling', 'food_manufacturing', 'food_storage', 'food_import', 'food_delivery',
      'saas_digital_service', 'personal_data_processing', 'online_intermediary', 'ecommerce_marketplace',
      'clinical_establishment', 'pharmacy', 'diagnostics', 'medical_devices',
      'school_education', 'coaching_training', 'higher_education', 'online_education', 'awards_qualifications',
      'factory_operations', 'hazardous_process', 'pollution_generating', 'physical_retail',
      'packaged_goods_sale', 'professional_consulting', 'real_estate_promoter', 'real_estate_agent',
      'construction', 'lending', 'payments', 'investment_advice', 'insurance', 'pension'
    ]::text[]
  );

create or replace function public.create_business_compliance_profile()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  insert into public.business_compliance_profiles (business_id, owner_id)
  values (new.id, new.owner_id)
  on conflict (business_id) do nothing;
  return new;
end;
$$;

drop trigger if exists businesses_create_compliance_profile on public.businesses;
create trigger businesses_create_compliance_profile
after insert on public.businesses
for each row execute function public.create_business_compliance_profile();

insert into public.business_compliance_profiles (business_id, owner_id)
select id, owner_id from public.businesses
on conflict (business_id) do nothing;

drop trigger if exists business_compliance_profiles_set_updated_at on public.business_compliance_profiles;
create trigger business_compliance_profiles_set_updated_at
before update on public.business_compliance_profiles
for each row execute function public.set_updated_at();

alter table public.business_compliance_profiles enable row level security;
drop policy if exists business_compliance_profiles_owner_access on public.business_compliance_profiles;
create policy business_compliance_profiles_owner_access on public.business_compliance_profiles
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());

create index if not exists business_compliance_profiles_owner_idx
  on public.business_compliance_profiles(owner_id, updated_at desc);

alter table public.obligations
  add column if not exists applicability_version integer,
  add column if not exists applicability_rule jsonb;

-- Published records receive narrowly scoped, deterministic rules. An absent,
-- malformed, or unsupported rule is rejected by both the API and import validator.
update public.obligations
set applicability_version = 1,
    applicability_rule = '{"field":"regulated_activities","op":"contains_any","value":["food_handling","food_manufacturing","food_storage","food_import","food_delivery"]}'::jsonb
where id = 'a1010000-0000-4000-8000-000000000001';

update public.obligations
set applicability_version = 1,
    applicability_rule = '{"field":"gst_registration_status","op":"eq","value":"registered"}'::jsonb
where id = 'a1010000-0000-4000-8000-000000000002';

update public.obligations
set applicability_version = 1,
    applicability_rule = '{"field":"has_physical_establishment","op":"eq","value":true}'::jsonb
where id in (
  'a1010000-0000-4000-8000-000000000003',
  'a1010000-0000-4000-8000-000000000004'
);

-- Any other legacy publication lacks a reviewed applicability rule and is
-- deliberately unpublished rather than treated as universal.
update public.obligations
set published = false,
    review_status = case when review_status = 'published' then 'reviewed' else review_status end
where published = true
  and (applicability_version is distinct from 1 or applicability_rule is null);

alter table public.obligations
  drop constraint if exists obligations_published_applicability_check;
alter table public.obligations
  add constraint obligations_published_applicability_check check (
    not published or (
      applicability_version = 1
      and applicability_rule is not null
      and jsonb_typeof(applicability_rule) = 'object'
    )
  );

comment on column public.businesses.industry_code is
  'Stable primary-industry code; display labels remain in the industry column.';
comment on table public.business_compliance_profiles is
  'Versioned, owner-scoped answers used only by deterministic applicability rules.';
comment on column public.obligations.applicability_rule is
  'Constrained declarative all/any/not rule; never executable code or AI output.';
