import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, Building2, UtensilsCrossed, Rocket, BarChart3, Wallet, Scale } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Sidebar from './components/Sidebar';
import MyBusinesses from './components/MyBusinesses';
import UploadDocuments from './components/UploadDocuments';
import Checklists from './components/Checklists';
import Settings from './components/Settings';
import Auth from './components/Auth';
import { supabase, getUserData, updateUserData } from './lib/supabase';
import './App.css';

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'https://businessrag.onrender.com';

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

/** Fire a real browser notification if permission granted and page is not focused */
function fireNotification(title, body) {
  if (typeof Notification === 'undefined') return;
  if (Notification.permission !== 'granted') return;
  if (document.visibilityState === 'visible' && document.hasFocus()) return;
  try {
    new Notification(title, { body, icon: '/logo.png', badge: '/logo.png' });
  } catch (_) {}
}

function App() {
  const [currentView, setCurrentView]     = useState('home');
  const [messages, setMessages]           = useState([]);
  const [input, setInput]                 = useState('');
  const [isTyping, setIsTyping]           = useState(false);
  const [isUploading, setIsUploading]     = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId]   = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [apiUrl, setApiUrl]               = useState(DEFAULT_API_URL);
  const [session, setSession]             = useState(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const currentConvIdRef = useRef(null);

  // Supabase Auth Listener
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setIsAuthLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Load conversations + settings
  useEffect(() => {
    const savedUrl = localStorage.getItem('bizguide_api_url');
    if (savedUrl) setApiUrl(savedUrl);
    
    if (session) {
      // Sync from Supabase
      getUserData(session.user.id).then(async (data) => {
        if (data && data.conversations) {
          setConversations(data.conversations);
        } else {
          // Migration from localStorage on first login
          const localConvs = localStorage.getItem('bizguide_conversations');
          const localBiz = localStorage.getItem('bizguide_businesses');
          const localChecks = localStorage.getItem('bizguide_checklists');
          
          const newDoc = {
            conversations: localConvs ? JSON.parse(localConvs) : [],
            businesses: localBiz ? JSON.parse(localBiz) : [],
            checklists: localChecks ? JSON.parse(localChecks) : {}
          };
          
          await updateUserData(session.user.id, newDoc);
          setConversations(newDoc.conversations);
          
          localStorage.removeItem('bizguide_conversations');
          localStorage.removeItem('bizguide_businesses');
          localStorage.removeItem('bizguide_checklists');
        }
      });
    }

    const savedAccent = localStorage.getItem('bizguide_accent');
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
  }, []);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const saveConversations = useCallback((updated) => {
    setConversations(updated);
    if (session) updateUserData(session.user.id, { conversations: updated });
  }, [session]);

  // Save current messages to the active conversation
  const persistCurrentConv = useCallback((msgs, convId) => {
    if (!convId || msgs.length === 0) return;
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
        };
        updated = [newConv, ...prev];
      }
      if (session) {
        updateUserData(session.user.id, { conversations: updated });
      }
      return updated;
    });
  }, [session]);

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
      currentConvIdRef.current = Date.now().toString();
      setActiveConvId(currentConvIdRef.current);
    }

    try {
      const response = await fetch(`${apiUrl}/api/chat`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({ query }),
      });
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || 'API Error');
      }
      
      const aiMsg = { role: 'ai', content: data.answer || 'No response received' };
      const finalMessages = [...updatedMessages, aiMsg];
      setMessages(finalMessages);
      persistCurrentConv(finalMessages, currentConvIdRef.current);
      // Fire browser notification if page is hidden
      fireNotification('BizGuide AI', 'Your answer is ready!');
    } catch (error) {
      const errMsg = { role: 'ai', content: `⚠️ Error connecting to the agent: ${error.message}` };
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

    setCurrentView('home');
    setIsUploading(true);
    const uploadMsg = { role: 'user', content: `📎 Uploading **${file.name}**…` };
    const updatedMessages = [...messages, uploadMsg];
    setMessages(updatedMessages);

    const formData = new FormData();
    formData.append('file', file);

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
      const data = await response.json();
      const resultMsg = response.ok
        ? { role: 'ai', content: `✅ **Upload Successful!** ${data.message}\n\nYou can now ask me questions based on this document. Your documents are private to your session only.` }
        : { role: 'ai', content: `❌ **Upload Failed:** ${data.detail}` };
      const finalMessages = [...updatedMessages, resultMsg];
      setMessages(finalMessages);
      persistCurrentConv(finalMessages, currentConvIdRef.current);
      fireNotification('BizGuide AI', `${file.name} uploaded and indexed successfully!`);
    } catch (error) {
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
    }
  };

  const handleDeleteConversation = (convId) => {
    const updated = conversations.filter(c => c.id !== convId);
    saveConversations(updated);
    if (activeConvId === convId) {
      setMessages([]);
      currentConvIdRef.current = null;
      setActiveConvId(null);
    }
  };

  const handleClearAllHistory = () => {
    saveConversations([]);
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
    await supabase.auth.signOut();
  };

  if (isAuthLoading) {
    return <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center', color: 'white' }}>Loading...</div>;
  }

  if (!session) {
    return <Auth />;
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
                    <div className="hero-badge">BizGuide AI</div>
                    <h1 className="hero-title">
                      Your <span className="gradient-text">Personal Agent</span><br />
                      for Business Compliance
                    </h1>
                    <p className="hero-subtitle">
                      Ask anything about starting a business, getting licenses, or filing taxes in India.
                      Our multi-agent AI system sources the latest government laws to give you accurate answers.
                    </p>
                    <div className="quick-actions">
                      {QUICK_ACTIONS.map((qa) => (
                        <motion.div
                          key={qa.title}
                          whileHover={{ scale: 1.03, y: -4 }}
                          whileTap={{ scale: 0.98 }}
                          className="glass-panel action-card"
                          onClick={() => handleSend(qa.query)}
                        >
                          <div className="action-icon">{qa.icon}</div>
                          <div className="action-title">{qa.title}</div>
                          <div className="action-desc">{qa.desc}</div>
                        </motion.div>
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
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
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
                          <div className="typing-indicator">
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0 }} className="typing-dot" />
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0.2 }} className="typing-dot" />
                            <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0.4 }} className="typing-dot" />
                            <span className="typing-text">
                              {isUploading ? 'Processing document and creating embeddings…' : 'Consulting Specialized Agents…'}
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
                  <motion.button
                    whileHover={input.trim() && !isTyping && !isUploading ? { scale: 1.1 } : {}}
                    whileTap={input.trim() && !isTyping && !isUploading ? { scale: 0.9 } : {}}
                    className="send-button"
                    onClick={() => handleSend(input)}
                    disabled={!input.trim() || isTyping || isUploading}
                  >
                    <Send size={20} />
                  </motion.button>
                </div>
                <div className="input-hint">BizGuide AI can make mistakes. Verify important legal and tax information with a professional.</div>
              </div>
            </motion.div>
          ) : currentView === 'businesses' ? (
            <motion.div key="businesses" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <MyBusinesses session={session} onAskQuestion={handleAskQuestion} />
            </motion.div>
          ) : currentView === 'upload' ? (
            <motion.div key="upload" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <UploadDocuments session={session} apiUrl={apiUrl} />
            </motion.div>
          ) : currentView === 'checklists' ? (
            <motion.div key="checklists" className="panel-view" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <Checklists session={session} onAskQuestion={handleAskQuestion} />
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
      </main>
    </div>
  );
}

export default App;
