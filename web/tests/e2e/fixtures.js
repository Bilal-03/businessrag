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
    state_code: 'DL',
    status: 'operating',
    metadata: { description: 'Courier operations workspace' },
    created_at: '2026-08-02T10:00:00.000Z',
    updated_at: '2026-08-02T10:00:00.000Z',
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

export async function installMocks(page, { authenticated = true, chatMode = 'stream' } = {}) {
  const state = {
    tasks: [WORKFLOW_TASK],
    documents: [],
    nextTaskNumber: 1,
  };

  await page.addInitScript(({ isAuthenticated, marker, authStorage }) => {
    window.localStorage.clear();
    window.localStorage.setItem(`bizguide_core_cutover:${marker}`, 'core-v1');
    if (isAuthenticated) window.localStorage.setItem('sb-test-auth-token', authStorage);
  }, {
    isAuthenticated: authenticated,
    marker: TEST_USER.id,
    authStorage: sessionStorageValue(),
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
    if (table === 'conversations') {
      if (request.method() === 'GET') {
        await fulfillJson(route, []);
        return;
      }
      await fulfillJson(route, request.method() === 'DELETE' ? [] : [bodyFromRequest(request)]);
      return;
    }
    if (table === 'messages' || table === 'message_sources' || table === 'user_data') {
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
      if (chatMode === 'error') {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          headers: apiHeaders,
          body: JSON.stringify({ detail: 'AI is temporarily unavailable.', request_id: 'e2e-chat-error' }),
        });
        return;
      }
      const stream = [
        'event: meta\n',
        `data: ${JSON.stringify({
          grounding: 'document',
          agent_type: 'Document Agent',
          citations: [{
            document_id: DOCUMENT.id,
            file_name: DOCUMENT.file_name,
            page_number: 2,
            snippet: 'Verify the filing date against the official notice.',
            score: 0.94,
          }],
        })}\n\n`,
        'event: token\n',
        `data: ${JSON.stringify({ text: 'Grounded answer from your document.' })}\n\n`,
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
      const document = { ...DOCUMENT, file_name: 'uploaded-guide.pdf', business_id: null };
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

    if (path === '/api/workflow/obligations' && request.method() === 'GET') {
      await fulfillJson(route, []);
      return;
    }
    if (path === '/api/workflow/tasks' && request.method() === 'GET') {
      const businessId = url.searchParams.get('business_id');
      await fulfillJson(route, state.tasks.filter(task => task.business_id === businessId));
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
  await expect(page.getByText('Educational beta · India-focused compliance')).toBeVisible();
}
