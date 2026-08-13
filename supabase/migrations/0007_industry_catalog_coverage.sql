-- Explicit catalog coverage map for the ten supported primary industries.
-- "partial" means routing and review workflow exist, not that every legal
-- requirement has been published. Only obligation rows with a published
-- lifecycle state and valid applicability rule can enter a user plan.

create table if not exists public.compliance_catalog_coverage (
  industry_code text not null,
  jurisdiction text not null,
  status text not null check (status in ('available', 'partial', 'in_review', 'unsupported')),
  notes text not null,
  source_families jsonb not null default '[]'::jsonb check (jsonb_typeof(source_families) = 'array'),
  reviewed_at timestamptz,
  review_owner text,
  updated_at timestamptz not null default now(),
  primary key (industry_code, jurisdiction),
  check (industry_code in (
    'food_beverage', 'technology_it', 'healthcare', 'education', 'manufacturing',
    'retail_ecommerce', 'consulting_services', 'real_estate', 'finance', 'other'
  ))
);

insert into public.compliance_catalog_coverage (
  industry_code, jurisdiction, status, notes, source_families, reviewed_at, review_owner
)
values
  ('food_beverage', 'India', 'partial', 'Food activity routing is live; only human-reviewed published rows are shown.', '["https://fssai.gov.in/cms/licensing.php"]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('technology_it', 'India', 'partial', 'Technology activity routing is live; MeitY source candidates require record-level domain approval.', '["https://www.meity.gov.in/documents/act-and-policies"]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('healthcare', 'India', 'partial', 'Healthcare activity routing is live; sector records remain unpublished until domain review.', '[]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('education', 'India', 'partial', 'Education activity routing is live; UGC and sector records require record-level domain approval.', '["https://www.ugc.gov.in/regulations"]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('manufacturing', 'India', 'partial', 'Factory, workforce, hazardous-process, and consent routing is live; record coverage is incomplete.', '["https://www.labour.gov.in/offerings/schemes-and-services/details/labour-codes-gzNzQzMtQWa"]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('retail_ecommerce', 'India', 'partial', 'Retail, marketplace, packaged-goods, and food-sale routing is live; record coverage is incomplete.', '[]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('consulting_services', 'India', 'partial', 'Common entity, tax, employment, and professional-activity routing is live; record coverage is incomplete.', '["https://www.labour.gov.in/offerings/schemes-and-services/details/labour-codes-gzNzQzMtQWa"]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('real_estate', 'India', 'partial', 'Promoter, project, broker, and construction routing is live; record coverage is incomplete.', '[]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('finance', 'India', 'partial', 'Lending, payments, investment, insurance, pension, and advisory routing is live; record coverage is incomplete.', '[]', '2026-08-13T00:00:00Z', 'catalog-governance-review'),
  ('other', 'India', 'partial', 'Common requirements and explicitly selected regulated activities are routed; record coverage is incomplete.', '[]', '2026-08-13T00:00:00Z', 'catalog-governance-review')
on conflict (industry_code, jurisdiction) do update set
  status = excluded.status,
  notes = excluded.notes,
  source_families = excluded.source_families,
  reviewed_at = excluded.reviewed_at,
  review_owner = excluded.review_owner,
  updated_at = now();

alter table public.compliance_catalog_coverage enable row level security;
drop policy if exists compliance_catalog_coverage_authenticated_read on public.compliance_catalog_coverage;
create policy compliance_catalog_coverage_authenticated_read on public.compliance_catalog_coverage
  for select to authenticated using (true);

comment on table public.compliance_catalog_coverage is
  'Human-governed coverage declaration. Partial coverage must be disclosed and must never trigger guessed obligations.';
