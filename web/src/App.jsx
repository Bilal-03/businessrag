import React, { lazy, Suspense, useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, Building2, UtensilsCrossed, Rocket, BarChart3, Wallet, Scale } from 'lucide-react';
import Sidebar from './components/Sidebar';
import { supabase } from './lib/supabase';
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
const Settings = lazy(() => import('./components/Settings.jsx'));
const Auth = lazy(() => import('./components/Auth.jsx'));
const MarkdownMessage = lazy(() => import('./components/MarkdownMessage.jsx'));

function PanelFallback() {
  return <div className="panel-loading" role="status" aria-live="polite">Loading workspace…</div>;
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
  const result = { answer: '', citations: [], grounding: 'general', agent_type: 'General Agent' };

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
    if (eventName === 'meta') {
      Object.assign(result, payload);
    } else if (eventName === 'token') {
      result.answer += payload.text || '';
      onUpdate({ ...result });
    } else if (eventName === 'error') {
      const error = new Error(payload.detail || 'We could not generate an answer.');
      error.requestId = payload.request_id;
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
  const [isTyping, setIsTyping]           = useState(false);
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
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const currentConvIdRef = useRef(null);
  const sessionUserIdRef = useRef(null);

  const resetClientState = useCallback((previousUserId = sessionUserIdRef.current) => {
    setMessages([]);
    setConversations([]);
    setBusinesses([]);
    setInput('');
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
        { primary: '#6366f1', secondary: '#8b5cf6' },
        { primary: '#14b8a6', secondary: '#06b6d4' },
        { primary: '#f43f5e', secondary: '#ec4899' },
        { primary: '#f59e0b', secondary: '#f97316' },
        { primary: '#10b981', secondary: '#059669' },
        { primary: '#0ea5e9', secondary: '#6366f1' },
      ];
      const idx = parseInt(savedAccent, 10);
      if (ACCENT_COLORS[idx]) {
        document.documentElement.style.setProperty('--accent-primary', ACCENT_COLORS[idx].primary);
        document.documentElement.style.setProperty('--accent-secondary', ACCENT_COLORS[idx].secondary);
      }
    }
    return () => { cancelled = true; };
  }, [session?.user?.id]);

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
        business_id: activeBusinessId,
        history,
      });
      let response = await fetch(`${apiUrl}/api/chat/stream`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: requestBody,
      });
      let data;

      if (response.status === 404 || response.status === 405) {
        // Keep the public beta compatible with an older backend during rollout.
        response = await fetch(`${apiUrl}/api/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${session.access_token}`
          },
          body: requestBody,
        });
        data = await readApiResponse(response);
      } else if (response.ok) {
        data = await readChatStream(response, streamed => {
          setMessages([...updatedMessages, {
            role: 'ai',
            content: streamed.answer,
            citations: streamed.citations || [],
            grounding: streamed.grounding || 'general',
            agentType: streamed.agent_type || 'General Agent',
          }]);
        });
      } else {
        data = await readApiResponse(response);
      }
      
      if (!response.ok) {
        const { detail, requestId } = getApiError(data, response, 'We could not generate an answer.');
        const error = new Error(detail);
        error.requestId = requestId;
        throw error;
      }
      
      const aiMsg = {
        role: 'ai',
        content: data.answer || 'No response received',
        citations: Array.isArray(data.citations) ? data.citations : [],
        grounding: data.grounding || 'general',
        agentType: data.agent_type || 'General Agent',
      };
      const finalMessages = [...updatedMessages, aiMsg];
      setMessages(finalMessages);
      persistCurrentConv(finalMessages, currentConvIdRef.current);
      // Fire browser notification if page is hidden
      fireNotification('BizGuide AI', 'Your answer is ready!');
    } catch (error) {
      const requestId = error.requestId ? `\n\nReference: \`${error.requestId}\`` : '';
      const errMsg = {
        role: 'ai',
        content: `⚠️ ${error.message || 'We could not generate an answer. Please try again.'}${requestId}`,
        retryQuery: query,
      };
      const finalMessages = [...updatedMessages, errMsg];
      setMessages(finalMessages);
      persistCurrentConv(finalMessages, currentConvIdRef.current);
    } finally {
      setIsTyping(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setMessages(prev => [...prev, { role: 'ai', content: '⚠️ Please choose a PDF file.' }]);
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setMessages(prev => [...prev, { role: 'ai', content: '⚠️ This PDF is larger than the 50MB upload limit.' }]);
      return;
    }

    setCurrentView('home');
    setIsUploading(true);
    const uploadMsg = { role: 'user', content: `📎 Uploading **${file.name}**…` };
    const updatedMessages = [...messages, uploadMsg];
    setMessages(updatedMessages);

    const formData = new FormData();
    formData.append('file', file);
    if (activeBusinessId) formData.append('business_id', activeBusinessId);

    try {
      // Upload with Authorization token for user isolation
      const uploadUrl = `${apiUrl}/api/documents/upload`;
      const response = await fetch(uploadUrl, { 
        method: 'POST', 
        headers: {
          'Authorization': `Bearer ${session.access_token}`
        },
        body: formData 
      });
      const data = await readApiResponse(response);
      const resultMsg = response.ok
        ? { role: 'ai', content: `✅ **Upload complete.** ${data.message}\n\nYou can now ask questions that use this document as context. Always verify important legal and tax decisions against the original source or a qualified professional.` }
        : (() => {
            const { detail, requestId } = getApiError(data, response, 'We could not process this PDF.');
            return { role: 'ai', content: `❌ **Upload failed:** ${detail}${requestId ? `\n\nReference: \`${requestId}\`` : ''}` };
          })();
      const finalMessages = [...updatedMessages, resultMsg];
      setMessages(finalMessages);
      persistCurrentConv(finalMessages, currentConvIdRef.current);
      if (response.ok) {
        fireNotification('BizGuide AI', `${file.name} uploaded and indexed successfully!`);
      }
    } catch {
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

  if (isAuthLoading) {
    return <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center', color: 'white' }}>Loading...</div>;
  }

  if (!session) {
    return <Suspense fallback={<PanelFallback />}><Auth /></Suspense>;
  }

  return (
    <div className="app-container">
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
      />

      <main className="main-content">
        {persistenceMessage && (
          <div className={`persistence-banner ${persistenceStatus === 'unavailable' ? 'error' : 'notice'}`} role={persistenceStatus === 'unavailable' ? 'alert' : 'status'}>
            <span>{persistenceMessage}</span>
            {persistenceStatus === 'unavailable' && <button type="button" className="persistence-retry" onClick={() => window.location.reload()}>Reload after migration</button>}
          </div>
        )}
        <Suspense fallback={<PanelFallback />}>
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
                    <div className="hero-badge">Educational beta · India-focused compliance</div>
                    <h1 className="hero-title">
                      Your <span className="gradient-text">Business Guide</span><br />
                      for Business Compliance
                    </h1>
                    <p className="hero-subtitle">
                      Explore AI-assisted planning information for Indian businesses and ask questions about your uploaded documents.
                      Check important legal and tax decisions against the original source and a qualified professional.
                    </p>
                    <div className="quick-actions">
                      {QUICK_ACTIONS.map((qa) => (
                        <motion.button
                          key={qa.title}
                          type="button"
                          whileHover={{ scale: 1.03, y: -4 }}
                          whileTap={{ scale: 0.98 }}
                          className="glass-panel action-card"
                          onClick={() => handleSend(qa.query)}
                          aria-label={`${qa.title}: ${qa.desc}`}
                        >
                          <div className="action-icon">{qa.icon}</div>
                          <div className="action-title">{qa.title}</div>
                          <div className="action-desc">{qa.desc}</div>
                        </motion.button>
                      ))}
                    </div>
                  </motion.div>
                ) : (
                  <div className="messages-list">
                    <AnimatePresence>
                      {messages.map((msg, idx) => (
                        <motion.div
                          key={idx}
                          initial={{ opacity: 0, y: 12, scale: 0.97 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          transition={{ duration: 0.3 }}
                          className={`message-bubble ${msg.role === 'user' ? 'message-user' : 'message-ai'}`}
                        >
                          {msg.role === 'ai' ? (
                            <>
                              <div className="ai-label">
                                <span className="ai-dot" />
                                BizGuide AI
                              </div>
                              <Suspense fallback={<div className="markdown-fallback">{msg.content}</div>}>
                                <MarkdownMessage content={msg.content} />
                              </Suspense>
                              {msg.citations?.length > 0 && (
                                <div className="citation-list" aria-label="Document sources">
                                  <div className="citation-heading">Sources from your documents</div>
                                  <ol>
                                    {msg.citations.map((citation, citationIndex) => (
                                      <li key={`${citation.document_id}-${citation.page_number || citationIndex}`}>
                                        <div className="citation-meta">
                                          <span>{citation.file_name || 'Uploaded document'}</span>
                                          {citation.page_number && <span> · page {citation.page_number}</span>}
                                        </div>
                                        <div className="citation-snippet">“{citation.snippet}”</div>
                                      </li>
                                    ))}
                                  </ol>
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
                              <p className="answer-disclaimer">
                                BizGuide AI can make mistakes. Verify important legal and tax information with a professional.
                              </p>
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
                          <div className="ai-label"><span className="ai-dot pulsing" /> BizGuide AI</div>
                          <div className="typing-indicator" role="status" aria-live="polite">
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0 }} className="typing-dot" />
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0.2 }} className="typing-dot" />
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0.4 }} className="typing-dot" />
                            <span className="typing-text">
                              {isUploading ? 'Processing document and creating embeddings…' : 'Preparing your response…'}
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
                  <input
                    type="text"
                    className="chat-input"
                    aria-label="Ask BizGuide a question"
                    placeholder="Ask about business structures, GST, licenses…"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && input.trim() && !isTyping && !isUploading) {
                        handleSend(input);
                      }
                    }}
                    disabled={isUploading || isTyping}
                    autoFocus
                  />
                  {!input && !isUploading && !isTyping && (
                    <div className="input-marquee" aria-hidden="true">
                      <span>
                        Ask about business structures, GST, licenses, and more&nbsp;&nbsp;•&nbsp;&nbsp;
                        Ask about business structures, GST, licenses, and more&nbsp;&nbsp;•&nbsp;&nbsp;
                      </span>
                    </div>
                  )}
                  <motion.button
                    whileHover={input.trim() && !isTyping && !isUploading ? { scale: 1.1 } : {}}
                    whileTap={input.trim() && !isTyping && !isUploading ? { scale: 0.9 } : {}}
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
              <MyBusinesses
                session={session}
                businesses={businesses}
                onBusinessesChange={handleBusinessesChange}
                onAskQuestion={handleAskQuestion}
                activeBusinessId={activeBusinessId}
                onSelectBusiness={handleSelectBusiness}
              />
            </motion.div>
          ) : currentView === 'upload' ? (
            <motion.div key="upload" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <UploadDocuments session={session} apiUrl={apiUrl} businessId={activeBusinessId} />
            </motion.div>
          ) : currentView === 'workflow' ? (
            <motion.div key="workflow" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <WorkflowDashboard
                session={session}
                apiUrl={apiUrl}
                activeBusinessId={activeBusinessId}
                businessJurisdiction={activeBusinessProfile?.state || ''}
                onGoToBusinesses={() => setCurrentView('businesses')}
              />
            </motion.div>
          ) : currentView === 'settings' ? (
            <motion.div key="settings" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <Settings
                session={session}
                onClearHistory={handleClearAllHistory}
                onApiUrlChange={setApiUrl}
                currentApiUrl={apiUrl}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>
        </Suspense>
      </main>
    </div>
  );
}

export default App;
