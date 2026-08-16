import { expect } from '@playwright/test';

export const TEST_USER = {
  id: '11111111-1111-4111-8111-111111111111',
  email: 'e2e@example.com',
  aud: 'authenticated',
  role: 'authenticated',
};

export const SESSION = {
  access_token: 'e2e-access-token',
  token_type: 'bearer',
  expires_in: 3600,
  expires_at: Math.floor(Date.now() / 1000) + 3600,
  refresh_token: 'e2e-refresh-token',
  user: TEST_USER,
};

export const BUSINESSES = [
  {
    id: '22222222-2222-4222-8222-222222222222',
    owner_id: TEST_USER.id,
    legal_name: 'Acme Foods Pvt Ltd',
    entity_type: 'Private Limited (Pvt Ltd)',
    industry: 'Food & Beverage',
    industry_code: 'food_beverage',
    state_code: 'MH',
    status: 'operating',
    metadata: { description: 'Food manufacturing workspace' },
    created_at: '2026-08-01T10:00:00.000Z',
    updated_at: '2026-08-01T10:00:00.000Z',
  },
  {
    id: '33333333-3333-4333-8333-333333333333',
    owner_id: TEST_USER.id,
    legal_name: 'Acme Courier Services',
    entity_type: 'Private Limited (Pvt Ltd)',
    industry: 'Technology/IT',
    industry_code: 'technology_it',
    state_code: 'DL',
    status: 'operating',
    metadata: { description: 'Courier operations workspace' },
    created_at: '2026-08-02T10:00:00.000Z',
    updated_at: '2026-08-02T10:00:00.000Z',
  },
];

export const COMPLIANCE_PROFILES = [
  {
    business_id: BUSINESSES[0].id,
    owner_id: TEST_USER.id,
    profile_version: 2,
    regulated_activities: ['food_manufacturing'],
    gst_registration_status: 'not_registered',
    has_physical_establishment: true,
    answers: {},
  },
  {
    business_id: BUSINESSES[1].id,
    owner_id: TEST_USER.id,
    profile_version: 2,
    regulated_activities: [],
    gst_registration_status: null,
    has_physical_establishment: true,
    answers: {},
  },
];

export const WORKFLOW_TASK = {
  id: '44444444-4444-4444-8444-444444444444',
  business_id: BUSINESSES[1].id,
  obligation_id: null,
  title: 'Review GST filing',
  status: 'todo',
  due_date: '2026-09-01',
  completed_at: null,
  created_at: '2026-08-03T10:00:00.000Z',
  updated_at: '2026-08-03T10:00:00.000Z',
};

export const WORKFLOW_OBLIGATIONS = [
  {
    id: '77777777-7777-4777-8777-777777777771',
    jurisdiction: 'India',
    title: 'Food business registration or licence (FSSAI)',
    description: 'Confirm the applicable FSSAI registration or licence category from the current official criteria.',
    source_url: 'https://fssai.gov.in/cms/licensing.php',
    source_version: 'Regulations 2011; Amendment 5 (23 Jun 2026)',
    source_citation: 'FSS Act, 2006, section 31(1); FSS Licensing Regulations, 2011, regulation 1.1.2.',
    primary_claim_id: 'claim-fssai',
    effective_from: '2011-08-05',
    effective_to: null,
    published: true,
    review_status: 'published',
    review_owner: 'food-safety-domain-review',
    reviewed_at: '2026-08-12T10:00:00.000Z',
    metadata: {},
  },
  {
    id: '77777777-7777-4777-8777-777777777775',
    jurisdiction: 'India',
    title: 'GSTR-3B return (where applicable)',
    description: 'Registered persons covered by the reviewed rule must furnish Form GSTR-3B.',
    source_url: 'https://cbic-gst.gov.in/pdf/10112020_CGST-Rules-2017_Part-A_Rules.pdf',
    source_version: 'Central Goods and Services Tax Rules, 2017, rule 61',
    source_citation: 'Central Goods and Services Tax Act, 2017, section 39; CGST Rules, rule 61.',
    primary_claim_id: 'claim-gstr3b',
    effective_from: '2017-07-01',
    effective_to: null,
    published: true,
    review_status: 'published',
    review_owner: 'indirect-tax-domain-review',
    reviewed_at: '2026-08-12T10:00:00.000Z',
    metadata: {},
  },
  {
    id: '77777777-7777-4777-8777-777777777772',
    jurisdiction: 'Delhi',
    title: 'Delhi Shops and Establishments employment requirements',
    description: 'Check the current Delhi Labour Department summary for covered establishments.',
    source_url: 'https://labour.delhi.gov.in/labour/inspectorate',
    source_version: 'Delhi Shops and Establishments Act, 1954',
    source_citation: 'Delhi Shops and Establishments Act, 1954, sections 8, 10, 15, 16, and 34.',
    primary_claim_id: 'claim-delhi-shop',
    effective_from: '1955-02-01',
    effective_to: null,
    published: true,
    review_status: 'published',
    review_owner: 'delhi-labour-domain-review',
    reviewed_at: '2026-08-12T10:00:00.000Z',
    metadata: {},
  },
  {
    id: '77777777-7777-4777-8777-777777777773',
    jurisdiction: 'India',
    title: 'Pending review source must stay hidden',
    description: 'This fixture row is intentionally not user-facing.',
    source_url: 'https://fssai.gov.in/cms/licensing.php',
    source_version: 'pending',
    source_citation: 'Pending domain review.',
    effective_from: '2011-08-05',
    effective_to: null,
    published: true,
    review_status: 'reviewed',
    review_owner: 'pending-review',
    reviewed_at: '2026-08-12T10:00:00.000Z',
    metadata: {},
  },
  {
    id: '77777777-7777-4777-8777-777777777774',
    jurisdiction: 'India',
    title: 'Expired source must stay hidden',
    description: 'This fixture row is outside its effective window.',
    source_url: 'https://fssai.gov.in/cms/licensing.php',
    source_version: 'expired',
    source_citation: 'Expired source window.',
    effective_from: '2011-08-05',
    effective_to: '2026-01-01',
    published: true,
    review_status: 'published',
    review_owner: 'food-safety-domain-review',
    reviewed_at: '2026-08-12T10:00:00.000Z',
    metadata: {},
  },
];

export const DOCUMENT = {
  id: '55555555-5555-4555-8555-555555555555',
  business_id: BUSINESSES[1].id,
  file_name: 'employee-handbook.pdf',
  mime_type: 'application/pdf',
  byte_size: 4096,
  status: 'indexed',
  created_at: '2026-08-03T10:00:00.000Z',
  indexed_at: '2026-08-03T10:01:00.000Z',
};

export const SAVED_CONVERSATIONS = [
  {
    id: '66666666-6666-4666-8666-666666666666',
    owner_id: TEST_USER.id,
    business_id: BUSINESSES[0].id,
    title: 'FSSAI registration requirements',
    created_at: '2026-08-04T10:00:00.000Z',
    updated_at: '2026-08-04T10:05:00.000Z',
    archived_at: null,
  },
];

export const SAVED_MESSAGES = [
  {
    id: '88888888-8888-4888-8888-888888888888',
    owner_id: TEST_USER.id,
    conversation_id: SAVED_CONVERSATIONS[0].id,
    role: 'user',
    content: 'What documents do I need for FSSAI registration?',
    agent_type: null,
    grounding: 'general',
    schema_version: 1,
    answer_mode: null,
    evidence_status: null,
    trust_metadata: {},
    client_message_id: `${SAVED_CONVERSATIONS[0].id}:0:user`,
    created_at: '2026-08-04T10:00:00.000Z',
  },
  {
    id: '99999999-9999-4999-8999-999999999999',
    owner_id: TEST_USER.id,
    conversation_id: SAVED_CONVERSATIONS[0].id,
    role: 'assistant',
    content: 'Start with the official FSSAI application requirements and verify the licence category for your activity.',
    agent_type: 'General Agent',
    grounding: 'general',
    schema_version: 1,
    answer_mode: 'general_business_guidance',
    evidence_status: 'general_guidance',
    trust_metadata: { context_used: ['business'] },
    client_message_id: `${SAVED_CONVERSATIONS[0].id}:1:ai`,
    created_at: '2026-08-04T10:05:00.000Z',
  },
];

const JSON_HEADERS = {
  'Access-Control-Allow-Origin': 'http://127.0.0.1:4173',
  'Access-Control-Allow-Headers': 'apikey, authorization, content-type, x-client-info, prefer',
  'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS',
  'Access-Control-Expose-Headers': 'content-range, x-request-id',
};

async function fulfillJson(route, payload, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    headers: JSON_HEADERS,
    body: status === 204 ? '' : JSON.stringify(payload),
  });
}

function sessionStorageValue() {
  return JSON.stringify({
    ...SESSION,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
  });
}

function bodyFromRequest(request) {
  try {
    return JSON.parse(request.postData() || '{}');
  } catch {
    return {};
  }
}

export async function installMocks(page, { authenticated = true, chatMode = 'stream', activeBusinessId = null, seedWorkspace = false } = {}) {
  const state = {
    tasks: [WORKFLOW_TASK],
    obligations: WORKFLOW_OBLIGATIONS,
    documents: seedWorkspace ? [DOCUMENT] : [],
    conversations: seedWorkspace ? SAVED_CONVERSATIONS.map(conversation => ({ ...conversation })) : [],
    messages: seedWorkspace ? SAVED_MESSAGES.map(message => ({ ...message })) : [],
    nextTaskNumber: 1,
    complianceProfiles: COMPLIANCE_PROFILES.map(profile => ({ ...profile })),
  };
  let chatAttempts = 0;

  await page.addInitScript(({ isAuthenticated, marker, authStorage, selectedBusinessId }) => {
    window.localStorage.clear();
    window.localStorage.setItem(`bizguide_core_cutover:${marker}`, 'core-v1');
    if (isAuthenticated) window.localStorage.setItem('sb-test-auth-token', authStorage);
    if (selectedBusinessId) window.localStorage.setItem(`bizguide_active_business:${marker}`, selectedBusinessId);
  }, {
    isAuthenticated: authenticated,
    marker: TEST_USER.id,
    authStorage: sessionStorageValue(),
    selectedBusinessId: activeBusinessId,
  });

  await page.route('**/auth/v1/**', async route => {
    const request = route.request();
    if (request.method() === 'OPTIONS') {
      await fulfillJson(route, {}, 204);
      return;
    }
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/session')) {
      await fulfillJson(route, authenticated ? SESSION : null);
      return;
    }
    if (path.endsWith('/token')) {
      await fulfillJson(route, SESSION);
      return;
    }
    if (path.endsWith('/user')) {
      await fulfillJson(route, authenticated ? TEST_USER : {}, authenticated ? 200 : 401);
      return;
    }
    if (path.endsWith('/logout')) {
      await fulfillJson(route, {}, 204);
      return;
    }
    await fulfillJson(route, {});
  });

  await page.route('**/rest/v1/**', async route => {
    const request = route.request();
    if (request.method() === 'OPTIONS') {
      await fulfillJson(route, {}, 204);
      return;
    }
    const url = new URL(request.url());
    const table = url.pathname.split('/').pop();
    if (table === 'businesses') {
      if (request.method() === 'GET') {
        await fulfillJson(route, BUSINESSES);
        return;
      }
      if (request.method() === 'DELETE') {
        await fulfillJson(route, []);
        return;
      }
      const body = bodyFromRequest(request);
      await fulfillJson(route, Array.isArray(body) ? body : [body]);
      return;
    }
    if (table === 'business_compliance_profiles') {
      if (request.method() === 'GET') {
        await fulfillJson(route, state.complianceProfiles);
        return;
      }
      const body = bodyFromRequest(request);
      const existing = state.complianceProfiles.find(profile => profile.business_id === body.business_id);
      if (existing) Object.assign(existing, body);
      else state.complianceProfiles.push(body);
      await fulfillJson(route, [existing || body]);
      return;
    }
    if (table === 'conversations') {
      if (request.method() === 'GET') {
        await fulfillJson(route, state.conversations);
        return;
      }
      await fulfillJson(route, request.method() === 'DELETE' ? [] : [bodyFromRequest(request)]);
      return;
    }
    if (table === 'messages') {
      if (request.method() === 'GET') {
        await fulfillJson(route, state.messages);
        return;
      }
      await fulfillJson(route, []);
      return;
    }
    if (table === 'message_sources' || table === 'user_data') {
      if (request.method() === 'GET') {
        await fulfillJson(route, []);
        return;
      }
      await fulfillJson(route, []);
      return;
    }
    await fulfillJson(route, []);
  });

  await page.route('**/api/**', async route => {
    const request = route.request();
    if (request.method() === 'OPTIONS') {
      await fulfillJson(route, {}, 204);
      return;
    }
    const url = new URL(request.url());
    const path = url.pathname;
    const apiHeaders = {
      ...JSON_HEADERS,
      'X-Request-ID': 'e2e-request-id',
    };

    if (path === '/api/chat/stream' && request.method() === 'POST') {
      if (chatMode === 'error' || (chatMode === 'transient-error' && chatAttempts++ === 0)) {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          headers: apiHeaders,
          body: JSON.stringify({ detail: 'AI is temporarily unavailable.', request_id: 'e2e-chat-error' }),
        });
        return;
      }
      const requestBody = bodyFromRequest(request);
      const useBusinessContext = requestBody.use_business_context === true;
      const useDocumentContext = requestBody.use_document_context === true;
      const contextUsed = [
        ...(useBusinessContext ? ['business'] : []),
        ...(useDocumentContext ? ['documents'] : []),
      ];
      const answer = useDocumentContext ? 'Grounded answer from your document.' : 'Independent answer.';
      const documentSnippet = chatMode === 'long-document-snippet'
        ? 'TransactionControlLanguage(TCL)'.repeat(20)
        : 'Verify the filing date against the official notice.';
      const stream = [
        'event: meta\n',
        `data: ${JSON.stringify({
          grounding: useDocumentContext ? 'document' : 'general',
          agent_type: useDocumentContext ? 'Document Agent' : 'General Agent',
          evidence_status: useDocumentContext ? 'partially_supported' : 'general_guidance',
          answer_mode: useDocumentContext ? 'user_document_analysis' : 'general_business_guidance',
          context_used: contextUsed,
          effective_date: '2026-08-16',
          citations: useDocumentContext ? [{
            document_id: DOCUMENT.id,
            file_name: DOCUMENT.file_name,
            page_number: 2,
            snippet: documentSnippet,
            score: 0.94,
          }] : [],
        })}\n\n`,
        'event: token\n',
        `data: ${JSON.stringify({ text: answer })}\n\n`,
        'event: done\n',
        'data: {}\n\n',
      ].join('');
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        headers: { ...apiHeaders, 'Cache-Control': 'no-cache' },
        body: stream,
      });
      return;
    }

    if (path === '/api/chat' && request.method() === 'POST') {
      await fulfillJson(route, { answer: 'Fallback answer.', citations: [], grounding: 'general', agent_type: 'General Agent' });
      return;
    }

    if (path === '/api/documents' && request.method() === 'GET') {
      await fulfillJson(route, state.documents);
      return;
    }
    if (path === '/api/documents/upload' && request.method() === 'POST') {
      const document = {
        ...DOCUMENT,
        id: state.documents.some(item => item.id === DOCUMENT.id)
          ? '55555555-5555-4555-8555-555555555556'
          : DOCUMENT.id,
        file_name: 'uploaded-guide.pdf',
        business_id: null,
      };
      state.documents.unshift(document);
      await fulfillJson(route, {
        message: 'Successfully uploaded and indexed 1 chunk from uploaded-guide.pdf',
        document_id: document.id,
        file_name: document.file_name,
        chunks_indexed: 1,
        status: 'indexed',
        created_at: document.created_at,
        request_id: 'e2e-upload-id',
      });
      return;
    }
    if (path.startsWith('/api/documents/') && request.method() === 'DELETE') {
      const documentId = path.split('/').pop();
      state.documents = state.documents.filter(document => document.id !== documentId);
      await fulfillJson(route, {} , 204);
      return;
    }

    if (path === '/api/workflow/plan' && request.method() === 'GET') {
      const businessId = url.searchParams.get('business_id');
      const business = BUSINESSES.find(item => item.id === businessId);
      const profile = state.complianceProfiles.find(item => item.business_id === businessId) || {};
      const applicable = state.obligations.filter(obligation => {
        if (obligation.review_status !== 'published' || obligation.effective_to) return false;
        if (obligation.title.includes('Food business')) return business?.industry_code === 'food_beverage' || profile.regulated_activities?.some(value => value.startsWith('food_'));
        if (obligation.title.includes('GSTR-3B')) return profile.gst_registration_status === 'registered';
        if (obligation.jurisdiction === 'Delhi') return business?.state_code === 'DL' && profile.has_physical_establishment === true;
        return false;
      });
      const questions = [];
      if (profile.gst_registration_status == null) {
        questions.push({
          key: 'gst_registration_status',
          label: 'Is this business registered for GST?',
          description: 'GSTR obligations are not shown until registration is confirmed.',
          answer_type: 'single_select',
          options: [
            { value: 'registered', label: 'Yes, registered' },
            { value: 'not_registered', label: 'No, not registered' },
            { value: 'not_applicable', label: 'Not applicable' },
          ],
          current_value: null,
        });
      }
      await fulfillJson(route, {
        business_id: businessId,
        obligations: applicable,
        questions,
        coverage: {
          central: { status: 'partial', message: 'Reviewed central coverage is partial.' },
          state: {
            status: business?.state_code === 'DL' ? 'partial' : 'in_review',
            jurisdiction: business?.state_code === 'DL' ? 'Delhi' : 'Maharashtra',
            message: 'No complete reviewed state catalog is available; no state requirement is guessed.',
          },
        },
        profile_version: 2,
      });
      return;
    }
    if (path.includes('/api/workflow/businesses/') && path.endsWith('/compliance-profile') && request.method() === 'PATCH') {
      const businessId = path.split('/')[4];
      const profile = state.complianceProfiles.find(item => item.business_id === businessId);
      Object.assign(profile, bodyFromRequest(request));
      await fulfillJson(route, profile);
      return;
    }
    if (path === '/api/workflow/tasks' && request.method() === 'GET') {
      const businessId = url.searchParams.get('business_id');
      await fulfillJson(route, state.tasks.filter(task => task.business_id === businessId));
      return;
    }
    if (path === '/api/workflow/reminders' && request.method() === 'GET') {
      await fulfillJson(route, []);
      return;
    }
    if (path === '/api/workflow/reminders/due' && request.method() === 'GET') {
      await fulfillJson(route, []);
      return;
    }
    if (path === '/api/answers/feedback' && request.method() === 'POST') {
      await fulfillJson(route, { id: '99999999-9999-4999-8999-999999999999', ...bodyFromRequest(request) }, 201);
      return;
    }
    if (path === '/api/review/me' && request.method() === 'GET') {
      await fulfillJson(route, { is_reviewer: false, roles: [] });
      return;
    }
    if (path === '/api/workflow/tasks' && request.method() === 'POST') {
      const body = bodyFromRequest(request);
      const task = {
        ...body,
        id: `66666666-6666-4666-8666-66666666666${state.nextTaskNumber}`,
        status: body.status || 'todo',
        obligation_id: null,
        completed_at: null,
        created_at: '2026-08-04T10:00:00.000Z',
        updated_at: '2026-08-04T10:00:00.000Z',
      };
      state.nextTaskNumber += 1;
      state.tasks.unshift(task);
      await fulfillJson(route, task, 201);
      return;
    }
    if (path.endsWith('/evidence') && request.method() === 'GET') {
      await fulfillJson(route, []);
      return;
    }
    if (path.endsWith('/history') && request.method() === 'GET') {
      await fulfillJson(route, []);
      return;
    }
    if (path.endsWith('/evidence') && request.method() === 'POST') {
      const taskId = path.split('/')[4];
      await fulfillJson(route, { id: '88888888-8888-4888-8888-888888888888', task_id: taskId, created_at: '2026-08-14T00:00:00Z', ...bodyFromRequest(request) }, 201);
      return;
    }
    if (path.startsWith('/api/workflow/tasks/') && request.method() === 'PATCH') {
      const taskId = path.split('/').pop();
      const task = state.tasks.find(item => item.id === taskId);
      const updated = { ...task, ...bodyFromRequest(request) };
      state.tasks = state.tasks.map(item => item.id === taskId ? updated : item);
      await fulfillJson(route, updated);
      return;
    }
    if (path.startsWith('/api/workflow/tasks/') && request.method() === 'DELETE') {
      const taskId = path.split('/').pop();
      state.tasks = state.tasks.filter(item => item.id !== taskId);
      await fulfillJson(route, {}, 204);
      return;
    }

    await fulfillJson(route, {});
  });
}

export async function openAuthenticatedApp(page, options = {}) {
  await installMocks(page, { authenticated: true, ...options });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
}

export async function openAuthenticatedChat(page, options = {}) {
  await openAuthenticatedApp(page, options);
  await page.getByRole('button', { name: 'Ask BizGuide', exact: true }).click();
  // Navigation is opened by a button click, but the accessibility suite also
  // verifies the document's first keyboard stop is the skip link.
  await page.evaluate(() => document.activeElement?.blur());
  await expect(page.getByRole('textbox', { name: 'Ask BizGuide a question' })).toBeVisible();
}
