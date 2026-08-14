import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Globe, Trash2, Info, Check, Palette, Shield, Bell, Bot, Search, FileText, MapPin, Settings as SettingsIcon } from 'lucide-react';
import Logo from './Logo';

const APP_VERSION = '1.0.0';

const ACCENT_COLORS = [
  { name: 'Terracotta', primary: '#9f3f29', secondary: '#7f321f' },
  { name: 'Olive', primary: '#52634d', secondary: '#394737' },
  { name: 'Ochre', primary: '#8a5c18', secondary: '#684511' },
  { name: 'Rosewood', primary: '#8f4650', secondary: '#6d333c' },
];

const Settings = ({ session, onClearHistory, onApiUrlChange, currentApiUrl }) => {
  const [profile, setProfile] = useState({ name: '', email: '', company: '' });
  const [apiUrl, setApiUrl] = useState(currentApiUrl || import.meta.env.VITE_API_URL || 'https://businessrag.onrender.com');
  const [saved, setSaved] = useState(false);
  const [selectedAccent, setSelectedAccent] = useState(0);
  const [notifications, setNotifications] = useState(false);
  const [notifPermission, setNotifPermission] = useState(
    typeof Notification !== 'undefined' ? Notification.permission : 'unsupported'
  );
  const [confirmClear, setConfirmClear] = useState(false);
  const [confirmClearDocs, setConfirmClearDocs] = useState(false);
  const [activeSection, setActiveSection] = useState('profile');
  const [dataStatus, setDataStatus] = useState('');
  const userKey = useCallback((name) => session?.user?.id ? `${name}:${session.user.id}` : name, [session?.user?.id]);

  useEffect(() => {
    const savedProfile = localStorage.getItem(userKey('bizguide_profile'));
    if (savedProfile) setProfile(JSON.parse(savedProfile));
    const savedAccent = localStorage.getItem(userKey('bizguide_accent'));
    if (savedAccent) {
      const savedIndex = parseInt(savedAccent, 10);
      setSelectedAccent(Number.isInteger(savedIndex) && ACCENT_COLORS[savedIndex] ? savedIndex : 0);
    }
    const savedApiUrl = localStorage.getItem(userKey('bizguide_api_url'));
    if (savedApiUrl) setApiUrl(savedApiUrl);
    const savedNotifs = localStorage.getItem(userKey('bizguide_notifications'));
    if (savedNotifs !== null) {
      setNotifications(savedNotifs === 'true' && typeof Notification !== 'undefined' && Notification.permission === 'granted');
    }
  }, [session, userKey]);

  const handleSaveProfile = () => {
    localStorage.setItem(userKey('bizguide_profile'), JSON.stringify(profile));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleAccentChange = (idx) => {
    setSelectedAccent(idx);
    localStorage.setItem(userKey('bizguide_accent'), idx.toString());
    const color = ACCENT_COLORS[idx];
    document.documentElement.style.setProperty('--color-accent', color.primary);
    document.documentElement.style.setProperty('--color-accent-strong', color.secondary);
    document.documentElement.style.setProperty('--color-accent-soft', `${color.primary}1f`);
    document.documentElement.style.setProperty('--accent-primary', color.primary);
    document.documentElement.style.setProperty('--accent-secondary', color.secondary);
  };

  const handleSaveApiUrl = () => {
    localStorage.setItem(userKey('bizguide_api_url'), apiUrl);
    if (onApiUrlChange) onApiUrlChange(apiUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleClearHistory = () => {
    if (confirmClear) {
      onClearHistory();
      localStorage.removeItem(`bizguide_conversations:${session?.user?.id || ''}`);
      setConfirmClear(false);
    } else {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 4000);
    }
  };

  const handleClearDocuments = async () => {
    if (!session) {
      setDataStatus('Sign in to manage uploaded documents.');
      return;
    }
    if (!confirmClearDocs) {
      setConfirmClearDocs(true);
      setTimeout(() => setConfirmClearDocs(false), 4000);
      return;
    }
    setConfirmClearDocs(false);
    try {
      const response = await fetch(`${apiUrl}/api/documents/clear`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      let data = {};
      try { data = await response.json(); } catch {}
      if (!response.ok) throw new Error(data.detail || 'We could not clear uploaded documents.');
      localStorage.removeItem(`bizguide_uploads:${session.user.id}`);
      setDataStatus('Your uploaded documents have been cleared.');
    } catch (e) {
      setDataStatus(e.message || 'Failed to clear documents. Please try again.');
    }
  };

  const SECTIONS = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'api', label: 'API & Data', icon: Globe },
    { id: 'about', label: 'About', icon: Info },
  ];

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div>
          <div className="panel-kicker"><SettingsIcon size={14} /> Workspace preferences</div>
          <h2 className="panel-title">Settings</h2>
          <p className="panel-subtitle">Customize your BizGuide experience.</p>
        </div>
      </div>

      <div className="settings-layout">
        {/* Settings Nav */}
        <div className="settings-nav" role="tablist" aria-label="Settings sections">
          {SECTIONS.map(s => (
            <button
              key={s.id}
              id={`settings-tab-${s.id}`}
              className={`settings-nav-item ${activeSection === s.id ? 'active' : ''}`}
              onClick={() => setActiveSection(s.id)}
              role="tab"
              aria-selected={activeSection === s.id}
              aria-controls={`settings-panel-${s.id}`}
              tabIndex={activeSection === s.id ? 0 : -1}
              onKeyDown={event => {
                if (!['ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault();
                const currentIndex = SECTIONS.findIndex(section => section.id === s.id);
                const nextIndex = event.key === 'Home'
                  ? 0
                  : event.key === 'End'
                    ? SECTIONS.length - 1
                    : (currentIndex + (event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : -1) + SECTIONS.length) % SECTIONS.length;
                const nextSection = SECTIONS[nextIndex];
                setActiveSection(nextSection.id);
                window.requestAnimationFrame(() => document.getElementById(`settings-tab-${nextSection.id}`)?.focus());
              }}
            >
              <s.icon size={18} /> {s.label}
            </button>
          ))}
        </div>

        {/* Settings Content */}
        <div className="settings-content" role="tabpanel" id={`settings-panel-${activeSection}`} aria-labelledby={`settings-tab-${activeSection}`} tabIndex="0">
          <AnimatePresence mode="wait">
            {activeSection === 'profile' && (
              <motion.div key="profile" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <div className="settings-section-title">Profile Information</div>
                <p className="settings-section-desc">This information is stored locally in your browser and helps personalize your experience.</p>
                <div className="settings-fields">
                  <div className="form-group full">
                    <label htmlFor="profile-name">Your Name</label>
                    <input id="profile-name" className="form-input" placeholder="e.g. Rajesh Kumar" value={profile.name} onChange={e => setProfile({ ...profile, name: e.target.value })} />
                  </div>
                  <div className="form-group full">
                    <label htmlFor="profile-email">Email Address</label>
                    <input id="profile-email" className="form-input" type="email" placeholder="you@example.com" value={profile.email} onChange={e => setProfile({ ...profile, email: e.target.value })} />
                  </div>
                  <div className="form-group full">
                    <label htmlFor="profile-company">Company / Business Name</label>
                    <input id="profile-company" className="form-input" placeholder="Your company name" value={profile.company} onChange={e => setProfile({ ...profile, company: e.target.value })} />
                  </div>
                </div>
                <motion.button whileHover={{ y: -1 }} className="btn-primary" onClick={handleSaveProfile}>
                  {saved ? <><Check size={16} /> Saved!</> : <><Check size={16} /> Save Profile</>}
                </motion.button>
              </motion.div>
            )}

            {activeSection === 'appearance' && (
              <motion.div key="appearance" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <div className="settings-section-title">Appearance</div>
                <p className="settings-section-desc">Choose an accent color theme for your BizGuide interface.</p>
                <div className="accent-grid">
                  {ACCENT_COLORS.map((color, idx) => (
                    <motion.button
                      key={color.name}
                      whileHover={{ y: -1 }}
                      whileTap={{ y: 0 }}
                      className={`accent-swatch ${selectedAccent === idx ? 'selected' : ''}`}
                      onClick={() => handleAccentChange(idx)}
                      title={color.name}
                      aria-label={`${color.name} accent theme`}
                      aria-pressed={selectedAccent === idx}
                    >
                      <div
                        className="accent-circle"
                        style={{ background: color.primary, '--swatch-secondary': color.secondary }}
                      />
                      <span className="accent-name">{color.name}</span>
                      {selectedAccent === idx && <Check size={14} className="accent-check" />}
                    </motion.button>
                  ))}
                </div>
                <div className="settings-toggle-row">
                  <div>
                    <div className="toggle-label"><Bell size={16} /> Browser Notifications
                      {notifPermission === 'granted' && <span className="notif-status granted">Granted</span>}
                      {notifPermission === 'denied'  && <span className="notif-status denied">Blocked in browser</span>}
                    </div>
                    <div className="toggle-desc">
                      {notifPermission === 'denied'
                        ? 'Notifications are blocked. Enable them in your browser site settings.'
                        : 'Get notified when AI responses are ready while you\'re in another tab.'}
                    </div>
                  </div>
                  <button
                    className={`toggle-switch ${notifications && notifPermission === 'granted' ? 'on' : 'off'}`}
                    disabled={notifPermission === 'denied'}
                    role="switch"
                    aria-checked={notifications && notifPermission === 'granted'}
                    aria-label="Browser notifications"
                    onClick={async () => {
                      if (!notifications) {
                        // Turning ON — request real browser permission
                        if (typeof Notification === 'undefined') return;
                        const permission = await Notification.requestPermission();
                        setNotifPermission(permission);
                        if (permission === 'granted') {
                          setNotifications(true);
                          localStorage.setItem(userKey('bizguide_notifications'), 'true');
                          // Fire a test notification so they can see it works
                          new Notification('BizGuide AI', {
                            body: 'Notifications are enabled! You\'ll be notified when AI responds.',
                            icon: '/logo.png',
                          });
                        } else {
                          setNotifications(false);
                          localStorage.setItem(userKey('bizguide_notifications'), 'false');
                        }
                      } else {
                        // Turning OFF
                        setNotifications(false);
                        localStorage.setItem(userKey('bizguide_notifications'), 'false');
                      }
                    }}
                  >
                    <motion.div className="toggle-thumb" animate={{ x: notifications && notifPermission === 'granted' ? 20 : 0 }} transition={{ type: 'spring', stiffness: 500, damping: 30 }} />
                  </button>
                </div>
              </motion.div>
            )}

            {activeSection === 'api' && (
              <motion.div key="api" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <div className="settings-section-title">API & Data</div>
                <p className="settings-section-desc">Configure the backend API endpoint and manage data.</p>
                {import.meta.env.DEV && (
                  <div className="form-group full" style={{ marginBottom: '24px' }}>
                    <label htmlFor="api-base-url">API Base URL</label>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <input id="api-base-url" className="form-input" placeholder="https://your-api.com" value={apiUrl} onChange={e => setApiUrl(e.target.value)} style={{ flex: 1 }} />
                      <motion.button whileHover={{ y: -1 }} className="btn-primary" style={{ flexShrink: 0 }} onClick={handleSaveApiUrl}>
                        Save
                      </motion.button>
                    </div>
                  </div>
                )}
                <div className="danger-zone">
                  <div className="danger-title"><Shield size={16} /> Danger Zone</div>
                  <div className="danger-row" style={{ marginBottom: '14px' }}>
                    <div>
                      <div className="danger-item-label">Clear My Uploaded Documents</div>
                      <div className="danger-item-desc">Remove all PDFs currently indexed for your account. This action cannot be undone.</div>
                    </div>
                    <motion.button
                      whileHover={{ y: -1 }}
                      className={`btn-danger ${confirmClearDocs ? 'confirming' : ''}`}
                      onClick={handleClearDocuments}
                      aria-label={confirmClearDocs ? 'Confirm clearing uploaded documents' : 'Clear uploaded documents'}
                    >
                      <Trash2 size={16} /> {confirmClearDocs ? 'Click again to confirm' : 'Clear My Docs'}
                    </motion.button>
                  </div>
                  <div className="danger-row">
                    <div>
                      <div className="danger-item-label">Clear Conversation History</div>
                      <div className="danger-item-desc">Permanently delete all saved conversations from this browser.</div>
                    </div>
                    <motion.button
                      whileHover={{ y: -1 }}
                      className={`btn-danger ${confirmClear ? 'confirming' : ''}`}
                      onClick={handleClearHistory}
                      aria-label={confirmClear ? 'Confirm clearing conversation history' : 'Clear conversation history'}
                    >
                      <Trash2 size={16} /> {confirmClear ? 'Click again to confirm' : 'Clear History'}
                    </motion.button>
                  </div>
                  {dataStatus && <div className="upload-status-message" role="status">{dataStatus}</div>}
                </div>
              </motion.div>
            )}

            {activeSection === 'about' && (
              <motion.div key="about" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <div className="settings-section-title">About BizGuide AI</div>
                <div className="about-card glass-panel">
                  <Logo size={56} showText={false} />
                  <div className="about-info">
                    <div className="about-name">BizGuide AI</div>
                    <div className="about-tagline">Business-compliance information for India</div>
                    <div className="about-version">Version {APP_VERSION}</div>
                  </div>
                </div>
                <div className="about-features">
                  {[
                    { icon: <Bot size={24} />, title: 'Gemini-assisted guidance', desc: 'Answers every question with Gemini and keeps business or document context opt-in per question' },
                    { icon: <Search size={24} />, title: 'Opt-in RAG', desc: 'Retrieval-augmented generation with Pinecone vector search and Gemini embeddings when Documents is enabled' },
                    { icon: <FileText size={24} />, title: 'Document Intelligence', desc: 'Upload your business PDFs to get answers grounded in your actual documents' },
                    { icon: <MapPin size={24} />, title: 'India-Focused', desc: 'Specialized in Indian business laws, GST, MCA regulations, and compliance' },
                  ].map(f => (
                    <div key={f.title} className="about-feature-item">
                      <span className="about-feature-icon">{f.icon}</span>
                      <div>
                        <div className="about-feature-title">{f.title}</div>
                        <div className="about-feature-desc">{f.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Credits */}
                <div className="credits-card">
                  <div className="credits-label">✦ Created by</div>
                  <div className="credits-name">Bilal</div>
                  <div className="credits-links">
                    <a
                      href="https://github.com/Bilal-03"
                      target="_blank"
                      rel="noreferrer"
                      className="credits-link"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                      </svg>
                      Bilal-03
                    </a>
                    <a
                      href="https://github.com/Bilal-03/businessrag"
                      target="_blank"
                      rel="noreferrer"
                      className="credits-link"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/>
                        <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/>
                      </svg>
                      Source Code
                    </a>
                  </div>
                  <div className="credits-message">
                    Built with ❤️ to help Indian entrepreneurs navigate business compliance with ease.
                  </div>
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default Settings;
