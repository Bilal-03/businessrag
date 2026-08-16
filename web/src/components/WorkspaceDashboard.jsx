import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  Clock3,
  FileText,
  HardDrive,
  MessageSquare,
  Plus,
  UploadCloud,
} from 'lucide-react';
import BrandKicker from './BrandKicker';

function displayName(session) {
  const metadata = session?.user?.user_metadata || {};
  const name = metadata.full_name || metadata.name || session?.user?.email?.split('@')[0] || 'there';
  return name.trim().split(/\s+/)[0] || 'there';
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / (1024 ** index);
  return `${value >= 10 || index === 0 ? Math.round(value) : value.toFixed(1)} ${units[index]}`;
}

function formatDate(value) {
  if (!value) return 'Date unavailable';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Date unavailable';
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function conversationPreview(conversation) {
  const message = (conversation?.messages || []).find(item => item.role === 'ai')
    || (conversation?.messages || []).find(item => item.role === 'user');
  return String(message?.content || 'No messages in this conversation.').replace(/[#*_`]/g, '').replace(/\s+/g, ' ').trim();
}

function documentStatus(document) {
  if (document.status === 'indexed') return { label: 'Indexed', className: 'is-success', icon: CheckCircle2 };
  if (document.status === 'failed') return { label: 'Needs attention', className: 'is-danger', icon: AlertCircle };
  return { label: document.processing_stage || 'Processing', className: 'is-pending', icon: Clock3 };
}

const WorkspaceDashboard = ({
  session,
  apiUrl,
  businesses = [],
  conversations = [],
  activeBusinessProfile,
  onNavigate,
  onSelectConversation,
  onNewChat,
}) => {
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    if (!session?.access_token) {
      setDocuments([]);
      setDocumentsLoading(false);
      return () => controller.abort();
    }

    setDocumentsLoading(true);
    setDocumentsError('');
    fetch(`${apiUrl}/api/documents`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      signal: controller.signal,
    })
      .then(async response => {
        let data = [];
        try { data = await response.json(); } catch {}
        if (!response.ok) throw new Error(data.detail || 'Source inventory is unavailable.');
        if (!Array.isArray(data)) throw new Error('Source inventory returned an unexpected response.');
        setDocuments(data);
      })
      .catch(error => {
        if (error.name !== 'AbortError') {
          setDocumentsError(error.message || 'Source inventory is unavailable.');
          setDocuments([]);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setDocumentsLoading(false);
      });

    return () => controller.abort();
  }, [apiUrl, session?.access_token]);

  const indexedDocuments = documents.filter(document => document.status === 'indexed').length;
  const storageBytes = documents.reduce((total, document) => total + (Number(document.byte_size) || 0), 0);
  const recentDocuments = documents.slice(0, 4);
  const recentConversations = conversations.slice(0, 4);
  const activeBusinessLabel = activeBusinessProfile?.name || 'Personal workspace';

  const metrics = useMemo(() => [
    {
      label: 'Business workspaces',
      value: businesses.length,
      detail: businesses.length ? 'Profiles ready for context' : 'Create your first profile',
      icon: Building2,
      tone: 'accent',
    },
    {
      label: 'Conversations',
      value: conversations.length,
      detail: conversations.length ? 'Saved source-aware discussions' : 'Start your first question',
      icon: MessageSquare,
      tone: 'sage',
    },
    {
      label: 'Indexed sources',
      value: documentsLoading ? '—' : indexedDocuments,
      detail: documentsLoading ? 'Checking source library' : `${documents.length} total source${documents.length === 1 ? '' : 's'}`,
      icon: FileText,
      tone: 'ochre',
    },
    {
      label: 'Source storage',
      value: documentsLoading ? '—' : formatBytes(storageBytes),
      detail: documentsLoading ? 'Checking storage' : 'Owner-scoped document inventory',
      icon: HardDrive,
      tone: 'rose',
    },
  ], [businesses.length, conversations.length, documents.length, documentsLoading, indexedDocuments, storageBytes]);

  return (
    <div className="dashboard-page">
      <section className="dashboard-welcome" aria-labelledby="dashboard-title">
        <div className="dashboard-welcome-copy">
          <BrandKicker icon={SparkleIcon}>Workspace overview</BrandKicker>
          <h1 id="dashboard-title">Welcome back, {displayName(session)}.</h1>
          <p>Keep your business context, trusted sources, and next compliance questions in one clear workspace.</p>
          <div className="dashboard-context-line">
            <span className="dashboard-context-dot" aria-hidden="true" />
            <span>Current workspace: <strong>{activeBusinessLabel}</strong></span>
          </div>
        </div>
        <div className="dashboard-welcome-actions">
          <button type="button" className="btn-primary" onClick={onNewChat}>
            <Plus size={16} aria-hidden="true" />
            New question
          </button>
          <button type="button" className="btn-ghost" onClick={() => onNavigate('upload')}>
            <UploadCloud size={16} aria-hidden="true" />
            Add a source
          </button>
        </div>
      </section>

      <section className="dashboard-metric-grid" aria-label="Workspace metrics">
        {metrics.map(metric => {
          const Icon = metric.icon;
          return (
            <article className={`dashboard-metric-card tone-${metric.tone}`} key={metric.label}>
              <div className="dashboard-metric-topline">
                <span>{metric.label}</span>
                <span className="dashboard-metric-icon" aria-hidden="true"><Icon size={17} /></span>
              </div>
              <strong>{metric.value}</strong>
              <small>{metric.detail}</small>
            </article>
          );
        })}
      </section>

      <section className="dashboard-source-cta" aria-labelledby="dashboard-source-title">
        <div className="dashboard-source-icon" aria-hidden="true"><UploadCloud size={22} /></div>
        <div>
          <h2 id="dashboard-source-title">Add a source to ground your next answer</h2>
          <p>Upload a PDF and BizGuide will keep its answers tied to the document evidence you provide.</p>
        </div>
        <button type="button" className="btn-primary" onClick={() => onNavigate('upload')}>
          Upload PDF
          <ArrowUpRight size={15} aria-hidden="true" />
        </button>
      </section>

      {documentsError && (
        <div className="dashboard-inline-alert" role="alert">
          <AlertCircle size={16} aria-hidden="true" />
          <span>{documentsError} Other workspace activity is still available.</span>
          <button type="button" className="btn-ghost" onClick={() => onNavigate('upload')}>Open Source Library</button>
        </div>
      )}

      <div className="dashboard-activity-grid">
        <section className="dashboard-activity-card" aria-labelledby="dashboard-sources-heading">
          <div className="dashboard-section-heading">
            <div>
              <span className="dashboard-section-kicker">Knowledge base</span>
              <h2 id="dashboard-sources-heading">Recent sources</h2>
            </div>
            <button type="button" className="dashboard-text-action" onClick={() => onNavigate('upload')}>View library <ArrowUpRight size={13} aria-hidden="true" /></button>
          </div>
          {documentsLoading ? (
            <div className="dashboard-list-state" role="status">Checking your source library…</div>
          ) : recentDocuments.length === 0 ? (
            <div className="dashboard-list-state dashboard-empty-inline">
              <FileText size={20} aria-hidden="true" />
              <strong>No sources yet</strong>
              <span>Upload a PDF to make answers more specific and verifiable.</span>
              <button type="button" className="btn-ghost" onClick={() => onNavigate('upload')}>Upload first PDF</button>
            </div>
          ) : (
            <div className="dashboard-source-list">
              {recentDocuments.map(document => {
                const status = documentStatus(document);
                const StatusIcon = status.icon;
                return (
                  <div className="dashboard-source-row" key={document.id}>
                    <span className="dashboard-row-icon" aria-hidden="true"><FileText size={16} /></span>
                    <div className="dashboard-row-copy">
                      <strong title={document.file_name}>{document.file_name}</strong>
                      <span>{formatDate(document.created_at)} · {formatBytes(Number(document.byte_size) || 0)}</span>
                    </div>
                    <span className={`dashboard-status ${status.className}`}><StatusIcon size={12} aria-hidden="true" /> {status.label}</span>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section className="dashboard-activity-card" aria-labelledby="dashboard-conversations-heading">
          <div className="dashboard-section-heading">
            <div>
              <span className="dashboard-section-kicker">Saved work</span>
              <h2 id="dashboard-conversations-heading">Recent conversations</h2>
            </div>
            <button type="button" className="dashboard-text-action" onClick={() => onNavigate('history')}>View history <ArrowUpRight size={13} aria-hidden="true" /></button>
          </div>
          {recentConversations.length === 0 ? (
            <div className="dashboard-list-state dashboard-empty-inline">
              <MessageSquare size={20} aria-hidden="true" />
              <strong>Your next answer starts here</strong>
              <span>Ask a question and your source-aware conversation will appear in this list.</span>
              <button type="button" className="btn-ghost" onClick={onNewChat}>Start a question</button>
            </div>
          ) : (
            <div className="dashboard-conversation-list">
              {recentConversations.map(conversation => (
                <button
                  type="button"
                  className="dashboard-conversation-row"
                  key={conversation.id}
                  onClick={() => onSelectConversation(conversation.id)}
                >
                  <span className="dashboard-row-icon dashboard-row-icon-chat" aria-hidden="true"><MessageSquare size={16} /></span>
                  <span className="dashboard-row-copy">
                    <strong>{conversation.title || 'Untitled conversation'}</strong>
                    <span>{conversationPreview(conversation)}</span>
                  </span>
                  <span className="dashboard-row-date">{conversation.date || 'Recently'}</span>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

function SparkleIcon(props) {
  return <span {...props} aria-hidden="true">✦</span>;
}

export default WorkspaceDashboard;
