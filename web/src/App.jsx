import React, { lazy, Suspense, useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, Building2, UtensilsCrossed, Rocket, BarChart3, Wallet, Scale, Flag, ThumbsUp } from 'lucide-react';
import Sidebar from './components/Sidebar';
import { supabase } from './lib/supabase';
import { captureEvent, captureException, durationBucket, lengthBucket, sizeBucket } from './lib/observability';
import {
  deleteAllConversations,
  deleteBusiness,
  deleteConversation,
  ensureCoreCutover,
  listBusinesses,
  listConversations,
  newUuid,
  saveBusiness,
  saveConversation,
} from './lib/corePersistence';
import './App.css';

const MyBusinesses = lazy(() => import('./components/MyBusinesses.jsx'));
const UploadDocuments = lazy(() => import('./components/UploadDocuments.jsx'));
const WorkflowDashboard = lazy(() => import('./components/WorkflowDashboard.jsx'));
const ReviewerConsole = lazy(() => import('./components/ReviewerConsole.jsx'));
const Settings = lazy(() => import('./components/Settings.jsx'));
const Auth = lazy(() => import('./components/Auth.jsx'));
const MarkdownMessage = lazy(() => import('./components/MarkdownMessage.jsx'));

function PanelFallback() {
  return <div className="panel-loading" role="status" aria-live="polite" aria-busy="true">Loading workspace…</div>;
}

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'https://businessrag.onrender.com';
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const SESSION_STORAGE_KEYS = [
  'bizguide_profile',
  'bizguide_notifications',
  'bizguide_accent',
  'bizguide_api_url',
];

const QUICK_ACTIONS = [
  { icon: <Building2 size={24} />, title: 'Company Registration', desc: 'Steps to incorporate a Pvt Ltd', query: 'What are the steps to register a Private Limited Company in India?' },
  { icon: <UtensilsCrossed size={24} />, title: 'FSSAI License',        desc: 'Get your food business permits',  query: 'How do I apply for FSSAI food license in India?' },
  { icon: <Rocket size={24} />, title: 'Startup India',         desc: 'Tax exemptions and funding',      query: 'What are the benefits of Startup India DPIIT recognition?' },
  { icon: <BarChart3 size={24} />, title: 'GST Registration',      desc: 'Register for GST online',         query: 'How do I register for GST for my business in India?' },
  { icon: <Wallet size={24} />, title: 'Income Tax Filing',     desc: 'ITR for businesses',              query: 'What are the income tax filing requirements for a Private Limited Company?' },
  { icon: <Scale size={24} />, title: 'LLP Formation',        desc: 'Set up an LLP',                  query: 'How do I form a Limited Liability Partnership (LLP) in India?' },
];

function generateTitle(firstMessage) {
  if (!firstMessage) return 'New Conversation';
  const words = firstMessage.trim().split(' ').slice(0, 6).join(' ');
  return words.length < firstMessage.trim().length ? words + '…' : words;
}

async function readApiResponse(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

async function readChatStream(response, onUpdate) {
  if (!response.body) throw new Error('Streaming is not available in this browser.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const result = { answer: '', citations: [], context_used: null, grounding: 'general', agent_type: 'General Agent' };

  const consumeEvent = (rawEvent) => {
    const lines = rawEvent.split(/\r?\n/);
    let eventName = 'message';
    let data = '';
    lines.forEach(line => {
      if (line.startsWith('event:')) eventName = line.slice(6).trim();
      if (line.startsWith('data:')) data += line.slice(5).trim();
    });
    if (!data) return;
    let payload = {};
    try { payload = JSON.parse(data); } catch { return; }
    if (eventName === 'meta' || eventName === 'result') {
      Object.assign(result, payload);
      if (eventName === 'result') onUpdate({ ...result });
    } else if (eventName === 'token') {
      result.answer += payload.text || '';
      onUpdate({ ...result });
    } else if (eventName === 'error') {
      const error = new Error(payload.detail || 'We could not generate an answer.');
      error.requestId = payload.request_id;
      error.status = payload.status_code;
      throw error;
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() || '';
    events.forEach(consumeEvent);
    if (done) break;
  }
  if (buffer.trim()) consumeEvent(buffer);
  if (!result.answer.trim()) throw new Error('The response stream ended without an answer.');
  return result;
}

function getApiError(data, response, fallback) {
  const requestId = data?.request_id || response?.headers?.get('X-Request-ID');
  const detail = typeof data?.detail === 'string' ? data.detail : fallback;
  return { detail, requestId };
}

const RETRYABLE_CHAT_STATUSES = new Set([408, 425, 429, 500, 502, 503, 504]);

function isTransientChatError(error) {
  if (Number.isFinite(error?.status)) return RETRYABLE_CHAT_STATUSES.has(error.status);
  return /load failed|failed to fetch|network|timeout|response stream/i.test(String(error?.message || '').toLowerCase());
}

function userFacingChatError(error) {
  const message = String(error?.message || '');
  if (!error?.status && /load failed|failed to fetch|network|timeout/i.test(message.toLowerCase())) {
    return 'The chat service was temporarily unreachable. We retried once; please try again.';
  }
  return message || 'We could not generate an answer. Please try again.';
}

async function requestChatResponse({ apiUrl, accessToken, requestBody, onStreamUpdate, onRetry }) {
  let lastError;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      let response = await fetch(`${apiUrl}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: requestBody,
      });
      let data;
      let usedStreaming = false;

      if (response.status === 404 || response.status === 405) {
        // Keep the public beta compatible with an older backend during rollout.
        response = await fetch(`${apiUrl}/api/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: requestBody,
        });
        data = await readApiResponse(response);
      } else if (response.ok) {
        usedStreaming = true;
        data = await readChatStream(response, onStreamUpdate);
      } else {
        data = await readApiResponse(response);
      }

      if (!response.ok) {
        const { detail, requestId } = getApiError(data, response, 'We could not generate an answer.');
        const error = new Error(detail);
        error.requestId = requestId;
        error.status = response.status;
        throw error;
      }
      return { data, usedStreaming };
    } catch (error) {
      lastError = error;
      if (attempt === 1 || !isTransientChatError(error)) throw error;
      onRetry?.(attempt + 1, error);
      await new Promise(resolve => window.setTimeout(resolve, 800));
    }
  }
  throw lastError || new Error('We could not generate an answer.');
}

/** Fire a real browser notification if permission granted and page is not focused */
function fireNotification(title, body) {
  if (typeof Notification === 'undefined') return;
  if (Notification.permission !== 'granted') return;
  if (document.visibilityState === 'visible' && document.hasFocus()) return;
  try {
    new Notification(title, { body, icon: '/logo.png', badge: '/logo.png' });
  } catch {}
}

function App() {
  const [currentView, setCurrentView]     = useState('home');
  const [messages, setMessages]           = useState([]);
  const [input, setInput]                 = useState('');
  const [answerLanguage, setAnswerLanguage] = useState('en');
  const [useBusinessContext, setUseBusinessContext] = useState(false);
  const [useDocumentContext, setUseDocumentContext] = useState(false);
  const [isTyping, setIsTyping]           = useState(false);
  const [isRetrying, setIsRetrying]       = useState(false);
  const [isUploading, setIsUploading]     = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId]   = useState(null);
  // Keep the desktop sidebar open, while starting compact navigation on phones.
  // This only affects presentation; navigation and application state stay the same.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches
  );
  const [apiUrl, setApiUrl]               = useState(DEFAULT_API_URL);
  const [session, setSession]             = useState(null);
  const [businesses, setBusinesses]       = useState([]);
  const [activeBusinessId, setActiveBusinessId] = useState(null);
  const [activeBusinessProfile, setActiveBusinessProfile] = useState(null);
  const [persistenceStatus, setPersistenceStatus] = useState('loading');
  const [persistenceMessage, setPersistenceMessage] = useState('');
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [reviewerRoles, setReviewerRoles] = useState([]);
  const [feedbackState, setFeedbackState] = useState({});
  const fileInputRef = useRef(null);
  const chatInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const currentConvIdRef = useRef(null);
  const sessionUserIdRef = useRef(null);

  useEffect(() => {
    captureEvent('app_loaded');
  }, []);

  useEffect(() => {
    captureEvent('workspace_viewed', { view: currentView });
  }, [currentView]);

  const resetClientState = useCallback((previousUserId = sessionUserIdRef.current) => {
    setMessages([]);
    setConversations([]);
    setBusinesses([]);
    setInput('');
    setUseBusinessContext(false);
    setUseDocumentContext(false);
    setIsRetrying(false);
    setActiveConvId(null);
    currentConvIdRef.current = null;
    setCurrentView('home');
    setApiUrl(DEFAULT_API_URL);
    setActiveBusinessId(null);
    setActiveBusinessProfile(null);
    if (previousUserId) {
      localStorage.removeItem(`bizguide_active_business:${previousUserId}`);
      localStorage.removeItem(`bizguide_active_business_profile:${previousUserId}`);
      SESSION_STORAGE_KEYS.forEach(key => localStorage.removeItem(`${key}:${previousUserId}`));
    }
    localStorage.removeItem('bizguide_active_business');
    SESSION_STORAGE_KEYS.forEach(key => localStorage.removeItem(key));
  }, []);

  const applySession = useCallback((nextSession) => {
    const nextUserId = nextSession?.user?.id || null;
    const previousUserId = sessionUserIdRef.current;
    if (previousUserId && previousUserId !== nextUserId) {
      resetClientState(previousUserId);
    }
    sessionUserIdRef.current = nextUserId;
    setSession(currentSession => {
      // Supabase may return a fresh session object for the same token. Avoid
      // turning that identity-only change into another auth bootstrap render.
      if (
        currentSession?.user?.id === nextSession?.user?.id &&
        currentSession?.access_token === nextSession?.access_token &&
        currentSession?.refresh_token === nextSession?.refresh_token &&
        currentSession?.expires_at === nextSession?.expires_at
      ) {
        return currentSession;
      }
      return nextSession;
    });
  }, [resetClientState]);

  // Supabase Auth Listener
  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data: { session: nextSession } }) => {
      if (!active) return;
      applySession(nextSession);
      setIsAuthLoading(false);
    }).catch(() => {
      if (!active) return;
      applySession(null);
      setIsAuthLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      applySession(nextSession);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [applySession]);

  // Load normalized core data + settings. The legacy user_data row is used
  // only once by ensureCoreCutover(), never as a live write target.
  useEffect(() => {
    const userId = session?.user?.id;
    if (!userId) return;
    let cancelled = false;

    const savedUrl = localStorage.getItem(`bizguide_api_url:${userId}`);
    if (savedUrl) setApiUrl(savedUrl);
    
    setPersistenceStatus('loading');
    setPersistenceMessage('');
    ensureCoreCutover(userId)
      .then(async result => {
        if (cancelled || sessionUserIdRef.current !== userId) return;
        if (!result.ready) {
          setPersistenceStatus('unavailable');
          setPersistenceMessage(result.error?.message || 'Apply the core Supabase migration before using saved workspace data.');
          setConversations([]);
          setBusinesses([]);
          return;
        }
        const [nextConversations, nextBusinesses] = await Promise.all([listConversations(), listBusinesses()]);
        if (cancelled || sessionUserIdRef.current !== userId) return;
        setConversations(nextConversations);
        setBusinesses(nextBusinesses);
        setPersistenceStatus('ready');
        setPersistenceMessage(result.migrated ? 'Your workspace was moved to the secured core data model. Legacy checklist state was not imported.' : '');
      })
      .catch(error => {
        if (cancelled) return;
        setPersistenceStatus('unavailable');
        setPersistenceMessage(error.message || 'Apply the core Supabase migration before using saved workspace data.');
        setConversations([]);
        setBusinesses([]);
      });

    const savedAccent = localStorage.getItem(`bizguide_accent:${userId}`);
    if (savedAccent) {
      const ACCENT_COLORS = [
        { primary: '#9f3f29', secondary: '#7f321f' },
        { primary: '#52634d', secondary: '#394737' },
        { primary: '#8a5c18', secondary: '#684511' },
        { primary: '#8f4650', secondary: '#6d333c' },
      ];
      const idx = parseInt(savedAccent, 10);
      const palette = ACCENT_COLORS[idx] || ACCENT_COLORS[0];
      document.documentElement.style.setProperty('--color-accent', palette.primary);
      document.documentElement.style.setProperty('--color-accent-strong', palette.secondary);
      document.documentElement.style.setProperty('--color-accent-soft', `${palette.primary}1f`);
      document.documentElement.style.setProperty('--accent-primary', palette.primary);
      document.documentElement.style.setProperty('--accent-secondary', palette.secondary);
    }
    return () => { cancelled = true; };
  }, [session?.user?.id]);

  useEffect(() => {
    if (!session?.access_token) { setReviewerRoles([]); return; }
    let cancelled = false;
    fetch(`${apiUrl}/api/review/me`, { headers: { Authorization: `Bearer ${session.access_token}` } })
      .then(readApiResponse)
      .then(data => { if (!cancelled) setReviewerRoles(Array.isArray(data.roles) ? data.roles : []); })
      .catch(() => { if (!cancelled) setReviewerRoles([]); });
    return () => { cancelled = true; };
  }, [apiUrl, session?.access_token]);

  useEffect(() => {
    const userId = session?.user?.id;
    if (!userId) {
      setActiveBusinessId(null);
      setActiveBusinessProfile(null);
      return;
    }
    const userKey = `bizguide_active_business:${userId}`;
    const profileKey = `bizguide_active_business_profile:${userId}`;
    const legacyKey = 'bizguide_active_business';
    const legacyValue = localStorage.getItem(legacyKey);
    const savedValue = localStorage.getItem(userKey) || legacyValue;
    let savedProfile = null;
    try {
      savedProfile = JSON.parse(localStorage.getItem(profileKey) || 'null');
    } catch {
      savedProfile = null;
    }
    if (savedValue && !localStorage.getItem(userKey)) localStorage.setItem(userKey, savedValue);
    localStorage.removeItem(legacyKey);
    const storedBusiness = businesses.find(business => business.id === savedValue);
    setActiveBusinessId(savedValue || null);
    setActiveBusinessProfile(storedBusiness || savedProfile);
  }, [businesses, session?.user?.id]);

  // Auto-scroll to bottom when messages change
  const scrollFrameRef = useRef(null);
  useEffect(() => {
    if (typeof window === 'undefined' || scrollFrameRef.current !== null) return;
    scrollFrameRef.current = window.requestAnimationFrame(() => {
      scrollFrameRef.current = null;
      messagesEndRef.current?.scrollIntoView({ behavior: isTyping ? 'auto' : 'smooth', block: 'end' });
    });
  }, [messages, isTyping]);

  useEffect(() => () => {
    if (typeof window !== 'undefined' && scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current);
    }
  }, []);

  useEffect(() => {
    const inputElement = chatInputRef.current;
    if (!inputElement) return;
    inputElement.style.height = 'auto';
    inputElement.style.height = `${Math.min(inputElement.scrollHeight, 152)}px`;
  }, [input]);

  const saveConversations = useCallback((updated) => {
    setConversations(updated);
  }, []);

  const handleSelectBusiness = useCallback((businessId, profile = null) => {
    setActiveBusinessId(businessId || null);
    setActiveBusinessProfile(profile || null);
    if (session?.user?.id) {
      const userKey = `bizguide_active_business:${session.user.id}`;
      const profileKey = `bizguide_active_business_profile:${session.user.id}`;
      if (businessId) localStorage.setItem(userKey, businessId);
      else localStorage.removeItem(userKey);
      if (profile) localStorage.setItem(profileKey, JSON.stringify(profile));
      else localStorage.removeItem(profileKey);
    }
    if (businessId) captureEvent('business_selected');
  }, [session]);

  const handleBusinessesChange = useCallback((updated) => {
    const userId = session?.user?.id;
    if (!userId) return;
    const previous = businesses;
    setBusinesses(updated);
    const nextIds = new Set(updated.map(business => business.id));
    Promise.all([
      ...updated.map(business => saveBusiness(business, userId)),
      ...previous.filter(business => !nextIds.has(business.id)).map(business => deleteBusiness(business.id)),
    ]).then(async () => {
      const refreshed = await listBusinesses();
      setBusinesses(refreshed);
      const selected = refreshed.find(business => business.id === activeBusinessId);
      if (selected) handleSelectBusiness(selected.id, selected);
      setPersistenceStatus('ready');
    }).catch(error => {
      setPersistenceStatus('unavailable');
      setPersistenceMessage(error.message || 'The business profile could not be saved.');
    });
  }, [activeBusinessId, businesses, handleSelectBusiness, session?.user?.id]);

  const handleComplianceProfileUpdated = useCallback((businessId, profile) => {
    const patch = {
      regulatedActivities: profile.regulated_activities ?? null,
      gstRegistrationStatus: profile.gst_registration_status ?? null,
      gstScheme: profile.gst_scheme ?? null,
      incorporationStage: profile.incorporation_stage ?? null,
      turnoverBand: profile.turnover_band ?? null,
      employeeCountBand: profile.employee_count_band ?? null,
      hasPhysicalEstablishment: profile.has_physical_establishment ?? null,
      premisesStatus: profile.premises_status ?? null,
      usesContractors: profile.uses_contractors ?? null,
      handlesPersonalData: profile.handles_personal_data ?? null,
      operatingStateCodes: profile.operating_state_codes ?? null,
      operatesMultipleStates: profile.operates_multiple_states ?? null,
      importsGoodsServices: profile.imports_goods_services ?? null,
      exportsGoodsServices: profile.exports_goods_services ?? null,
      complianceAnswers: profile.answers || {},
      complianceDateAnswers: profile.date_answers || {},
      complianceProfileVersion: profile.profile_version || 2,
    };
    setBusinesses(current => current.map(business => business.id === businessId ? { ...business, ...patch } : business));
    setActiveBusinessProfile(current => current?.id === businessId ? { ...current, ...patch } : current);
  }, []);

  // Save current messages to the active conversation
  const persistCurrentConv = useCallback((msgs, convId) => {
    if (!convId || msgs.length === 0) return;
    const userId = session?.user?.id;
    setConversations(prev => {
      const existing = prev.find(c => c.id === convId);
      let updated;
      if (existing) {
        updated = prev.map(c =>
          c.id === convId
            ? { ...c, messages: msgs, title: generateTitle(msgs[0]?.content) }
            : c
        );
      } else {
        const newConv = {
          id: convId,
          title: generateTitle(msgs[0]?.content),
          messages: msgs,
          date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
          businessId: activeBusinessId,
        };
        updated = [newConv, ...prev];
      }
      const conversation = updated.find(item => item.id === convId);
      if (userId && conversation) {
        saveConversation({ ...conversation, businessId: conversation.businessId || activeBusinessId }, userId)
          .catch(error => {
            setPersistenceStatus('unavailable');
            setPersistenceMessage(error.message || 'Conversation history could not be saved.');
          });
      }
      return updated;
    });
  }, [activeBusinessId, session?.user?.id]);

  const handleSend = async (query) => {
    if (!query.trim() || isTyping || isUploading) return;

    const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now();
    captureEvent('chat_submitted', {
      has_active_business: Boolean(activeBusinessId),
      use_business_context: useBusinessContext && Boolean(activeBusinessId),
      use_document_context: useDocumentContext,
      history_count: Math.min(messages.length, 12),
      input_length: lengthBucket(query),
    });

    // Switch to home/chat view when sending a message
    setCurrentView('home');

    const userMsg = { role: 'user', content: query };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput('');
    setIsTyping(true);

    // Create a conversation ID if none exists
    if (!currentConvIdRef.current) {
      currentConvIdRef.current = newUuid();
      setActiveConvId(currentConvIdRef.current);
    }

    try {
      const history = messages
        .slice(-12)
        .map(message => ({
          role: message.role === 'ai' ? 'assistant' : message.role,
          content: String(message.content || '').slice(0, 6000),
        }))
        .filter(message => (message.role === 'user' || message.role === 'assistant') && message.content);
      const requestBody = JSON.stringify({
        query,
        conversation_id: currentConvIdRef.current,
        business_id: useBusinessContext ? activeBusinessId : null,
        use_business_context: useBusinessContext && Boolean(activeBusinessId),
        use_document_context: useDocumentContext,
        language: answerLanguage,
        history,
      });
      const { data, usedStreaming } = await requestChatResponse({
        apiUrl,
        accessToken: session.access_token,
        requestBody,
        onRetry: () => {
          setIsRetrying(true);
          captureEvent('chat_retry');
        },
        onStreamUpdate: streamed => {
          setMessages([...updatedMessages, {
            role: 'ai',
            content: streamed.answer,
            citations: streamed.citations || [],
            contextUsed: Array.isArray(streamed.context_used) ? streamed.context_used : null,
            grounding: streamed.grounding || 'general',
            agentType: streamed.agent_type || 'General Agent',
            schemaVersion: streamed.schema_version || 1,
            answerMode: streamed.answer_mode,
            evidenceStatus: streamed.evidence_status,
            language: streamed.language || answerLanguage,
            assumptions: streamed.assumptions || [],
            missingInputs: streamed.missing_inputs || [],
            conflicts: streamed.conflicts || [],
            coverage: streamed.coverage || {},
            effectiveDate: streamed.effective_date,
            profileVersion: streamed.profile_version,
            escalation: streamed.escalation,
          }]);
        },
      });
      
      const aiMsg = {
        role: 'ai',
        content: data.answer || 'No response received',
        citations: Array.isArray(data.citations) ? data.citations : [],
        contextUsed: Array.isArray(data.context_used) ? data.context_used : null,
        grounding: data.grounding || 'general',
        agentType: data.agent_type || 'General Agent',
        schemaVersion: data.schema_version || 1,
        answerMode: data.answer_mode,
        evidenceStatus: data.evidence_status,
        language: data.language || answerLanguage,
        assumptions: data.assumptions || [],
        missingInputs: data.missing_inputs || [],
        conflicts: data.conflicts || [],
        coverage: data.coverage || {},
        effectiveDate: data.effective_date,
        profileVersion: data.profile_version,
        escalation: data.escalation,
      };
      const finalMessages = [...updatedMessages, aiMsg];
      setMessages(finalMessages);
      persistCurrentConv(finalMessages, currentConvIdRef.current);
      captureEvent('chat_completed', {
        grounding: aiMsg.grounding,
        citation_count: aiMsg.citations.length,
        streamed: usedStreaming,
        duration: durationBucket((typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt),
      });
      // Fire browser notification if page is hidden
      fireNotification('BizGuide', 'Your answer is ready!');
    } catch (error) {
      captureException(error, { source: 'chat_request' });
      captureEvent('chat_failed', { has_request_id: Boolean(error.requestId) });
      const requestId = error.requestId ? `\n\nReference: \`${error.requestId}\`` : '';
      const errMsg = {
        role: 'ai',
        content: `⚠️ ${userFacingChatError(error)}${requestId}`,
        retryQuery: query,
      };
      const finalMessages = [...updatedMessages, errMsg];
      setMessages(finalMessages);
      persistCurrentConv(finalMessages, currentConvIdRef.current);
    } finally {
      setIsTyping(false);
      setIsRetrying(false);
    }
  };

  const submitAnswerFeedback = async (message, index, rating, reasonCode = null) => {
    const key = message.id || `${activeConvId || 'current'}:${index}`;
    if (feedbackState[key] === 'saving' || feedbackState[key] === 'saved') return;
    setFeedbackState(current => ({ ...current, [key]: 'saving' }));
    try {
      const evidenceIds = (message.citations || []).map(citation => citation.evidence_id).filter(Boolean);
      const response = await fetch(`${apiUrl}/api/answers/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.access_token}` },
        body: JSON.stringify({
          conversation_id: activeConvId || null,
          message_id: message.id || null,
          rating,
          reason_code: reasonCode,
          answer_status: message.evidenceStatus || 'general_guidance',
          evidence_ids: evidenceIds,
        }),
      });
      const data = await readApiResponse(response);
      if (!response.ok) throw new Error(data.detail || 'Feedback could not be saved.');
      setFeedbackState(current => ({ ...current, [key]: 'saved' }));
    } catch (error) {
      captureException(error, { source: 'answer_feedback' });
      setFeedbackState(current => ({ ...current, [key]: 'error' }));
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      captureEvent('upload_rejected', { reason: 'file_type' });
      setMessages(prev => [...prev, { role: 'ai', content: '⚠️ Please choose a PDF file.' }]);
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      captureEvent('upload_rejected', { reason: 'file_size', size: sizeBucket(file.size) });
      setMessages(prev => [...prev, { role: 'ai', content: '⚠️ This PDF is larger than the 50MB upload limit.' }]);
      return;
    }

    setCurrentView('home');
    setIsUploading(true);
    captureEvent('upload_started', { size: sizeBucket(file.size), has_active_business: Boolean(activeBusinessId) });
    const uploadMsg = { role: 'user', content: `📎 Uploading **${file.name}**…` };
    const updatedMessages = [...messages, uploadMsg];
    setMessages(updatedMessages);

    const formData = new FormData();
    formData.append('file', file);
    if (activeBusinessId) formData.append('business_id', activeBusinessId);

    try {
      // Upload with Authorization token for user isolation
      const uploadUrl = `${apiUrl}/api/documents/upload`;
      const idempotencyKey = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const response = await fetch(uploadUrl, { 
        method: 'POST', 
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'X-Idempotency-Key': idempotencyKey,
        },
        body: formData 
      });
      const data = await readApiResponse(response);
      const resultMsg = response.ok
        ? { role: 'ai', content: `✅ **${data.status === 'indexed' ? 'Upload complete.' : 'Upload queued.'}** ${data.message}\n\n${data.status === 'indexed' ? 'You can now ask questions that use this document as context.' : 'Processing continues in the background. Open Source Library to monitor progress.'} Always verify important legal and tax decisions against the original source or a qualified professional.` }
        : (() => {
            const { detail, requestId } = getApiError(data, response, 'We could not process this PDF.');
            return { role: 'ai', content: `❌ **Upload failed:** ${detail}${requestId ? `\n\nReference: \`${requestId}\`` : ''}` };
          })();
      const finalMessages = [...updatedMessages, resultMsg];
      setMessages(finalMessages);
      persistCurrentConv(finalMessages, currentConvIdRef.current);
      if (response.ok) {
        captureEvent(data.status === 'indexed' ? 'upload_indexed' : 'upload_queued');
        fireNotification('BizGuide', data.status === 'indexed' ? `${file.name} uploaded and indexed successfully!` : `${file.name} is queued for processing.`);
      }
      else captureEvent('upload_failed', { status: response.status });
    } catch (error) {
      captureException(error, { source: 'chat_upload' });
      captureEvent('upload_failed', { reason: 'network' });
      const errMsg = { role: 'ai', content: '⚠️ Network error during upload. Please try again.' };
      const finalMessages = [...updatedMessages, errMsg];
      setMessages(finalMessages);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleNewChat = () => {
    if (messages.length > 0 && currentConvIdRef.current) {
      persistCurrentConv(messages, currentConvIdRef.current);
    }
    setMessages([]);
    currentConvIdRef.current = null;
    setActiveConvId(null);
    setCurrentView('home');
  };

  const handleSelectConversation = (convId) => {
    const conv = conversations.find(c => c.id === convId);
    if (conv) {
      if (messages.length > 0 && currentConvIdRef.current) {
        persistCurrentConv(messages, currentConvIdRef.current);
      }
      setMessages(conv.messages || []);
      currentConvIdRef.current = convId;
      setActiveConvId(convId);
      setCurrentView('home');
      if (typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches) {
        setSidebarCollapsed(true);
      }
    }
  };

  const handleDeleteConversation = (convId) => {
    const updated = conversations.filter(c => c.id !== convId);
    saveConversations(updated);
    deleteConversation(convId).catch(error => {
      setPersistenceStatus('unavailable');
      setPersistenceMessage(error.message || 'Conversation history could not be deleted.');
    });
    if (activeConvId === convId) {
      setMessages([]);
      currentConvIdRef.current = null;
      setActiveConvId(null);
    }
  };

  const handleClearAllHistory = () => {
    saveConversations([]);
    deleteAllConversations().catch(error => {
      setPersistenceStatus('unavailable');
      setPersistenceMessage(error.message || 'Conversation history could not be cleared.');
    });
    setMessages([]);
    currentConvIdRef.current = null;
    setActiveConvId(null);
  };

  // Navigate to chat with a pre-filled query from other panels
  const handleAskQuestion = (query) => {
    setCurrentView('home');
    setTimeout(() => handleSend(query), 100);
  };

  const handleSignOut = async () => {
    resetClientState();
    await supabase.auth.signOut();
  };

  const chatBusinessIncluded = useBusinessContext && Boolean(activeBusinessId);
  const chatWorkspaceLabel = chatBusinessIncluded && activeBusinessProfile?.name
    ? activeBusinessProfile.name
    : 'Personal workspace';
  const chatWorkspaceTitle = chatBusinessIncluded
    ? 'Business context is included for this question'
    : 'Business context is off; this question uses Gemini independently';
  const chatComposerLabel = chatBusinessIncluded && activeBusinessProfile?.name
    ? activeBusinessProfile.name
    : useDocumentContext
      ? 'Selected documents'
      : 'Gemini by default';

  if (isAuthLoading) {
    return <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center', color: 'white' }}>Loading...</div>;
  }

  if (!session) {
    return <Suspense fallback={<PanelFallback />}><Auth /></Suspense>;
  }

  return (
    <div className="app-container">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <Sidebar
        currentView={currentView}
        setCurrentView={setCurrentView}
        onNewChat={handleNewChat}
        conversations={conversations}
        onSelectConversation={handleSelectConversation}
        activeConversationId={activeConvId}
        onDeleteConversation={handleDeleteConversation}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(prev => !prev)}
        session={session}
        onSignOut={handleSignOut}
        isReviewer={reviewerRoles.length > 0}
      />

      <main id="main-content" className="main-content" tabIndex="-1">
        {persistenceMessage && (
          <div className={`persistence-banner ${persistenceStatus === 'unavailable' ? 'error' : 'notice'}`} role={persistenceStatus === 'unavailable' ? 'alert' : 'status'}>
            <span>{persistenceMessage}</span>
            {persistenceStatus === 'unavailable' && <button type="button" className="persistence-retry" onClick={() => window.location.reload()}>Reload after migration</button>}
          </div>
        )}
        <AnimatePresence mode="wait">
          {currentView === 'home' ? (
            <motion.div
              key="home"
              className="home-view"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className="chat-container">
                {messages.length === 0 ? (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    className="hero-section"
                  >
                    <div className="hero-shell">
                      <div className="hero-topline" aria-label="Workspace status">
                        <span className="hero-status-dot" aria-hidden="true" />
                        <span>Source-first workspace</span>
                        <span className="hero-topline-divider" aria-hidden="true" />
                        <span className="hero-topline-context">{chatWorkspaceLabel}</span>
                      </div>
                      <div className="hero-copy">
                        <div className="hero-badge">Guided by your business context and sources</div>
                        <h1 className="hero-title">
                          What do you need to<br />
                          <span className="gradient-text">verify today?</span>
                        </h1>
                        <p className="hero-subtitle">
                          <span className="hero-subtitle-desktop">Ask a question, review an obligation, or work from your own documents. BizGuide will show the evidence and coverage limits behind each answer.</span>
                          <span className="hero-subtitle-mobile">Ask anything with Gemini. Turn on Business or Documents below when you want context included.</span>
                          <span className="hero-mobile-disclaimer">Verify important decisions against the original source.</span>
                        </p>
                        <div className="hero-privacy-note">
                          <span className="hero-privacy-icon" aria-hidden="true">i</span>
                          Important legal and tax decisions should still be checked against the original source and a qualified professional.
                        </div>
                      </div>
                      <div className="hero-workbench-heading">
                        <div>
                          <span className="hero-section-kicker">Start with a workflow</span>
                          <h2>Common starting points</h2>
                        </div>
                        <span className="hero-workbench-note">Choose one to begin a sourced conversation</span>
                      </div>
                      <div className="quick-actions">
                        {QUICK_ACTIONS.map((qa) => (
                          <motion.button
                            key={qa.title}
                            type="button"
                            whileHover={{ y: -2 }}
                            whileTap={{ y: 0 }}
                            className="glass-panel action-card"
                            onClick={() => handleSend(qa.query)}
                            aria-label={`${qa.title}: ${qa.desc}`}
                          >
                            <div className="action-icon">{qa.icon}</div>
                            <div className="action-copy">
                              <div className="action-title">{qa.title}</div>
                              <div className="action-desc">{qa.desc}</div>
                            </div>
                            <span className="action-arrow" aria-hidden="true">↗</span>
                          </motion.button>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                ) : (
                  <div className="messages-list">
                    <AnimatePresence>
                      {messages.map((msg, idx) => (
                        <motion.div
                          key={idx}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.3 }}
                          className={`message-bubble ${msg.role === 'user' ? 'message-user' : 'message-ai'}`}
                        >
                          {msg.role === 'ai' ? (
                            <>
                              <div className="ai-label">
                                <span className="ai-dot" />
                                BizGuide
                              </div>
                              <Suspense fallback={<div className="markdown-fallback">{msg.content}</div>}>
                                <MarkdownMessage content={msg.content} />
                              </Suspense>
                              {msg.evidenceStatus && (
                                <div className={`evidence-status status-${msg.evidenceStatus.replaceAll('_', '-')}`} role="status">
                                  {msg.evidenceStatus === 'verified' ? 'Verified from reviewed official evidence' : msg.evidenceStatus === 'cannot_verify' ? 'Cannot verify from the reviewed catalog' : msg.evidenceStatus.replaceAll('_', ' ')}
                                  {msg.effectiveDate && <span> · as of {msg.effectiveDate}</span>}
                                </div>
                              )}
                              {Array.isArray(msg.contextUsed) && (
                                <div className="answer-context" role="status">
                                  {msg.contextUsed.length > 0
                                    ? `Context used: ${msg.contextUsed.map(context => context === 'business' ? 'business profile' : 'uploaded documents').join(' + ')}`
                                    : 'Answered independently by Gemini — no business or document context used'}
                                </div>
                              )}
                              {msg.missingInputs?.length > 0 && (
                                <div className="grounding-warning" role="status"><strong>Missing inputs:</strong> {msg.missingInputs.join(', ')}</div>
                              )}
                              {msg.conflicts?.length > 0 && (
                                <div className="workflow-alert" role="alert"><strong>Evidence conflict:</strong> {msg.conflicts.join(' ')}</div>
                              )}
                              {msg.citations?.length > 0 && (
                                <div className="citation-list" aria-label="Answer evidence">
                                  <div className="citation-heading">{msg.citations.some(citation => citation.source_kind === 'official') ? 'Reviewed official evidence' : 'Sources from your documents (private evidence)'}</div>
                                  <ol>
                                    {msg.citations.map((citation, citationIndex) => (
                                      <li key={`${citation.evidence_id || citation.document_id || citationIndex}-${citation.page_number || citationIndex}`}>
                                        <div className="citation-meta">
                                          {citation.url ? <a href={citation.url} target="_blank" rel="noreferrer">{citation.title || citation.authority || 'Official source'}</a> : <span>{citation.file_name || 'Uploaded document'}</span>}
                                          {citation.authority && citation.title !== citation.authority && <span> · {citation.authority}</span>}
                                          {citation.anchor && <span> · {citation.anchor}</span>}
                                          {citation.page_number && <span> · page {citation.page_number}</span>}
                                        </div>
                                        <div className="citation-snippet">“{citation.snippet}”</div>
                                        {citation.last_checked_at && <div className="citation-freshness">Last checked {new Date(citation.last_checked_at).toLocaleDateString('en-IN')} · tier {citation.source_tier}</div>}
                                      </li>
                                    ))}
                                  </ol>
                                </div>
                              )}
                              {msg.escalation && (
                                <div className="escalation-brief">
                                  <strong>Professional brief: {msg.escalation.recommended_role}</strong>
                                  <p>{msg.escalation.reason}</p>
                                  {msg.escalation.briefing?.length > 0 && <ul>{msg.escalation.briefing.map(item => <li key={item}>{item}</li>)}</ul>}
                                </div>
                              )}
                              {msg.grounding === 'insufficient' && (
                                <p className="grounding-warning" role="status">
                                  Retrieved document context is missing source metadata. Treat this answer as unverified and check the original file.
                                </p>
                              )}
                              {msg.retryQuery && (
                                <button className="retry-message-button" onClick={() => handleSend(msg.retryQuery)}>
                                  Try again
                                </button>
                              )}
                              <p className="answer-disclaimer">{msg.evidenceStatus === 'verified' ? 'The answer is limited to the cited evidence, effective date, confirmed profile facts, and disclosed coverage.' : msg.evidenceStatus === 'general_guidance' ? 'This is general Gemini guidance. Verify current legal or tax specifics against an official source or qualified professional.' : 'This answer is not a verified legal or tax conclusion. Coverage limits and missing evidence are shown above.'}</p>
                              {msg.evidenceStatus && (() => {
                                const feedbackKey = msg.id || `${activeConvId || 'current'}:${idx}`;
                                const feedbackStatus = feedbackState[feedbackKey];
                                return (
                                  <div className="answer-feedback" aria-label="Answer feedback">
                                    <span>{feedbackStatus === 'saved' ? 'Feedback recorded' : feedbackStatus === 'error' ? 'Feedback could not be saved' : 'Was this answer useful?'}</span>
                                    <button type="button" className="btn-ghost" onClick={() => submitAnswerFeedback(msg, idx, 'helpful')} disabled={feedbackStatus === 'saving' || feedbackStatus === 'saved'}><ThumbsUp size={14} /> Helpful</button>
                                    <button type="button" className="btn-ghost" onClick={() => submitAnswerFeedback(msg, idx, 'report', 'incorrect')} disabled={feedbackStatus === 'saving' || feedbackStatus === 'saved'}><Flag size={14} /> Report</button>
                                  </div>
                                );
                              })()}
                            </>
                          ) : (
                            <span>{msg.content}</span>
                          )}
                        </motion.div>
                      ))}

                      {(isTyping || isUploading) && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="message-bubble message-ai"
                        >
                          <div className="ai-label"><span className="ai-dot pulsing" /> BizGuide</div>
                          <div className="typing-indicator" role="status" aria-live="polite">
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0 }} className="typing-dot" />
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0.2 }} className="typing-dot" />
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0.4 }} className="typing-dot" />
                            <span className="typing-text">
                              {isUploading ? 'Processing document and creating embeddings…' : isRetrying ? 'Retrying the chat service…' : 'Preparing your response…'}
                            </span>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              {/* Input Area */}
              <div className="input-container">
                  <div className="composer-context">
                    <div className="composer-workspace" title={chatWorkspaceTitle}>
                      <span className={`composer-status-dot ${chatBusinessIncluded ? 'included' : 'independent'}`} aria-hidden="true" />
                      <span>{chatComposerLabel}</span>
                    </div>
                    <div className="language-switch" aria-label="Answer language">
                      <button type="button" className={answerLanguage === 'en' ? 'active' : ''} aria-pressed={answerLanguage === 'en'} onClick={() => setAnswerLanguage('en')}>English</button>
                      <button type="button" className={answerLanguage === 'hi' ? 'active' : ''} aria-pressed={answerLanguage === 'hi'} onClick={() => setAnswerLanguage('hi')}>हिन्दी</button>
                    </div>
                    <div className="composer-options" aria-label="Optional answer context">
                      <span className="composer-options-label">Include</span>
                      <button
                        type="button"
                        className={`context-toggle ${useBusinessContext ? 'active' : ''}`}
                        aria-pressed={useBusinessContext}
                        disabled={!activeBusinessId || isTyping || isUploading}
                        title={activeBusinessId ? 'Use the selected business profile for this question' : 'Select a business to enable business context'}
                        onClick={() => setUseBusinessContext(current => !current)}
                      >
                        <Building2 size={14} aria-hidden="true" />
                        <span>Business</span>
                      </button>
                      <button
                        type="button"
                        className={`context-toggle ${useDocumentContext ? 'active' : ''}`}
                        aria-pressed={useDocumentContext}
                        disabled={isTyping || isUploading}
                        title="Use relevant uploaded documents for this question"
                        onClick={() => setUseDocumentContext(current => !current)}
                      >
                        <Paperclip size={14} aria-hidden="true" />
                        <span>Documents</span>
                      </button>
                    </div>
                  </div>
                <div className="chat-input-wrapper">
                  <button
                    className="upload-button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading || isTyping}
                    title="Upload PDF Document"
                    aria-label="Upload PDF document"
                  >
                    <Paperclip size={20} />
                  </button>
                  <input
                    type="file"
                    accept=".pdf"
                    style={{ display: 'none' }}
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                  />
                  <textarea
                    ref={chatInputRef}
                    rows="1"
                    className="chat-input"
                    aria-label="Ask BizGuide a question"
                    placeholder="Ask a question…"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey && input.trim() && !isTyping && !isUploading) {
                        e.preventDefault();
                        handleSend(input);
                      }
                    }}
                    disabled={isUploading || isTyping}
                  />
                  <motion.button
                    whileHover={input.trim() && !isTyping && !isUploading ? { y: -1 } : {}}
                    whileTap={input.trim() && !isTyping && !isUploading ? { y: 0 } : {}}
                    className="send-button"
                    onClick={() => handleSend(input)}
                    disabled={!input.trim() || isTyping || isUploading}
                    aria-label="Send message"
                  >
                    <Send size={20} />
                  </motion.button>
                </div>
              </div>
            </motion.div>
          ) : currentView === 'businesses' ? (
            <motion.div key="businesses" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <Suspense fallback={<PanelFallback />}>
                <MyBusinesses
                  session={session}
                  businesses={businesses}
                  onBusinessesChange={handleBusinessesChange}
                  onAskQuestion={handleAskQuestion}
                  activeBusinessId={activeBusinessId}
                  onSelectBusiness={handleSelectBusiness}
                />
              </Suspense>
            </motion.div>
          ) : currentView === 'upload' ? (
            <motion.div key="upload" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <Suspense fallback={<PanelFallback />}>
                <UploadDocuments session={session} apiUrl={apiUrl} businessId={activeBusinessId} />
              </Suspense>
            </motion.div>
          ) : currentView === 'workflow' ? (
            <motion.div key="workflow" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <Suspense fallback={<PanelFallback />}>
                <WorkflowDashboard
                  session={session}
                  apiUrl={apiUrl}
                  businesses={businesses}
                  activeBusinessId={activeBusinessId}
                  onSelectBusiness={handleSelectBusiness}
                  onGoToBusinesses={() => setCurrentView('businesses')}
                  onComplianceProfileUpdated={handleComplianceProfileUpdated}
                />
              </Suspense>
            </motion.div>
          ) : currentView === 'review' && reviewerRoles.length > 0 ? (
            <motion.div key="review" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <Suspense fallback={<PanelFallback />}><ReviewerConsole session={session} apiUrl={apiUrl} reviewerRoles={reviewerRoles} /></Suspense>
            </motion.div>
          ) : currentView === 'settings' ? (
            <motion.div key="settings" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <Suspense fallback={<PanelFallback />}>
                <Settings
                  session={session}
                  onClearHistory={handleClearAllHistory}
                  onApiUrlChange={setApiUrl}
                  currentApiUrl={apiUrl}
                />
              </Suspense>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </main>
    </div>
  );
}

export default App;
