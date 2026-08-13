-- Authoritative source-family candidates. These are discovery/monitoring
-- records only: inserting a registry row never publishes a claim.

insert into public.source_documents (
  id, authority_name, jurisdiction, source_tier, source_type, canonical_url, title, monitoring_frequency, metadata
)
values
  ('b2010000-0000-4000-8000-000000000001', 'India Code', 'India', 1, 'statute', 'https://www.indiacode.nic.in/', 'India Code', 'daily', '{"launch_modules":["entity","tax","employment","sector"]}'),
  ('b2010000-0000-4000-8000-000000000002', 'eGazette of India', 'India', 1, 'gazette', 'https://egazette.nic.in/', 'eGazette of India', 'daily', '{"launch_modules":["all"]}'),
  ('b2010000-0000-4000-8000-000000000003', 'Ministry of Corporate Affairs', 'India', 2, 'official_guidance', 'https://www.mca.gov.in/', 'Ministry of Corporate Affairs', 'daily', '{"launch_modules":["entity_governance"]}'),
  ('b2010000-0000-4000-8000-000000000004', 'Central Board of Indirect Taxes and Customs', 'India', 2, 'official_guidance', 'https://cbic-gst.gov.in/', 'CBIC GST', 'daily', '{"launch_modules":["gst"]}'),
  ('b2010000-0000-4000-8000-000000000005', 'Income Tax Department', 'India', 2, 'official_guidance', 'https://www.incometax.gov.in/', 'Income Tax Department', 'daily', '{"launch_modules":["income_tax"]}'),
  ('b2010000-0000-4000-8000-000000000006', 'Ministry of Labour and Employment', 'India', 2, 'official_guidance', 'https://labour.gov.in/', 'Ministry of Labour and Employment', 'daily', '{"launch_modules":["employment"]}'),
  ('b2010000-0000-4000-8000-000000000007', 'Food Safety and Standards Authority of India', 'India', 2, 'official_guidance', 'https://fssai.gov.in/cms/licensing.php', 'FSSAI licensing', 'daily', '{"industries":["food_beverage"],"activities":["food_handling","food_manufacturing","food_storage","food_import","food_delivery"]}'),
  ('b2010000-0000-4000-8000-000000000008', 'Ministry of Electronics and Information Technology', 'India', 2, 'official_guidance', 'https://www.meity.gov.in/documents/act-and-policies', 'MeitY acts and policies', 'daily', '{"industries":["technology_it","retail_ecommerce"]}'),
  ('b2010000-0000-4000-8000-000000000009', 'University Grants Commission', 'India', 2, 'official_guidance', 'https://www.ugc.gov.in/regulations', 'UGC regulations', 'weekly', '{"industries":["education"]}'),
  ('b2010000-0000-4000-8000-000000000010', 'Reserve Bank of India', 'India', 2, 'official_guidance', 'https://www.rbi.org.in/', 'Reserve Bank of India', 'daily', '{"industries":["finance"]}'),
  ('b2010000-0000-4000-8000-000000000011', 'Securities and Exchange Board of India', 'India', 2, 'official_guidance', 'https://www.sebi.gov.in/legal.html', 'SEBI legal material', 'daily', '{"industries":["finance"]}'),
  ('b2010000-0000-4000-8000-000000000012', 'Central Drugs Standard Control Organisation', 'India', 2, 'official_guidance', 'https://cdsco.gov.in/opencms/opencms/en/Acts-Rules/', 'CDSCO Acts and Rules', 'daily', '{"industries":["healthcare"]}'),
  ('b2010000-0000-4000-8000-000000000013', 'Central Pollution Control Board', 'India', 2, 'official_guidance', 'https://cpcb.nic.in/acts-and-rules/', 'CPCB Acts and Rules', 'weekly', '{"industries":["manufacturing","real_estate"]}'),
  ('b2010000-0000-4000-8000-000000000014', 'Employees Provident Fund Organisation', 'India', 2, 'official_guidance', 'https://www.epfindia.gov.in/', 'EPFO', 'daily', '{"launch_modules":["employment"]}'),
  ('b2010000-0000-4000-8000-000000000015', 'Employees State Insurance Corporation', 'India', 2, 'official_guidance', 'https://www.esic.gov.in/', 'ESIC', 'daily', '{"launch_modules":["employment"]}'),
  ('b2010000-0000-4000-8000-000000000016', 'Insurance Regulatory and Development Authority of India', 'India', 2, 'official_guidance', 'https://irdai.gov.in/', 'IRDAI', 'daily', '{"industries":["finance"]}'),
  ('b2010000-0000-4000-8000-000000000017', 'Pension Fund Regulatory and Development Authority', 'India', 2, 'official_guidance', 'https://www.pfrda.org.in/', 'PFRDA', 'daily', '{"industries":["finance"]}'),
  ('b2010000-0000-4000-8000-000000000018', 'Labour Department, Government of NCT of Delhi', 'Delhi', 2, 'official_guidance', 'https://labour.delhi.gov.in/', 'Delhi Labour Department', 'daily', '{"launch_state":"DL"}'),
  ('b2010000-0000-4000-8000-000000000019', 'Labour Department, Government of Maharashtra', 'Maharashtra', 2, 'official_guidance', 'https://mahakamgar.maharashtra.gov.in/', 'Maharashtra Labour Department', 'daily', '{"launch_state":"MH"}')
on conflict (canonical_url) do update set
  authority_name = excluded.authority_name,
  jurisdiction = excluded.jurisdiction,
  source_tier = excluded.source_tier,
  source_type = excluded.source_type,
  title = excluded.title,
  monitoring_frequency = excluded.monitoring_frequency,
  metadata = excluded.metadata,
  updated_at = now();

-- Launch matrix cells are explicitly blocked until a qualified reviewer signs
-- them off. This prevents a partial row count from looking like completeness.
insert into public.compliance_coverage_cells (jurisdiction, industry_code, module_code, activity_code, status, notes)
select jurisdiction, industry_code, module_code, 'common', 'blocked',
       'Not launch-ready: qualified reviewer approval and active claim evidence are required.'
from (values ('India'), ('Delhi'), ('Maharashtra')) as jurisdictions(jurisdiction)
cross join (values
  ('food_beverage'), ('technology_it'), ('healthcare'), ('education'), ('manufacturing'),
  ('retail_ecommerce'), ('consulting_services'), ('real_estate'), ('finance'), ('other')
) as industries(industry_code)
cross join (values
  ('entity_governance'), ('gst'), ('income_tax'), ('employment'), ('premises'), ('imports_exports'), ('industry_activity')
) as modules(module_code)
on conflict (jurisdiction, industry_code, module_code, activity_code) do nothing;
