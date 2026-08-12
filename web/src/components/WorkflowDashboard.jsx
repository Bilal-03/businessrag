import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, ClipboardCheck, ExternalLink, Plus, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react';

const TASK_STATUSES = [
  { value: 'todo', label: 'To do' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'done', label: 'Done' },
  { value: 'dismissed', label: 'Dismissed' },
];

async function parseResponse(response) {
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) {
    const error = new Error(data.detail || 'Compliance Plan data is unavailable.');
    error.status = response.status;
    throw error;
  }
  return data;
}

function formatDate(value) {
  if (!value) return 'No due date';
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function sourceHref(value) {
  return typeof value === 'string' && /^https:\/\//i.test(value) ? value : null;
}

const WorkflowDashboard = ({
  session,
  apiUrl,
  businesses = [],
  activeBusinessId,
  businessJurisdiction,
  onSelectBusiness,
  onGoToBusinesses,
}) => {
  const [obligations, setObligations] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [sourceStatus, setSourceStatus] = useState('unavailable');
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDueDate, setNewTaskDueDate] = useState('');
  const [pendingDeleteId, setPendingDeleteId] = useState(null);

  const headers = useMemo(() => ({
    Authorization: `Bearer ${session?.access_token || ''}`,
    'Content-Type': 'application/json',
  }), [session]);

  const loadWorkflow = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError('');
    try {
      let nextObligations = [];
      if (businessJurisdiction?.trim()) {
        const obligationsResponse = await fetch(`${apiUrl}/api/workflow/obligations?jurisdiction=${encodeURIComponent(businessJurisdiction.trim())}`, { headers });
        nextObligations = await parseResponse(obligationsResponse);
        setSourceStatus(nextObligations.length > 0 ? 'ready' : 'empty');
      } else {
        setSourceStatus('needs_jurisdiction');
      }
      setObligations(Array.isArray(nextObligations) ? nextObligations : []);

      if (activeBusinessId) {
        const tasksResponse = await fetch(`${apiUrl}/api/workflow/tasks?business_id=${encodeURIComponent(activeBusinessId)}`, { headers });
        const nextTasks = await parseResponse(tasksResponse);
        setTasks(Array.isArray(nextTasks) ? nextTasks : []);
      } else {
        setTasks([]);
      }
    } catch (requestError) {
      setError(requestError.message || 'Compliance Plan data is unavailable.');
      setSourceStatus(requestError.status === 503 ? 'unavailable' : 'error');
      setObligations([]);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [activeBusinessId, apiUrl, businessJurisdiction, headers, session]);

  useEffect(() => { loadWorkflow(); }, [loadWorkflow]);

  const createTask = async (event) => {
    event.preventDefault();
    if (!activeBusinessId || !newTaskTitle.trim() || saving) return;
    setSaving(true);
    setError('');
    try {
      const response = await fetch(`${apiUrl}/api/workflow/tasks`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          business_id: activeBusinessId,
          title: newTaskTitle.trim(),
          due_date: newTaskDueDate || null,
        }),
      });
      const task = await parseResponse(response);
      setTasks(current => [task, ...current]);
      setNewTaskTitle('');
      setNewTaskDueDate('');
    } catch (requestError) {
      setError(requestError.message || 'The planning task could not be created.');
    } finally {
      setSaving(false);
    }
  };

  const updateTask = async (taskId, changes) => {
    setError('');
    try {
      const response = await fetch(`${apiUrl}/api/workflow/tasks/${encodeURIComponent(taskId)}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(changes),
      });
      const updatedTask = await parseResponse(response);
      setTasks(current => current.map(task => task.id === taskId ? updatedTask : task));
    } catch (requestError) {
      setError(requestError.message || 'The task could not be updated.');
    }
  };

  const deleteTask = async (taskId) => {
    if (pendingDeleteId !== taskId) {
      setPendingDeleteId(taskId);
      window.setTimeout(() => setPendingDeleteId(current => current === taskId ? null : current), 4000);
      return;
    }
    setError('');
    try {
      const response = await fetch(`${apiUrl}/api/workflow/tasks/${encodeURIComponent(taskId)}`, {
        method: 'DELETE',
        headers,
      });
      await parseResponse(response);
      setTasks(current => current.filter(task => task.id !== taskId));
    } catch (requestError) {
      setError(requestError.message || 'The task could not be deleted.');
    } finally {
      setPendingDeleteId(null);
    }
  };

  const doneCount = tasks.filter(task => task.status === 'done').length;
  const selectedBusinessId = businesses.some(business => business.id === activeBusinessId)
    ? activeBusinessId
    : '';
  const businessOptionLabels = useMemo(() => {
    const bases = businesses.map(business => [
      business.id,
      [business.name, business.type, business.state].filter(Boolean).join(' · ') || 'Unnamed business',
    ]);
    const totals = new Map();
    bases.forEach(([, base]) => totals.set(base, (totals.get(base) || 0) + 1));
    const occurrences = new Map();
    return new Map(bases.map(([businessId, base]) => {
      const occurrence = (occurrences.get(base) || 0) + 1;
      occurrences.set(base, occurrence);
      return [businessId, totals.get(base) > 1 ? `${base} · ${occurrence}` : base];
    }));
  }, [businesses]);

  const handleBusinessChange = (event) => {
    const nextBusiness = businesses.find(business => business.id === event.target.value);
    if (nextBusiness) onSelectBusiness?.(nextBusiness.id, nextBusiness);
  };

  return (
    <div className="panel-container workflow-container">
      <div className="panel-header">
        <div>
          <div className="workflow-kicker"><ClipboardCheck size={15} /> Source-backed workflow</div>
          <h2 className="panel-title">Compliance Plan</h2>
          <p className="panel-subtitle">Track verified obligations and your own planning tasks for the selected business.</p>
        </div>
        <div className="workflow-header-controls">
          {businesses.length > 0 && (
            <label className="workflow-business-field" htmlFor="workflow-business-select">
              <span>Business workspace</span>
              <select
                id="workflow-business-select"
                className="form-input workflow-business-select"
                value={selectedBusinessId}
                onChange={handleBusinessChange}
                aria-label="Select business workspace"
              >
                <option value="" disabled>Select a business</option>
                {businesses.map(business => (
                  <option key={business.id} value={business.id}>
                    {businessOptionLabels.get(business.id)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button type="button" className="btn-ghost workflow-refresh" onClick={loadWorkflow} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="workflow-alert" role="alert">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      )}

      {!activeBusinessId ? (
        <div className="workflow-empty glass-panel">
          <div className="workflow-empty-icon"><ClipboardCheck size={28} /></div>
          <h3>Select a business first</h3>
          <p>Compliance requirements depend on entity type and jurisdiction. Choose a business profile before creating tasks or interpreting obligations.</p>
          <button type="button" className="btn-primary" onClick={onGoToBusinesses}>Go to My Businesses</button>
        </div>
      ) : (
        <>
          <div className="workflow-stat-grid" aria-label="Compliance plan summary">
            <div className="workflow-stat glass-panel"><span>Published obligations</span><strong>{loading ? '—' : obligations.length}</strong></div>
            <div className="workflow-stat glass-panel"><span>Planning tasks</span><strong>{loading ? '—' : tasks.length}</strong></div>
            <div className="workflow-stat glass-panel"><span>Tasks complete</span><strong>{loading ? '—' : `${doneCount}/${tasks.length}`}</strong></div>
          </div>

          {sourceStatus === 'unavailable' && (
            <div className="workflow-gated glass-panel" role="status">
              <ShieldAlert size={22} />
              <div>
                <h3>Source-backed obligations are not enabled yet</h3>
                <p>The workflow schema or source catalog is unavailable. The legacy checklist is intentionally not shown, and no compliance claim is being made.</p>
              </div>
            </div>
          )}

          {sourceStatus === 'empty' && (
            <div className="workflow-gated glass-panel" role="status">
              <ShieldAlert size={22} />
              <div>
                <h3>No published obligations yet</h3>
                <p>The database is reachable, but no source-versioned obligations are published for this beta. Add planning tasks only; do not treat this as a complete compliance list.</p>
              </div>
            </div>
          )}

          {sourceStatus === 'needs_jurisdiction' && (
            <div className="workflow-gated glass-panel" role="status">
              <ShieldAlert size={22} />
              <div>
                <h3>Add a primary state before viewing obligations</h3>
                <p>Jurisdiction is required to avoid presenting a misleading universal compliance list. Update this business profile, then refresh.</p>
              </div>
            </div>
          )}

          {sourceStatus === 'ready' && (
            <section className="workflow-section" aria-labelledby="published-obligations-title">
              <div className="workflow-section-heading">
                <div>
                  <h3 id="published-obligations-title">Published obligations</h3>
                  <p>Only records with an effective source window are shown.</p>
                </div>
              </div>
              <div className="obligation-list">
                {obligations.map(obligation => {
                  const href = sourceHref(obligation.source_url);
                  return (
                    <article key={obligation.id} className="obligation-card glass-panel">
                      <div className="obligation-card-top">
                        <span className="obligation-jurisdiction">{obligation.jurisdiction}</span>
                        <span className="obligation-version">Source {obligation.source_version}</span>
                      </div>
                      <h4>{obligation.title}</h4>
                      <p>{obligation.description}</p>
                      <div className="obligation-card-footer">
                        <span>Effective {formatDate(obligation.effective_from)}{obligation.effective_to ? ` – ${formatDate(obligation.effective_to)}` : ''}</span>
                        {href && <a href={href} target="_blank" rel="noreferrer">Open source <ExternalLink size={13} /></a>}
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          )}

          <section className="workflow-section" aria-labelledby="planning-tasks-title">
            <div className="workflow-section-heading">
              <div>
                <h3 id="planning-tasks-title">Planning tasks</h3>
                <p>These are your tasks, not legal or tax advice.</p>
              </div>
            </div>
            <form className="workflow-task-form glass-panel" onSubmit={createTask}>
              <label className="sr-only" htmlFor="new-workflow-task">Task title</label>
              <input id="new-workflow-task" className="form-input" value={newTaskTitle} onChange={event => setNewTaskTitle(event.target.value)} placeholder="Add a planning task" maxLength={240} disabled={sourceStatus === 'unavailable' || saving} />
              <label className="sr-only" htmlFor="new-workflow-due-date">Due date</label>
              <input id="new-workflow-due-date" className="form-input task-date-input" type="date" value={newTaskDueDate} onChange={event => setNewTaskDueDate(event.target.value)} disabled={sourceStatus === 'unavailable' || saving} />
              <button type="submit" className="btn-primary" disabled={sourceStatus === 'unavailable' || saving || !newTaskTitle.trim()}><Plus size={16} /> Add task</button>
            </form>
            {tasks.length === 0 ? (
              <div className="workflow-task-empty"><CheckCircle2 size={18} /> No planning tasks yet.</div>
            ) : (
              <div className="workflow-task-list">
                {tasks.map(task => (
                  <div className={`workflow-task-row glass-panel status-${task.status}`} key={task.id}>
                    <div className="workflow-task-main">
                      <div className="workflow-task-title">{task.title}</div>
                      <div className="workflow-task-meta">{formatDate(task.due_date)}</div>
                    </div>
                    <select className="form-input task-status-select" aria-label={`Status for ${task.title}`} value={task.status} onChange={event => updateTask(task.id, { status: event.target.value })}>
                      {TASK_STATUSES.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    <button
                      type="button"
                      className={`icon-btn task-delete-button ${pendingDeleteId === task.id ? 'confirming' : ''}`}
                      onClick={() => deleteTask(task.id)}
                      aria-label={`${pendingDeleteId === task.id ? 'Confirm deletion of' : 'Delete'} task ${task.title}`}
                      title={pendingDeleteId === task.id ? 'Click again to confirm deletion' : 'Delete task'}
                    >
                      <Trash2 size={16} />
                      {pendingDeleteId === task.id && <span>Confirm delete</span>}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
};

export default WorkflowDashboard;
