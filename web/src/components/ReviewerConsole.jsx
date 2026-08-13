import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, History, RefreshCw, ShieldAlert, XCircle } from 'lucide-react';

async function parseResponse(response) {
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) throw new Error(data.detail || 'Reviewer data is unavailable.');
  return data;
}

export default function ReviewerConsole({ session, apiUrl, reviewerRoles = [] }) {
  const [queue, setQueue] = useState([]);
  const [changes, setChanges] = useState([]);
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [comments, setComments] = useState({});
  const headers = useMemo(() => ({ Authorization: `Bearer ${session?.access_token || ''}`, 'Content-Type': 'application/json' }), [session]);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [claims, changeEvents, events] = await Promise.all([
        fetch(`${apiUrl}/api/review/queue?lifecycle=in_review`, { headers }).then(parseResponse),
        fetch(`${apiUrl}/api/review/change-events`, { headers }).then(parseResponse),
        fetch(`${apiUrl}/api/review/audit`, { headers }).then(parseResponse),
      ]);
      setQueue(Array.isArray(claims) ? claims : []);
      setChanges(Array.isArray(changeEvents) ? changeEvents : []);
      setAudit(Array.isArray(events) ? events : []);
    } catch (requestError) { setError(requestError.message); } finally { setLoading(false); }
  }, [apiUrl, headers]);

  useEffect(() => { load(); }, [load]);

  const review = async (claim, decision) => {
    const role = reviewerRoles.find(item => item !== 'catalog_admin' && item !== 'bilingual_reviewer') || reviewerRoles.find(item => item !== 'catalog_admin');
    if (!role || !comments[claim.id]?.trim()) { setError('Select an assigned reviewer role and add review comments.'); return; }
    try {
      await parseResponse(await fetch(`${apiUrl}/api/review/claims/${claim.id}/reviews`, {
        method: 'POST', headers,
        body: JSON.stringify({ reviewer_role: role, decision, comments: comments[claim.id].trim() }),
      }));
      setComments(current => ({ ...current, [claim.id]: '' }));
      await load();
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="panel-container reviewer-console">
      <div className="panel-header"><div><div className="workflow-kicker"><ShieldAlert size={15} /> Human-governed knowledge</div><h2 className="panel-title">Review Console</h2><p className="panel-subtitle">AI can draft and classify. Only assigned professionals can approve, and only catalog admins can publish.</p></div><button type="button" className="btn-ghost" onClick={load}><RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh</button></div>
      {error && <div className="workflow-alert" role="alert"><XCircle size={17} /> {error}</div>}
      <section className="reviewer-grid">
        <div className="glass-panel reviewer-panel"><h3>Claims awaiting review</h3><p>Your roles: {reviewerRoles.join(', ')}</p>{queue.length === 0 ? <div className="workflow-task-empty">No claims assigned to this queue.</div> : queue.map(claim => <article key={claim.id} className="review-claim"><div className="review-claim-meta">{claim.jurisdiction} · {claim.claim_type} · {claim.risk_level} risk</div><h4>{claim.claim_key}</h4><p>{claim.statement_en}</p><textarea className="form-input" value={comments[claim.id] || ''} onChange={event => setComments(current => ({ ...current, [claim.id]: event.target.value }))} placeholder="Required review rationale and source check" maxLength={4000} /><div className="review-actions"><button className="btn-ghost" onClick={() => review(claim, 'request_changes')}>Request changes</button><button className="btn-primary" onClick={() => review(claim, 'approve')}><CheckCircle2 size={15} /> Approve</button></div></article>)}</div>
        <div className="glass-panel reviewer-panel"><h3>Open source changes</h3><p>Changed or unavailable sources stop supporting high-risk claims until resolved.</p>{changes.length === 0 ? <div className="workflow-task-empty">No open source-change alerts.</div> : changes.map(item => <div className="review-event" key={item.id}><strong>{item.event_type.replaceAll('_', ' ')}</strong><span>{item.severity} · {new Date(item.detected_at).toLocaleString('en-IN')}</span></div>)}</div>
      </section>
      <section className="glass-panel reviewer-panel"><h3><History size={16} /> Append-only review history</h3>{audit.slice(0, 30).map(item => <div className="review-event" key={item.id}><strong>{item.entity_type}: {item.action.replaceAll('_', ' ')}</strong><span>{item.from_state || 'new'} → {item.to_state || 'unchanged'} · {new Date(item.created_at).toLocaleString('en-IN')}</span><p>{item.reason}</p></div>)}</section>
    </div>
  );
}
