import React, { useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Home, Folder, UploadCloud, ClipboardCheck, Settings, Plus, MessageSquare, Trash2, Menu, X, LogOut, ShieldCheck } from 'lucide-react';
import Logo from './Logo';

const NAV_ITEMS = [
  { id: 'home',       label: 'Ask BizGuide',     shortLabel: 'Ask',        icon: Home },
  { id: 'businesses', label: 'Businesses',       shortLabel: 'Businesses', icon: Folder },
  { id: 'upload',     label: 'Source Library',   shortLabel: 'Sources',    icon: UploadCloud },
  { id: 'workflow',   label: 'Compliance Plan',  shortLabel: 'Plan',       icon: ClipboardCheck },
];

const Sidebar = ({
  currentView,
  setCurrentView,
  onNewChat,
  conversations,
  onSelectConversation,
  activeConversationId,
  onDeleteConversation,
  collapsed,
  onToggleCollapse,
  session,
  onSignOut,
  isReviewer = false,
}) => {
  const navItems = isReviewer ? [...NAV_ITEMS, { id: 'review', label: 'Review Desk', shortLabel: 'Review', icon: ShieldCheck }] : NAV_ITEMS;
  const recentConvos = (conversations || []).slice(0, 8);
  const conversationActivationRef = useRef(false);
  const isMobile = () => window.matchMedia('(max-width: 767px)').matches;
  const navigate = (view) => {
    setCurrentView(view);
    if (isMobile() && !collapsed) onToggleCollapse();
  };
  const startNewChat = () => {
    onNewChat();
    if (isMobile() && !collapsed) onToggleCollapse();
  };
  const selectConversation = (convId) => {
    if (conversationActivationRef.current) return;
    conversationActivationRef.current = true;
    onSelectConversation(convId);
    window.setTimeout(() => { conversationActivationRef.current = false; }, 0);
  };

  return (
    <>
      {!collapsed ? (
        <>
          <button className="sidebar-backdrop" type="button" onClick={onToggleCollapse} aria-label="Close navigation" />
          <aside className="sidebar" aria-label="Workspace navigation">
            {/* Logo */}
            <div className="sidebar-logo">
              <Logo size={36} showText={!collapsed} tone="dark" />
              <button className="sidebar-collapse-btn" onClick={onToggleCollapse} title="Collapse sidebar" aria-label="Collapse sidebar" aria-expanded="true">
                <X size={18} />
              </button>
            </div>

            {/* New chat button */}
            <motion.button
              whileHover={{ x: 2 }}
              whileTap={{ x: 0 }}
              className="new-chat-btn"
              onClick={startNewChat}
            >
              <Plus size={18} />
              <span>New question</span>
            </motion.button>

            {/* Main Nav */}
            <nav className="sidebar-nav" aria-label="Primary navigation">
              {navItems.map(item => (
                <motion.button
                  key={item.id}
                  whileHover={{ x: 2 }}
                  whileTap={{ x: 0 }}
                  className={`nav-item ${currentView === item.id ? 'active' : ''}`}
                  onClick={() => navigate(item.id)}
                  aria-current={currentView === item.id ? 'page' : undefined}
                >
                  <item.icon size={19} />
                  <span>{item.label}</span>
                  {currentView === item.id && (
                    <motion.div layoutId="active-indicator" className="nav-active-indicator" />
                  )}
                </motion.button>
              ))}
            </nav>

            {/* Recent Conversations */}
            {recentConvos.length > 0 && (
              <div className="sidebar-section">
                <div className="sidebar-section-label">Recent Conversations</div>
                <div className="conversation-list">
                  <AnimatePresence>
                    {recentConvos.map(conv => (
                      <motion.div
                        key={conv.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -10 }}
                        className={`conversation-item ${activeConversationId === conv.id ? 'active-conv' : ''}`}
                      >
                        <button
                          type="button"
                          className="conversation-select-btn"
                          aria-label={`Open conversation ${conv.title || 'Untitled'}`}
                          aria-current={activeConversationId === conv.id ? 'page' : undefined}
                          onPointerUp={e => {
                            if (e.button === 0) selectConversation(conv.id);
                          }}
                          onClick={() => selectConversation(conv.id)}
                        >
                          <MessageSquare size={14} className="conv-icon" />
                          <span className="conv-title">{conv.title || 'Untitled'}</span>
                        </button>
                        <button
                          type="button"
                          className="conv-delete-btn"
                          onClick={e => { e.stopPropagation(); onDeleteConversation(conv.id); }}
                          title="Delete conversation"
                          aria-label={`Delete conversation ${conv.title || 'Untitled'}`}
                        >
                          <Trash2 size={12} />
                        </button>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            )}

            {/* Settings + Sign Out at bottom */}
            <div className="sidebar-bottom">
              <motion.button
                whileHover={{ x: 2 }}
                whileTap={{ x: 0 }}
                className={`nav-item ${currentView === 'settings' ? 'active' : ''}`}
                onClick={() => navigate('settings')}
                aria-current={currentView === 'settings' ? 'page' : undefined}
              >
                <Settings size={19} />
                <span>Settings</span>
                {currentView === 'settings' && (
                  <motion.div layoutId="active-indicator" className="nav-active-indicator" />
                )}
              </motion.button>
              {session && (
                <motion.button
                  whileHover={{ x: 2 }}
                  whileTap={{ x: 0 }}
                  className="nav-item sign-out-item"
                  onClick={onSignOut}
                  title={`Sign out ${session.user?.email || ''}`}
                  aria-label={`Sign out ${session.user?.email || ''}`}
                >
                  <LogOut size={19} />
                  <span>Sign Out</span>
                </motion.button>
              )}
            </div>
          </aside>
        </>
      ) : (
        <>
          <button className="mobile-menu-button" onClick={onToggleCollapse} title="Open navigation" aria-label="Open navigation">
            <Menu size={24} />
          </button>

        <div className="sidebar-icon-strip">
          <button className="sidebar-collapse-btn" onClick={onToggleCollapse} title="Expand sidebar" aria-label="Expand sidebar" aria-expanded="false">
            <Menu size={20} />
          </button>
          <div className="mobile-sidebar-logo"><Logo size={32} showText={false} tone="dark" /></div>
          <div style={{ flex: 1 }} />
          {navItems.map(item => (
            <button
              key={item.id}
              className={`icon-strip-btn ${currentView === item.id ? 'active' : ''}`}
              onClick={() => {
                setCurrentView(item.id);
                if (!isMobile()) onToggleCollapse();
              }}
              title={item.label}
              aria-label={item.label}
              aria-current={currentView === item.id ? 'page' : undefined}
            >
              <item.icon size={20} />
            </button>
          ))}
          <button
            className={`icon-strip-btn ${currentView === 'settings' ? 'active' : ''}`}
            onClick={() => {
              setCurrentView('settings');
              if (!isMobile()) onToggleCollapse();
            }}
            title="Settings"
            aria-label="Settings"
            aria-current={currentView === 'settings' ? 'page' : undefined}
          >
            <Settings size={20} />
          </button>
        </div>
        </>
      )}
      <nav className={`mobile-bottom-nav ${!collapsed ? 'drawer-open' : ''}`} aria-label="Mobile navigation">
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            type="button"
            className={currentView === item.id ? 'active' : ''}
            onClick={() => navigate(item.id)}
            aria-current={currentView === item.id ? 'page' : undefined}
            aria-label={item.label}
          >
            <item.icon size={19} />
            <span>{item.shortLabel}</span>
          </button>
        ))}
      </nav>
    </>
  );
};

export default Sidebar;
