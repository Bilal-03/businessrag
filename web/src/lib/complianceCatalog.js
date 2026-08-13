export const INDUSTRY_OPTIONS = [
  { code: 'food_beverage', label: 'Food & Beverage' },
  { code: 'technology_it', label: 'Technology/IT' },
  { code: 'healthcare', label: 'Healthcare' },
  { code: 'education', label: 'Education' },
  { code: 'manufacturing', label: 'Manufacturing' },
  { code: 'retail_ecommerce', label: 'Retail & E-Commerce' },
  { code: 'consulting_services', label: 'Consulting/Services' },
  { code: 'real_estate', label: 'Real Estate' },
  { code: 'finance', label: 'Finance' },
  { code: 'other', label: 'Other' },
];

export const INDUSTRY_CODE_BY_LABEL = Object.fromEntries(INDUSTRY_OPTIONS.map(option => [option.label, option.code]));
export const INDUSTRY_LABEL_BY_CODE = Object.fromEntries(INDUSTRY_OPTIONS.map(option => [option.code, option.label]));

export const ACTIVITY_OPTIONS = [
  { value: 'food_handling', label: 'Handles or prepares food', industries: ['food_beverage', 'retail_ecommerce'] },
  { value: 'food_manufacturing', label: 'Manufactures food', industries: ['food_beverage', 'manufacturing'] },
  { value: 'food_storage', label: 'Stores food commercially', industries: ['food_beverage', 'retail_ecommerce'] },
  { value: 'food_import', label: 'Imports food', industries: ['food_beverage', 'retail_ecommerce'] },
  { value: 'food_delivery', label: 'Delivers food', industries: ['food_beverage', 'technology_it', 'retail_ecommerce'] },
  { value: 'saas_digital_service', label: 'Provides SaaS or digital services', industries: ['technology_it'] },
  { value: 'personal_data_processing', label: 'Processes personal data', industries: ['technology_it', 'healthcare', 'education', 'finance'] },
  { value: 'online_intermediary', label: 'Operates an online intermediary or platform', industries: ['technology_it', 'retail_ecommerce'] },
  { value: 'ecommerce_marketplace', label: 'Operates an e-commerce marketplace', industries: ['technology_it', 'retail_ecommerce'] },
  { value: 'clinical_establishment', label: 'Operates a clinical establishment', industries: ['healthcare'] },
  { value: 'pharmacy', label: 'Operates a pharmacy', industries: ['healthcare', 'retail_ecommerce'] },
  { value: 'diagnostics', label: 'Provides diagnostic services', industries: ['healthcare'] },
  { value: 'medical_devices', label: 'Makes, imports, or sells medical devices', industries: ['healthcare', 'manufacturing', 'retail_ecommerce'] },
  { value: 'school_education', label: 'Operates a school', industries: ['education'] },
  { value: 'coaching_training', label: 'Provides coaching or training', industries: ['education'] },
  { value: 'higher_education', label: 'Provides higher education', industries: ['education'] },
  { value: 'online_education', label: 'Provides online education', industries: ['education', 'technology_it'] },
  { value: 'awards_qualifications', label: 'Awards qualifications', industries: ['education'] },
  { value: 'factory_operations', label: 'Operates a factory', industries: ['manufacturing'] },
  { value: 'hazardous_process', label: 'Uses a hazardous process', industries: ['manufacturing'] },
  { value: 'pollution_generating', label: 'May require environmental consent review', industries: ['manufacturing', 'real_estate'] },
  { value: 'physical_retail', label: 'Operates a physical retail location', industries: ['retail_ecommerce'] },
  { value: 'packaged_goods_sale', label: 'Sells packaged goods', industries: ['retail_ecommerce'] },
  { value: 'professional_consulting', label: 'Provides professional consulting services', industries: ['consulting_services'] },
  { value: 'real_estate_promoter', label: 'Acts as a real-estate promoter', industries: ['real_estate'] },
  { value: 'real_estate_agent', label: 'Acts as a real-estate agent or broker', industries: ['real_estate'] },
  { value: 'construction', label: 'Carries out construction', industries: ['real_estate', 'manufacturing'] },
  { value: 'lending', label: 'Provides lending', industries: ['finance'] },
  { value: 'payments', label: 'Provides payment services', industries: ['finance', 'technology_it'] },
  { value: 'investment_advice', label: 'Provides investment advice', industries: ['finance'] },
  { value: 'insurance', label: 'Provides insurance services', industries: ['finance'] },
  { value: 'pension', label: 'Provides pension services', industries: ['finance'] },
];

export function activityOptionsFor(industryCode, selected = []) {
  const selectedSet = new Set(selected || []);
  return [...ACTIVITY_OPTIONS].sort((left, right) => {
    const leftPriority = left.industries.includes(industryCode) || selectedSet.has(left.value) ? 0 : 1;
    const rightPriority = right.industries.includes(industryCode) || selectedSet.has(right.value) ? 0 : 1;
    return leftPriority - rightPriority || left.label.localeCompare(right.label);
  });
}
