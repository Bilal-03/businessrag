import { supabase, getUserData } from './supabase';
import { INDUSTRY_CODE_BY_LABEL, INDUSTRY_LABEL_BY_CODE } from './complianceCatalog';

/**
 * Normalized persistence for the post-cutover schema.
 *
 * The old user_data row is read only by ensureCoreCutover() and is never used
 * as the live source of truth. This keeps tenant data behind Supabase RLS and
 * makes the browser a cache for presentation preferences only.
 */

export const CORE_CUTOVER_VERSION = 'core-v1';

const LEGACY_KEYS = [
  'bizguide_conversations',
  'bizguide_businesses',
  'bizguide_uploads',
  'bizguide_checklists',
  'bizguide_checklist_state',
  'bizguide_active_business',
];

const STATE_CODES = {
  'Andhra Pradesh': 'AP',
  Delhi: 'DL',
  Gujarat: 'GJ',
  Karnataka: 'KA',
  Kerala: 'KL',
  Maharashtra: 'MH',
  'Tamil Nadu': 'TN',
  Telangana: 'TG',
  'Uttar Pradesh': 'UP',
  'West Bengal': 'WB',
  'Other / Multi-state': 'MULTI',
};

const STATE_NAMES = Object.fromEntries(Object.entries(STATE_CODES).map(([name, code]) => [code, name]));

const isUuid = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
const newUuid = () => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const hex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16));
  hex[12] = '4';
  hex[16] = ((parseInt(hex[16], 16) & 0x3) | 0x8).toString(16);
  return `${hex.slice(0, 8).join('')}-${hex.slice(8, 12).join('')}-${hex.slice(12, 16).join('')}-${hex.slice(16, 20).join('')}-${hex.slice(20).join('')}`;
};

export class CorePersistenceError extends Error {
  constructor(message, cause) {
    super(message);
    this.name = 'CorePersistenceError';
    this.cause = cause;
  }
}

function throwPersistenceError(error, message = 'Core data storage is unavailable.') {
  if (error) {
    console.warn(message, error);
  }
  throw new CorePersistenceError(message, error);
}

function parseJson(value, fallback) {
  try {
    const parsed = JSON.parse(value);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

export function businessRowToProfile(row, complianceProfile = null) {
  if (!row) return null;
  const state = STATE_NAMES[row.state_code] || row.state_code || '';
  const statusMap = { planning: 'Planning', registered: 'Registered', operating: 'Operating', on_hold: 'On Hold' };
  return {
    id: row.id,
    name: row.legal_name,
    type: row.entity_type,
    industryCode: row.industry_code || INDUSTRY_CODE_BY_LABEL[row.industry] || 'other',
    industry: row.industry || INDUSTRY_LABEL_BY_CODE[row.industry_code] || 'Other',
    state,
    status: statusMap[row.status] || 'Planning',
    description: row.metadata?.description || '',
    createdAt: row.created_at ? new Date(row.created_at).toLocaleDateString('en-IN') : '',
    updatedAt: row.updated_at,
    regulatedActivities: complianceProfile?.regulated_activities ?? null,
    gstRegistrationStatus: complianceProfile?.gst_registration_status ?? null,
    gstScheme: complianceProfile?.gst_scheme ?? null,
    incorporationStage: complianceProfile?.incorporation_stage ?? null,
    turnoverBand: complianceProfile?.turnover_band ?? null,
    employeeCountBand: complianceProfile?.employee_count_band ?? null,
    hasPhysicalEstablishment: complianceProfile?.has_physical_establishment ?? null,
    premisesStatus: complianceProfile?.premises_status ?? null,
    usesContractors: complianceProfile?.uses_contractors ?? null,
    handlesPersonalData: complianceProfile?.handles_personal_data ?? null,
    operatingStateCodes: complianceProfile?.operating_state_codes ?? null,
    operatesMultipleStates: complianceProfile?.operates_multiple_states ?? null,
    importsGoodsServices: complianceProfile?.imports_goods_services ?? null,
    exportsGoodsServices: complianceProfile?.exports_goods_services ?? null,
    complianceAnswers: complianceProfile?.answers || {},
    complianceDateAnswers: complianceProfile?.date_answers || {},
    complianceProfileVersion: complianceProfile?.profile_version || 2,
  };
}

export function businessProfileToRow(profile, ownerId) {
  const statusMap = { Planning: 'planning', Registered: 'registered', Operating: 'operating', 'On Hold': 'on_hold' };
  const state = profile.state || '';
  return {
    id: isUuid(profile.id) ? profile.id : newUuid(),
    owner_id: ownerId,
    legal_name: String(profile.name || '').trim().slice(0, 200),
    entity_type: String(profile.type || 'Other').trim().slice(0, 80),
    industry: String(profile.industry || '').trim().slice(0, 120) || null,
    industry_code: profile.industryCode || INDUSTRY_CODE_BY_LABEL[profile.industry] || 'other',
    state_code: (STATE_CODES[state] || state).slice(0, 120) || null,
    status: statusMap[profile.status] || 'planning',
    metadata: { description: String(profile.description || '').trim().slice(0, 2000) },
  };
}

export async function listBusinesses() {
  const [{ data, error }, { data: profiles, error: profileError }] = await Promise.all([
    supabase.from('businesses').select('*').order('updated_at', { ascending: false }),
    supabase.from('business_compliance_profiles').select('*'),
  ]);
  if (error) throwPersistenceError(error, 'Business profiles are unavailable until the core schema is applied.');
  if (profileError) throwPersistenceError(profileError, 'Compliance profiles are unavailable until migration 0006 is applied.');
  const profileMap = new Map((profiles || []).map(profile => [profile.business_id, profile]));
  return (data || []).map(row => businessRowToProfile(row, profileMap.get(row.id)));
}

export async function saveBusiness(profile, ownerId) {
  const payload = businessProfileToRow(profile, ownerId);
  if (!payload.legal_name) throw new CorePersistenceError('Business name is required.');
  const { data, error } = await supabase.from('businesses').upsert(payload, { onConflict: 'id' }).select('*').single();
  if (error) throwPersistenceError(error, 'The business profile could not be saved.');
  const compliancePayload = {
    business_id: data.id,
    owner_id: ownerId,
    profile_version: 2,
    regulated_activities: profile.regulatedActivities ?? null,
    gst_registration_status: profile.gstRegistrationStatus ?? null,
    gst_scheme: profile.gstScheme ?? null,
    incorporation_stage: profile.incorporationStage ?? null,
    turnover_band: profile.turnoverBand ?? null,
    employee_count_band: profile.employeeCountBand ?? null,
    has_physical_establishment: profile.hasPhysicalEstablishment ?? null,
    premises_status: profile.premisesStatus ?? null,
    uses_contractors: profile.usesContractors ?? null,
    handles_personal_data: profile.handlesPersonalData ?? null,
    operating_state_codes: profile.operatingStateCodes ?? null,
    operates_multiple_states: profile.operatesMultipleStates ?? null,
    imports_goods_services: profile.importsGoodsServices ?? null,
    exports_goods_services: profile.exportsGoodsServices ?? null,
    answers: profile.complianceAnswers || {},
    date_answers: profile.complianceDateAnswers || {},
  };
  const { data: complianceData, error: complianceError } = await supabase
    .from('business_compliance_profiles')
    .upsert(compliancePayload, { onConflict: 'business_id' })
    .select('*')
    .single();
  if (complianceError) {
    const legacyPayload = {
      business_id: data.id, owner_id: ownerId, profile_version: 1,
      regulated_activities: profile.regulatedActivities ?? null,
      gst_registration_status: profile.gstRegistrationStatus ?? null,
      turnover_band: profile.turnoverBand ?? null,
      employee_count_band: profile.employeeCountBand ?? null,
      has_physical_establishment: profile.hasPhysicalEstablishment ?? null,
      operates_multiple_states: profile.operatesMultipleStates ?? null,
      imports_goods_services: profile.importsGoodsServices ?? null,
      exports_goods_services: profile.exportsGoodsServices ?? null,
      answers: profile.complianceAnswers || {},
    };
    const { data: legacyData, error: legacyError } = await supabase.from('business_compliance_profiles').upsert(legacyPayload, { onConflict: 'business_id' }).select('*').single();
    if (legacyError) throwPersistenceError(legacyError, 'The business compliance profile could not be saved.');
    return businessRowToProfile(data, legacyData);
  }
  return businessRowToProfile(data, complianceData);
}

export async function deleteBusiness(id) {
  if (!isUuid(id)) return;
  const { error } = await supabase.from('businesses').delete().eq('id', id);
  if (error) throwPersistenceError(error, 'The business profile could not be deleted.');
}

function messageToRow(message, conversationId, ownerId, index) {
  const id = isUuid(message.id) ? message.id : newUuid();
  return {
    id,
    owner_id: ownerId,
    conversation_id: conversationId,
    role: message.role === 'ai' ? 'assistant' : message.role,
    content: String(message.content || '').slice(0, 30000),
    agent_type: message.agentType || null,
    grounding: ['document', 'mixed', 'general', 'insufficient'].includes(message.grounding) ? message.grounding : 'general',
    schema_version: message.schemaVersion || 1,
    answer_mode: message.answerMode || null,
    evidence_status: message.evidenceStatus || null,
    trust_metadata: {
      language: message.language || 'en',
      assumptions: message.assumptions || [],
      missing_inputs: message.missingInputs || [],
      conflicts: message.conflicts || [],
      coverage: message.coverage || {},
      effective_date: message.effectiveDate || null,
      profile_version: message.profileVersion || null,
      escalation: message.escalation || null,
      official_citations: (message.citations || []).filter(citation => citation.source_kind === 'official'),
    },
    client_message_id: message.clientMessageId || `${conversationId}:${index}:${message.role}`,
  };
}

function messageRowToUi(row, sourceMap) {
  const citations = (sourceMap.get(row.id) || []).map(source => ({
    document_id: source.document_id,
    file_name: source.file_name || null,
    page_number: source.page_number || null,
    snippet: source.snippet,
    score: source.score,
  }));
  return {
    id: row.id,
    clientMessageId: row.client_message_id,
    role: row.role === 'assistant' ? 'ai' : 'user',
    content: row.content,
    agentType: row.agent_type || 'General Agent',
    grounding: row.grounding || 'general',
    schemaVersion: row.schema_version || 1,
    answerMode: row.answer_mode || null,
    evidenceStatus: row.evidence_status || null,
    language: row.trust_metadata?.language || 'en',
    assumptions: row.trust_metadata?.assumptions || [],
    missingInputs: row.trust_metadata?.missing_inputs || [],
    conflicts: row.trust_metadata?.conflicts || [],
    coverage: row.trust_metadata?.coverage || {},
    effectiveDate: row.trust_metadata?.effective_date || null,
    profileVersion: row.trust_metadata?.profile_version || null,
    escalation: row.trust_metadata?.escalation || null,
    citations: [...(row.trust_metadata?.official_citations || []), ...citations],
  };
}

export async function listConversations() {
  const { data: conversations, error } = await supabase
    .from('conversations')
    .select('*')
    .is('archived_at', null)
    .order('updated_at', { ascending: false });
  if (error) throwPersistenceError(error, 'Conversation history is unavailable until the core schema is applied.');
  if (!conversations?.length) return [];

  const ids = conversations.map(conversation => conversation.id);
  const [{ data: messages, error: messageError }, { data: sources, error: sourceError }] = await Promise.all([
    supabase.from('messages').select('*').in('conversation_id', ids).order('created_at', { ascending: true }),
    supabase.from('message_sources').select('*, documents(file_name)').in('message_id', ids),
  ]);
  if (messageError) throwPersistenceError(messageError, 'Conversation messages are unavailable.');
  // A source read failure should not hide an otherwise usable conversation.
  if (sourceError) console.warn('Conversation citations are temporarily unavailable.', sourceError);
  const sourceMap = new Map();
  (sources || []).forEach(source => {
    const list = sourceMap.get(source.message_id) || [];
    list.push({ ...source, file_name: source.documents?.file_name || null });
    sourceMap.set(source.message_id, list);
  });
  return conversations.map(conversation => ({
    id: conversation.id,
    title: conversation.title,
    date: conversation.created_at ? new Date(conversation.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '',
    businessId: conversation.business_id,
    messages: (messages || []).filter(message => message.conversation_id === conversation.id).map(message => messageRowToUi(message, sourceMap)),
  }));
}

export async function saveConversation(conversation, ownerId) {
  const conversationId = isUuid(conversation.id) ? conversation.id : newUuid();
  const businessId = isUuid(conversation.businessId) ? conversation.businessId : null;
  const title = String(conversation.title || 'New conversation').trim().slice(0, 200) || 'New conversation';
  const { error: conversationError } = await supabase.from('conversations').upsert({
    id: conversationId,
    owner_id: ownerId,
    business_id: businessId,
    title,
  }, { onConflict: 'id' });
  if (conversationError) throwPersistenceError(conversationError, 'The conversation could not be saved.');

  const rows = (conversation.messages || [])
    .map((message, index) => messageToRow(message, conversationId, ownerId, index))
    .filter(message => message.content);
  const { error: clearMessageError } = await supabase.from('messages').delete().eq('conversation_id', conversationId);
  if (clearMessageError) throwPersistenceError(clearMessageError, 'The conversation messages could not be replaced.');
  if (rows.length) {
    let { data: insertedMessages, error: messageError } = await supabase.from('messages').insert(rows).select('*');
    if (messageError) {
      const legacyRows = rows.map(row => ({
        id: row.id,
        owner_id: row.owner_id,
        conversation_id: row.conversation_id,
        role: row.role,
        content: row.content,
        agent_type: row.agent_type,
        grounding: row.grounding,
        client_message_id: row.client_message_id,
      }));
      const fallback = await supabase.from('messages').insert(legacyRows).select('*');
      insertedMessages = fallback.data;
      messageError = fallback.error;
    }
    if (messageError) throwPersistenceError(messageError, 'The conversation messages could not be saved.');
    const sourceRows = [];
    (conversation.messages || []).forEach((message, index) => {
      const inserted = (insertedMessages || []).find(row => row.client_message_id === `${conversationId}:${index}:${message.role}`);
      if (!inserted || !Array.isArray(message.citations)) return;
      message.citations.forEach(citation => {
        if (!isUuid(citation.document_id) || !citation.snippet) return;
        sourceRows.push({
          owner_id: ownerId,
          message_id: inserted.id,
          document_id: citation.document_id,
          page_number: citation.page_number || null,
          snippet: String(citation.snippet).slice(0, 1200),
          score: typeof citation.score === 'number' ? citation.score : null,
        });
      });
    });
    if (sourceRows.length) {
      const { error: sourceError } = await supabase.from('message_sources').insert(sourceRows);
      if (sourceError) console.warn('Conversation source citations could not be persisted.', sourceError);
    }
  }
  return { ...conversation, id: conversationId, businessId };
}

export async function deleteConversation(id) {
  if (!isUuid(id)) return;
  const { error } = await supabase.from('conversations').delete().eq('id', id);
  if (error) throwPersistenceError(error, 'The conversation could not be deleted.');
}

export async function deleteAllConversations() {
  // RLS scopes this delete to the signed-in owner. A broad delete is safe here
  // because no service-role credential ever reaches the browser.
  const { error } = await supabase.from('conversations').delete().not('id', 'is', null);
  if (error) throwPersistenceError(error, 'Conversation history could not be cleared.');
}

export async function ensureCoreCutover(userId) {
  if (!userId) return { ready: false, migrated: false };
  const markerKey = `bizguide_core_cutover:${userId}`;
  const probe = await supabase.from('businesses').select('id').limit(1);
  if (probe.error) {
    return { ready: false, migrated: false, error: new CorePersistenceError('Core storage is not available. Apply the Supabase migration before using saved workspace data.', probe.error) };
  }
  if (localStorage.getItem(markerKey) === CORE_CUTOVER_VERSION) return { ready: true, migrated: false };

  const legacy = await getUserData(userId).catch(() => null);
  const localBusinesses = parseJson(localStorage.getItem('bizguide_businesses') || '[]', []);
  const localConversations = parseJson(localStorage.getItem('bizguide_conversations') || '[]', []);
  const legacyBusinesses = [...(Array.isArray(legacy?.businesses) ? legacy.businesses : []), ...(Array.isArray(localBusinesses) ? localBusinesses : [])];
  const uniqueBusinesses = new Map();
  legacyBusinesses.forEach(profile => {
    if (profile?.name?.trim()) uniqueBusinesses.set(String(profile.name).trim().toLowerCase(), profile);
  });
  const existingBusinesses = await listBusinesses();
  if (!existingBusinesses.length) {
    for (const profile of uniqueBusinesses.values()) await saveBusiness(profile, userId);
  }

  const legacyConversations = [...(Array.isArray(legacy?.conversations) ? legacy.conversations : []), ...(Array.isArray(localConversations) ? localConversations : [])];
  if (legacyConversations.length) {
    const existingConversations = await listConversations();
    if (!existingConversations.length) {
      for (const conversation of legacyConversations.slice(0, 100)) {
        await saveConversation({
          id: null,
          title: conversation.title,
          businessId: null,
          messages: Array.isArray(conversation.messages) ? conversation.messages : [],
        }, userId);
      }
    }
  }

  // Legacy checklist state and upload history are deliberately not imported:
  // neither has source/version or document ownership guarantees.
  LEGACY_KEYS.forEach(key => localStorage.removeItem(key));
  localStorage.setItem(markerKey, CORE_CUTOVER_VERSION);
  return { ready: true, migrated: legacyBusinesses.length > 0 || legacyConversations.length > 0 };
}

export { isUuid, newUuid };
