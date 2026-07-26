import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Home, Folder, UploadCloud, FileText, Settings, Plus, MessageSquare, ChevronRight, Trash2, Menu, X, LogOut } from 'lucide-react';
import Logo from './Logo';

const NAV_ITEMS = [
  { id: 'home',       label: 'Home',             icon: Home },
  { id: 'businesses', label: 'My Businesses',     icon: Folder },
  { id: 'upload',     label: 'Upload Documents',  icon: UploadCloud },
  { id: 'checklists', label: 'Checklists',        icon: FileText },
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
}) => {
  const recentConvos = (conversations || []).slice(0, 8);

  return (
    <>
      {/* Mobile/collapse overlay */}
      <AnimatePresence>
        {!collapsed && (
          <motion.aside
            initial={false}
            className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}
          >
            {/* Logo */}
            <div className="sidebar-logo">
              <Logo size={36} showText={!collapsed} textSize={20} />
              <button className="sidebar-collapse-btn" onClick={onToggleCollapse} title="Collapse sidebar">
                <X size={18} />
              </button>
            </div>

            {/* New Consultation Button */}
            <motion.button
              whileHover={{ scale: 1.02, y: -1 }}
              whileTap={{ scale: 0.98 }}
              className="new-chat-btn"
              onClick={onNewChat}
            >
              <Plus size={18} />
              <span>New Consultation</span>
            </motion.button>

            {/* Main Nav */}
            <nav className="sidebar-nav">
              {NAV_ITEMS.map(item => (
                <motion.button
                  key={item.id}
                  whileHover={{ x: 2 }}
                  whileTap={{ scale: 0.97 }}
                  className={`nav-item ${currentView === item.id ? 'active' : ''}`}
                  onClick={() => setCurrentView(item.id)}
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
                        onClick={() => onSelectConversation(conv.id)}
                      >
                        <MessageSquare size={14} className="conv-icon" />
                        <span className="conv-title">{conv.title || 'Untitled'}</span>
                        <button
                          className="conv-delete-btn"
                          onClick={e => { e.stopPropagation(); onDeleteConversation(conv.id); }}
                          title="Delete conversation"
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
                whileTap={{ scale: 0.97 }}
                className={`nav-item ${currentView === 'settings' ? 'active' : ''}`}
                onClick={() => setCurrentView('settings')}
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
                  whileTap={{ scale: 0.97 }}
                  className="nav-item sign-out-item"
                  onClick={onSignOut}
                  title={`Sign out ${session.user?.email || ''}`}
                >
                  <LogOut size={19} />
                  <span>Sign Out</span>
                </motion.button>
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Collapsed sidebar — just icon strip */}
      {collapsed && (
        <div className="sidebar-icon-strip">
          <button className="sidebar-collapse-btn" onClick={onToggleCollapse} title="Expand sidebar">
            <Menu size={20} />
          </button>
          <Logo size={32} showText={false} />
          <div style={{ flex: 1 }} />
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`icon-strip-btn ${currentView === item.id ? 'active' : ''}`}
              onClick={() => { setCurrentView(item.id); onToggleCollapse(); }}
              title={item.label}
            >
              <item.icon size={20} />
            </button>
          ))}
          <button
            className={`icon-strip-btn ${currentView === 'settings' ? 'active' : ''}`}
            onClick={() => { setCurrentView('settings'); onToggleCollapse(); }}
            title="Settings"
          >
            <Settings size={20} />
          </button>
        </div>
      )}
    </>
  );
};

export default Sidebar;
