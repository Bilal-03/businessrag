import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, History, RefreshCw, ShieldAlert, XCircle } from 'lucide-react';
import BrandKicker from './BrandKicker';

async function parseResponse(response) {
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) throw new Error(data.detail || 'Reviewer data is unavailable.');
  return data;
}

export default function ReviewerConsole({ session, apiUrl, reviewerRoles = [] }) {
  const [queue, setQueue] = useState([]);
  const [changes, setChanges] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [audit, setAudit] = useState([]);
  const [sourceVersions, setSourceVersions] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [assignment, setAssignment] = useState({ reviewer_user_id: '', reviewer_role: 'lawyer' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [comments, setComments] = useState({});
  const headers = useMemo(() => ({ Authorization: `Bearer ${session?.access_token || ''}`, 'Content-Type': 'application/json' }), [session]);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const lifecycleStates = ['draft', 'in_review', 'published', 'quarantined'];
      const [claimGroups, changeEvents, claimConflicts, events, sourceGroups, reviewerAssignments] = await Promise.all([
        Promise.all(lifecycleStates.map(lifecycle => fetch(`${apiUrl}/api/review/queue?lifecycle=${lifecycle}`, { headers }).then(parseResponse))),
        fetch(`${apiUrl}/api/review/change-events`, { headers }).then(parseResponse),
        fetch(`${apiUrl}/api/review/conflicts`, { headers }).then(parseResponse),
        fetch(`${apiUrl}/api/review/audit`, { headers }).then(parseResponse),
        Promise.all(['draft', 'in_review', 'approved', 'quarantined'].map(reviewStatus => fetch(`${apiUrl}/api/review/source-versions?review_status=${reviewStatus}`, { headers }).then(parseResponse))),
        reviewerRoles.includes('catalog_admin')
          ? fetch(`${apiUrl}/api/review/assignments`, { headers }).then(parseResponse)
          : Promise.resolve([]),
      ]);
      setQueue(claimGroups.flat());
      setChanges(Array.isArray(changeEvents) ? changeEvents : []);
      setConflicts(Array.isArray(claimConflicts) ? claimConflicts : []);
      setAudit(Array.isArray(events) ? events : []);
      setSourceVersions(sourceGroups.flat());
      setAssignments(Array.isArray(reviewerAssignments) ? reviewerAssignments : []);
    } catch (requestError) { setError(requestError.message); } finally { setLoading(false); }
  }, [apiUrl, headers, reviewerRoles]);

  useEffect(() => { load(); }, [load]);

  const review = async (claim, decision) => {
    const role = reviewerRoles.includes(claim.required_reviewer_role)
      ? claim.required_reviewer_role
      : reviewerRoles.find(item => item !== 'catalog_admin' && item !== 'bilingual_reviewer') || reviewerRoles.find(item => item !== 'catalog_admin');
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

  const resolveConflict = async (conflict, resolutionStatus) => {
    const notes = comments[`conflict:${conflict.id}`]?.trim();
    if (!notes) { setError('Add conflict-resolution notes before continuing.'); return; }
    try {
      await parseResponse(await fetch(`${apiUrl}/api/review/conflicts/${conflict.id}/resolve`, {
        method: 'POST', headers, body: JSON.stringify({ resolution_status: resolutionStatus, resolution_notes: notes }),
      }));
      await load();
    } catch (requestError) { setError(requestError.message); }
  };

  const resolveChange = async (change, resolutionStatus) => {
    const notes = comments[`change:${change.id}`]?.trim();
    if (!notes) { setError('Add source-change resolution notes before continuing.'); return; }
    try {
      await parseResponse(await fetch(`${apiUrl}/api/review/change-events/${change.id}/resolve`, {
        method: 'POST', headers, body: JSON.stringify({ resolution_status: resolutionStatus, notes }),
      }));
      await load();
    } catch (requestError) { setError(requestError.message); }
  };

  const transitionClaim = async (claim, lifecycle) => {
    const reason = comments[`claim-transition:${claim.id}`]?.trim();
    if (!reason) { setError('Add a transition reason before continuing.'); return; }
    try {
      await parseResponse(await fetch(`${apiUrl}/api/review/claims/${claim.id}/transition`, {
        method: 'POST', headers, body: JSON.stringify({ lifecycle, reason }),
      }));
      await load();
    } catch (requestError) { setError(requestError.message); }
  };

  const transitionSource = async (version, reviewStatus) => {
    const reason = comments[`source:${version.id}`]?.trim();
    if (!reason) { setError('Add a source-review reason before continuing.'); return; }
    try {
      await parseResponse(await fetch(`${apiUrl}/api/review/source-versions/${version.id}/transition`, {
        method: 'POST', headers, body: JSON.stringify({ review_status: reviewStatus, reason }),
      }));
      await load();
    } catch (requestError) { setError(requestError.message); }
  };

  const createAssignment = async () => {
    if (!assignment.reviewer_user_id.trim()) { setError('Enter the reviewer user UUID.'); return; }
    try {
      await parseResponse(await fetch(`${apiUrl}/api/review/assignments`, {
        method: 'POST', headers, body: JSON.stringify(assignment),
      }));
      setAssignment(current => ({ ...current, reviewer_user_id: '' }));
      await load();
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <div className="panel-container reviewer-console">
      <div className="panel-header"><div><BrandKicker icon={ShieldAlert}>Human-governed knowledge</BrandKicker><h2 className="panel-title">Review Console</h2><p className="panel-subtitle">AI can draft and classify. Only assigned professionals can approve, and only catalog admins can publish.</p></div><button type="button" className="btn-ghost" onClick={load}><RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh</button></div>
      {error && <div className="workflow-alert" role="alert"><XCircle size={17} /> {error}</div>}
      <section className="reviewer-grid">
        <div className="glass-panel reviewer-panel"><h3>Claim lifecycle</h3><p>Your roles: {reviewerRoles.join(', ')}</p>{queue.length === 0 ? <div className="workflow-task-empty">No claims in the active queues.</div> : queue.map(claim => <article key={claim.id} className="review-claim"><div className="review-claim-meta">{claim.lifecycle} · {claim.jurisdiction} · {claim.claim_type} · {claim.risk_level} risk</div><h4>{claim.claim_key}</h4><p>{claim.statement_en}</p>{claim.lifecycle === 'in_review' && <><textarea className="form-input" value={comments[claim.id] || ''} onChange={event => setComments(current => ({ ...current, [claim.id]: event.target.value }))} placeholder="Required review rationale and source check" maxLength={4000} /><div className="review-actions"><button className="btn-ghost" onClick={() => review(claim, 'request_changes')}>Request changes</button><button className="btn-primary" onClick={() => review(claim, 'approve')}><CheckCircle2 size={15} /> Approve</button></div></>}{(claim.lifecycle === 'draft' || reviewerRoles.includes('catalog_admin')) && <><textarea className="form-input" value={comments[`claim-transition:${claim.id}`] || ''} onChange={event => setComments(current => ({ ...current, [`claim-transition:${claim.id}`]: event.target.value }))} placeholder="Lifecycle transition reason" maxLength={4000} /><div className="review-actions">{claim.lifecycle === 'draft' && <button className="btn-primary" onClick={() => transitionClaim(claim, 'in_review')}>Submit for review</button>}{reviewerRoles.includes('catalog_admin') && claim.lifecycle === 'in_review' && <button className="btn-primary" onClick={() => transitionClaim(claim, 'published')}>Publish</button>}{reviewerRoles.includes('catalog_admin') && claim.lifecycle === 'published' && <><button className="btn-ghost" onClick={() => transitionClaim(claim, 'superseded')}>Supersede</button><button className="btn-ghost" onClick={() => transitionClaim(claim, 'quarantined')}>Rollback</button></>}{reviewerRoles.includes('catalog_admin') && claim.lifecycle === 'quarantined' && <button className="btn-ghost" onClick={() => transitionClaim(claim, 'superseded')}>Supersede</button>}</div></>}</article>)}</div>
        <div className="glass-panel reviewer-panel"><h3>Open source changes</h3><p>Changed or unavailable sources stop supporting high-risk claims until resolved.</p>{changes.length === 0 ? <div className="workflow-task-empty">No open source-change alerts.</div> : changes.map(item => <div className="review-event" key={item.id}><strong>{item.event_type.replaceAll('_', ' ')}</strong><span>{item.severity} · {new Date(item.detected_at).toLocaleString('en-IN')}</span>{item.details?.diff_preview && <pre className="source-diff">{item.details.diff_preview}</pre>}{reviewerRoles.includes('catalog_admin') && <><textarea className="form-input" value={comments[`change:${item.id}`] || ''} onChange={event => setComments(current => ({ ...current, [`change:${item.id}`]: event.target.value }))} placeholder="Resolution notes" /><div className="review-actions"><button className="btn-ghost" onClick={() => resolveChange(item, 'triaged')}>Mark triaged</button><button className="btn-primary" onClick={() => resolveChange(item, 'resolved')}>Resolve</button></div></>}</div>)}</div>
      </section>
      <section className="glass-panel reviewer-panel"><h3>Source version lifecycle</h3><p>Snapshots remain immutable; review status controls whether a source may support claims.</p>{sourceVersions.length === 0 ? <div className="workflow-task-empty">No source versions in the active queues.</div> : sourceVersions.map(item => <div className="review-event" key={item.id}><strong>{item.version_label}</strong><span>{item.review_status} · {item.fetch_status} · checked {new Date(item.last_checked_at).toLocaleString('en-IN')}</span>{reviewerRoles.includes('catalog_admin') && <><textarea className="form-input" value={comments[`source:${item.id}`] || ''} onChange={event => setComments(current => ({ ...current, [`source:${item.id}`]: event.target.value }))} placeholder="Source transition reason" /><div className="review-actions">{item.review_status === 'draft' && <button className="btn-ghost" onClick={() => transitionSource(item, 'in_review')}>Submit</button>}{item.review_status === 'in_review' && <button className="btn-primary" onClick={() => transitionSource(item, 'approved')}>Approve source</button>}{item.review_status === 'approved' && <button className="btn-ghost" onClick={() => transitionSource(item, 'quarantined')}>Quarantine</button>}{item.review_status === 'quarantined' && <button className="btn-ghost" onClick={() => transitionSource(item, 'superseded')}>Supersede</button>}</div></>}</div>)}</section>
      <section className="glass-panel reviewer-panel"><h3>Open claim contradictions</h3><p>Conflicting canonical claim values remain unpublished or suppressed until a catalog administrator records a resolution.</p>{conflicts.length === 0 ? <div className="workflow-task-empty">No unresolved claim contradictions.</div> : conflicts.map(item => <div className="review-event" key={item.id}><strong>{item.claim_id} ↔ {item.conflicting_claim_id}</strong><textarea className="form-input" value={comments[`conflict:${item.id}`] || ''} onChange={event => setComments(current => ({ ...current, [`conflict:${item.id}`]: event.target.value }))} placeholder="Resolution notes" />{reviewerRoles.includes('catalog_admin') && <div className="review-actions"><button className="btn-ghost" onClick={() => resolveConflict(item, 'not_a_conflict')}>Not a conflict</button><button className="btn-primary" onClick={() => resolveConflict(item, 'resolved')}>Resolved</button></div>}</div>)}</section>
      {reviewerRoles.includes('catalog_admin') && <section className="glass-panel reviewer-panel"><h3>Qualified reviewer assignments</h3><div className="review-actions"><input className="form-input" value={assignment.reviewer_user_id} onChange={event => setAssignment(current => ({ ...current, reviewer_user_id: event.target.value }))} placeholder="Reviewer user UUID" /><select className="form-input" value={assignment.reviewer_role} onChange={event => setAssignment(current => ({ ...current, reviewer_role: event.target.value }))}><option value="CA">CA</option><option value="CS">CS</option><option value="lawyer">Lawyer</option><option value="sector_specialist">Sector specialist</option><option value="bilingual_reviewer">Bilingual reviewer</option><option value="catalog_admin">Catalog admin</option></select><button className="btn-primary" onClick={createAssignment}>Assign</button></div>{assignments.map(item => <div className="review-event" key={item.id}><strong>{item.reviewer_role}</strong><span>{item.reviewer_user_id} · {item.active ? 'active' : 'inactive'}</span></div>)}</section>}
      <section className="glass-panel reviewer-panel"><h3><History size={16} /> Append-only review history</h3>{audit.slice(0, 30).map(item => <div className="review-event" key={item.id}><strong>{item.entity_type}: {item.action.replaceAll('_', ' ')}</strong><span>{item.from_state || 'new'} → {item.to_state || 'unchanged'} · {new Date(item.created_at).toLocaleString('en-IN')}</span><p>{item.reason}</p></div>)}</section>
    </div>
  );
}
