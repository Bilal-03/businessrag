// Keep analytics intentionally small and explicit. This product handles uploaded
// documents and chat prompts, so event names and properties are allow-listed
// instead of forwarding arbitrary UI state to third parties.
const ALLOWED_EVENTS = new Set([
  'app_loaded',
  'chat_submitted',
  'chat_completed',
  'chat_failed',
  'upload_started',
  'upload_rejected',
  'upload_queued',
  'upload_indexed',
  'upload_failed',
  'document_processing_completed',
  'document_processing_failed',
  'business_created',
  'business_updated',
  'business_deleted',
  'business_selected',
  'workflow_task_created',
  'workflow_task_updated',
  'workflow_task_deleted',
]);

const SENSITIVE_KEY = /^(authorization|cookie|set-cookie|access[_-]?token|refresh[_-]?token|id[_-]?token|token|query|prompt|answer|content|file[_-]?name|filename|document|snippet|email|phone|password|secret)$/i;
const SENSITIVE_TEXT = /(bearer\s+)[a-z0-9._~+/=-]+/gi;

let sentryInitialized = false;
let posthogInitialized = false;
let Sentry = null;
let posthog = null;
let sentryInitPromise = null;
let posthogInitPromise = null;
const pendingEvents = [];
const pendingExceptions = [];

function scrubText(value, maxLength = 240) {
  if (typeof value !== 'string') return value;
  return value.replace(SENSITIVE_TEXT, '$1[redacted]').slice(0, maxLength);
}

function scrubEvent(event) {
  if (event.request) {
    delete event.request.data;
    delete event.request.cookies;
    delete event.request.headers;
    delete event.request.query_string;
  }
  delete event.user;

  if (event.message) event.message = 'BizGuide client operation failed';
  if (Array.isArray(event.exception?.values)) {
    event.exception.values = event.exception.values.map(exception => ({
      ...exception,
      // Error values may contain server echoes, filenames, or user input.
      value: 'BizGuide client operation failed',
    }));
  }
  if (Array.isArray(event.breadcrumbs)) {
    event.breadcrumbs = event.breadcrumbs.map(({ category, level, type, timestamp }) => ({
      category,
      level,
      type,
      timestamp,
    }));
  }
  return event;
}

function resolvePostHogHost(value) {
  const configured = String(value || 'https://us.i.posthog.com').trim();
  try {
    const url = new URL(configured);
    // The dashboard hostname is commonly copied by mistake. Normalize it to
    // the ingestion hostname while retaining the configured region.
    if (url.hostname === 'us.posthog.com') url.hostname = 'us.i.posthog.com';
    if (url.hostname === 'eu.posthog.com') url.hostname = 'eu.i.posthog.com';
    return url.toString().replace(/\/$/, '');
  } catch {
    return 'https://us.i.posthog.com';
  }
}

function createSanitizedError(error) {
  const sanitizedError = new Error('BizGuide client operation failed');
  sanitizedError.name = error?.name || 'Error';
  if (typeof error?.stack === 'string') sanitizedError.stack = error.stack;
  return sanitizedError;
}

function sendException(error, context) {
  if (!sentryInitialized || !Sentry) return;
  Sentry.withScope(scope => {
    scope.setTag('error_name', error.name || 'Error');
    Object.entries(safeProperties(context)).forEach(([key, value]) => scope.setTag(key, value));
    Sentry.captureException(error);
  });
}

function flushPendingObservability() {
  if (posthogInitialized && posthog) {
    pendingEvents.splice(0).forEach(({ name, properties }) => posthog.capture(name, properties));
  }
  if (sentryInitialized && Sentry) {
    pendingExceptions.splice(0).forEach(({ error, context }) => sendException(error, context));
  }
}

function safeProperties(properties = {}) {
  return Object.entries(properties).reduce((result, [key, value]) => {
    if (SENSITIVE_KEY.test(key)) return result;
    if (typeof value === 'string') result[key] = scrubText(value, 80);
    else if (typeof value === 'number' && Number.isFinite(value)) result[key] = value;
    else if (typeof value === 'boolean') result[key] = value;
    return result;
  }, {});
}

export function sizeBucket(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return 'unknown';
  if (bytes < 1024 * 1024) return '<1mb';
  if (bytes < 10 * 1024 * 1024) return '1-10mb';
  if (bytes < 25 * 1024 * 1024) return '10-25mb';
  if (bytes < 50 * 1024 * 1024) return '25-50mb';
  return 'over-limit';
}

export function lengthBucket(value) {
  const length = typeof value === 'string' ? value.trim().length : 0;
  if (!length) return 'empty';
  if (length <= 80) return 'short';
  if (length <= 400) return 'medium';
  return 'long';
}

export function durationBucket(durationMs) {
  if (!Number.isFinite(durationMs) || durationMs < 0) return 'unknown';
  if (durationMs < 1000) return '<1s';
  if (durationMs < 3000) return '1-3s';
  if (durationMs < 10000) return '3-10s';
  return '10s+';
}

export function initializeObservability() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (dsn && !sentryInitPromise) {
    sentryInitPromise = import('@sentry/react').then(sdk => {
      Sentry = sdk;
      Sentry.init({
        dsn,
        environment: import.meta.env.MODE === 'production' ? 'production' : import.meta.env.MODE,
        sendDefaultPii: false,
        tracesSampleRate: 0,
        replaysSessionSampleRate: 0,
        replaysOnErrorSampleRate: 0,
        enableLogs: false,
        beforeSend: scrubEvent,
      });
      sentryInitialized = true;
      flushPendingObservability();
    }).catch(() => {
      pendingExceptions.length = 0;
    });
  }

  const key = import.meta.env.VITE_POSTHOG_KEY;
  if (key && !posthogInitPromise) {
    posthogInitPromise = import('posthog-js').then(sdk => {
      posthog = sdk.default;
      posthog.init(key, {
        api_host: resolvePostHogHost(import.meta.env.VITE_POSTHOG_HOST),
        autocapture: false,
        capture_pageview: false,
        capture_pageleave: false,
        disable_session_recording: true,
        person_profiles: 'identified_only',
        respect_dnt: true,
        persistence: 'localStorage',
        secure_cookie: true,
      });
      posthogInitialized = true;
      flushPendingObservability();
    }).catch(() => {
      pendingEvents.length = 0;
    });
  }
}

export function captureEvent(name, properties = {}) {
  if (!ALLOWED_EVENTS.has(name)) return;
  const safe = safeProperties(properties);
  if (posthogInitialized && posthog) posthog.capture(name, safe);
  else if (import.meta.env.VITE_POSTHOG_KEY && pendingEvents.length < 50) pendingEvents.push({ name, properties: safe });
}

export function captureException(error, context = {}) {
  if (!error || !import.meta.env.VITE_SENTRY_DSN) return;
  const sanitizedError = createSanitizedError(error);
  if (sentryInitialized && Sentry) sendException(sanitizedError, context);
  else if (pendingExceptions.length < 10) pendingExceptions.push({ error: sanitizedError, context });
}
