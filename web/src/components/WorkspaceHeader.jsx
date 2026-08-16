import React from 'react';
import { ArrowUpRight, Building2, CircleUserRound, Sparkles } from 'lucide-react';
import Logo from './Logo';

const VIEW_LABELS = {
  dashboard: 'Workspace overview',
  chat: 'Ask BizGuide',
  businesses: 'Business profiles',
  upload: 'Source library',
  workflow: 'Compliance plan',
  history: 'Conversation history',
  review: 'Review desk',
  settings: 'Workspace settings',
};

function displayName(session) {
  const metadata = session?.user?.user_metadata || {};
  return metadata.full_name || metadata.name || session?.user?.email?.split('@')[0] || 'there';
}

function initials(session) {
  const name = displayName(session);
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0])
    .join('')
    .toUpperCase() || 'B';
}

const WorkspaceHeader = ({ currentView, activeBusinessProfile, session, onNewChat }) => (
  <header className="workspace-header">
    <div className="workspace-header-brand">
      <Logo size={34} showText tone="light" />
      <span className="workspace-header-divider" aria-hidden="true" />
      <div className="workspace-header-page">
        <span className="workspace-header-eyebrow">{VIEW_LABELS[currentView] || 'BizGuide workspace'}</span>
      </div>
    </div>

    <div className="workspace-header-actions">
      <div className="workspace-header-context" title={activeBusinessProfile?.name || 'Personal workspace'}>
        <span className="workspace-header-status-dot" aria-hidden="true" />
        <Building2 size={14} aria-hidden="true" />
        <span>{activeBusinessProfile?.name || 'Personal workspace'}</span>
      </div>
      <div className="workspace-header-user" title={session?.user?.email || undefined}>
        <span className="workspace-header-avatar" aria-hidden="true">{initials(session)}</span>
        <span className="workspace-header-user-copy">
          <strong>{displayName(session)}</strong>
          <small>{session?.user?.email || 'Signed-in workspace'}</small>
        </span>
        <CircleUserRound size={16} aria-hidden="true" />
      </div>
      <button type="button" className="workspace-header-new" onClick={onNewChat}>
        <Sparkles size={15} aria-hidden="true" />
        <span>New question</span>
        <ArrowUpRight size={14} aria-hidden="true" />
      </button>
    </div>
  </header>
);

export default WorkspaceHeader;
