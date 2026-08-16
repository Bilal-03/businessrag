import React, { useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, Clock3, FileText, MessageSquare, Plus, Search, Trash2 } from 'lucide-react';
import BrandKicker from './BrandKicker';

function conversationText(conversation) {
  return (conversation?.messages || [])
    .map(message => String(message.content || ''))
    .join(' ')
    .replace(/[#*_`]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function preview(conversation) {
  const message = (conversation?.messages || []).find(item => item.role === 'ai')
    || (conversation?.messages || []).find(item => item.role === 'user');
  const value = String(message?.content || 'No messages in this conversation.')
    .replace(/[#*_`]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return value.length > 150 ? `${value.slice(0, 150).trim()}…` : value;
}

function conversationContext(conversation) {
  const contexts = new Set();
  if (conversation?.businessId) contexts.add('Business context');
  (conversation?.messages || []).forEach(message => {
    (message.contextUsed || []).forEach(context => contexts.add(context === 'business' ? 'Business context' : 'Uploaded sources'));
  });
  return Array.from(contexts);
}

const ConversationHistory = ({
  conversations = [],
  onSelectConversation,
  onDeleteConversation,
  onClearHistory,
  onNewChat,
}) => {
  const [query, setQuery] = useState('');
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (!pendingDeleteId) return undefined;
    const timeout = window.setTimeout(() => setPendingDeleteId(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [pendingDeleteId]);

  useEffect(() => {
    if (!confirmClear) return undefined;
    const timeout = window.setTimeout(() => setConfirmClear(false), 4000);
    return () => window.clearTimeout(timeout);
  }, [confirmClear]);

  const filteredConversations = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return conversations;
    return conversations.filter(conversation => {
      const title = String(conversation.title || '').toLowerCase();
      return title.includes(normalized) || conversationText(conversation).toLowerCase().includes(normalized);
    });
  }, [conversations, query]);

  const handleDelete = (conversationId) => {
    if (pendingDeleteId !== conversationId) {
      setPendingDeleteId(conversationId);
      return;
    }
    setPendingDeleteId(null);
    onDeleteConversation(conversationId);
  };

  const handleClear = () => {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    setConfirmClear(false);
    onClearHistory();
  };

  return (
    <div className="history-page">
      <section className="history-hero" aria-labelledby="history-title">
        <div>
          <BrandKicker icon={Clock3}>Saved work</BrandKicker>
          <h1 id="history-title">Conversation history</h1>
          <p>Return to previous questions, review the evidence behind an answer, or start a new source-aware conversation.</p>
        </div>
        <div className="history-hero-actions">
          <button type="button" className="btn-danger" onClick={handleClear} aria-label={confirmClear ? 'Confirm clearing conversation history' : 'Clear conversation history'}>
            <Trash2 size={15} aria-hidden="true" />
            {confirmClear ? 'Click again to confirm' : 'Clear history'}
          </button>
          <button type="button" className="btn-primary" onClick={onNewChat}>
            <Plus size={15} aria-hidden="true" />
            New question
          </button>
        </div>
      </section>

      <label className="history-search" htmlFor="conversation-history-search">
        <Search size={17} aria-hidden="true" />
        <span className="sr-only">Search conversation history</span>
        <input
          id="conversation-history-search"
          type="search"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="Search by title or message content…"
        />
        {query && <button type="button" className="history-search-clear" onClick={() => setQuery('')} aria-label="Clear history search">×</button>}
      </label>

      <div className="history-results-bar" aria-live="polite">
        <span>{filteredConversations.length} conversation{filteredConversations.length === 1 ? '' : 's'}</span>
        {query && <span>matching “{query}”</span>}
      </div>

      {filteredConversations.length === 0 ? (
        <section className="history-empty glass-panel">
          <span className="history-empty-icon" aria-hidden="true"><MessageSquare size={24} /></span>
          <h2>{conversations.length === 0 ? 'No conversations yet' : 'No matching conversations'}</h2>
          <p>{conversations.length === 0 ? 'Ask BizGuide a question and your saved source-aware work will appear here.' : 'Try a different search term or clear the filter.'}</p>
          {conversations.length === 0 && <button type="button" className="btn-primary" onClick={onNewChat}><Plus size={15} aria-hidden="true" /> Start a question</button>}
          {conversations.length > 0 && <button type="button" className="btn-ghost" onClick={() => setQuery('')}>Clear search</button>}
        </section>
      ) : (
        <section className="history-grid" aria-label="Conversation history results">
          {filteredConversations.map(conversation => {
            const contexts = conversationContext(conversation);
            const pending = pendingDeleteId === conversation.id;
            return (
              <article className="history-card glass-panel" key={conversation.id}>
                <div className="history-card-topline">
                  <span className="history-card-icon" aria-hidden="true"><MessageSquare size={17} /></span>
                  <span className="history-card-date"><Clock3 size={12} aria-hidden="true" /> {conversation.date || 'Recently'}</span>
                </div>
                <h2>{conversation.title || 'Untitled conversation'}</h2>
                <p>{preview(conversation)}</p>
                <div className="history-card-contexts">
                  {contexts.length > 0 ? contexts.map(context => <span key={context}><FileText size={11} aria-hidden="true" /> {context}</span>) : <span>Independent guidance</span>}
                </div>
                <div className="history-card-actions">
                  <button type="button" className="history-resume" onClick={() => onSelectConversation(conversation.id)}>Resume <ArrowUpRight size={13} aria-hidden="true" /></button>
                  <button type="button" className={`history-delete ${pending ? 'confirming' : ''}`} onClick={() => handleDelete(conversation.id)} aria-label={pending ? `Confirm deleting ${conversation.title || 'conversation'}` : `Delete ${conversation.title || 'conversation'}`}>
                    <Trash2 size={14} aria-hidden="true" />
                    {pending ? 'Confirm' : 'Delete'}
                  </button>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
};

export default ConversationHistory;
