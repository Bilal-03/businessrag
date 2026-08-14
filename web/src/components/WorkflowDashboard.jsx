import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Bell, CheckCircle2, ClipboardCheck, ExternalLink, Plus, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react';
import { captureEvent, captureException } from '../lib/observability';
import BrandKicker from './BrandKicker';

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

function formatDateTime(value) {
  if (!value) return 'No reminder time';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

function sourceHref(value) {
  return typeof value === 'string' && /^https:\/\//i.test(value) ? value : null;
}

function isAuthoritativeSource(value) {
  const href = sourceHref(value);
  if (!href) return false;
  try {
    const hostname = new URL(href).hostname.toLowerCase();
    return hostname.endsWith('.gov.in') || hostname.endsWith('.nic.in') || hostname.endsWith('.org.in');
  } catch {
    return false;
  }
}

function isCurrentReviewedObligation(obligation, asOf = new Date()) {
  if (!obligation || obligation.published !== true || obligation.review_status !== 'published') return false;
  if (!obligation.source_citation?.trim() || !obligation.review_owner?.trim() || !obligation.reviewed_at) return false;
  if (!isAuthoritativeSource(obligation.source_url) || Number.isNaN(new Date(obligation.reviewed_at).getTime())) return false;
  const effectiveFrom = obligation.effective_from ? new Date(`${obligation.effective_from}T00:00:00`) : null;
  const effectiveTo = obligation.effective_to ? new Date(`${obligation.effective_to}T23:59:59`) : null;
  if (!effectiveFrom || Number.isNaN(effectiveFrom.getTime()) || effectiveFrom > asOf) return false;
  if (effectiveTo && (Number.isNaN(effectiveTo.getTime()) || effectiveTo < asOf)) return false;
  return new Date(obligation.reviewed_at) <= asOf;
}

const WorkflowDashboard = ({
  session,
  apiUrl,
  businesses = [],
  activeBusinessId,
  onSelectBusiness,
  onGoToBusinesses,
  onComplianceProfileUpdated,
}) => {
  const [obligations, setObligations] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [coverage, setCoverage] = useState(null);
  const [profileVersion, setProfileVersion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [sourceStatus, setSourceStatus] = useState('unavailable');
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDueDate, setNewTaskDueDate] = useState('');
  const [newTaskRecurrence, setNewTaskRecurrence] = useState('');
  const [newReminderTitle, setNewReminderTitle] = useState('');
  const [newReminderAt, setNewReminderAt] = useState('');
  const [newReminderTaskId, setNewReminderTaskId] = useState('');
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [answeringKey, setAnsweringKey] = useState(null);
  const [answerDrafts, setAnswerDrafts] = useState({});
  const [taskDetails, setTaskDetails] = useState({});
  const [taskNote, setTaskNote] = useState({});

  const headers = useMemo(() => ({
    Authorization: `Bearer ${session?.access_token || ''}`,
    'Content-Type': 'application/json',
  }), [session]);

  const loadWorkflow = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError('');
    setObligations([]);
    setQuestions([]);
    setCoverage(null);
    try {
      let nextObligations = [];
      if (activeBusinessId) {
        const planResponse = await fetch(`${apiUrl}/api/workflow/plan?business_id=${encodeURIComponent(activeBusinessId)}`, { headers });
        const plan = await parseResponse(planResponse);
        nextObligations = Array.isArray(plan.obligations) ? plan.obligations.filter(obligation => isCurrentReviewedObligation(obligation)) : [];
        const nextQuestions = Array.isArray(plan.questions) ? plan.questions : [];
        setQuestions(nextQuestions);
        setCoverage(plan.coverage || null);
        setProfileVersion(plan.profile_version || null);
        setSourceStatus(nextObligations.length > 0 ? 'ready' : nextQuestions.length > 0 ? 'partial' : 'empty');
      } else {
        setSourceStatus('needs_business');
      }
      setObligations(Array.isArray(nextObligations) ? nextObligations : []);

      if (activeBusinessId) {
        const tasksResponse = await fetch(`${apiUrl}/api/workflow/tasks?business_id=${encodeURIComponent(activeBusinessId)}`, { headers });
        const nextTasks = await parseResponse(tasksResponse);
        setTasks(Array.isArray(nextTasks) ? nextTasks : []);
        try {
          const remindersResponse = await fetch(`${apiUrl}/api/workflow/reminders?business_id=${encodeURIComponent(activeBusinessId)}`, { headers });
          const nextReminders = await parseResponse(remindersResponse);
          setReminders(Array.isArray(nextReminders) ? nextReminders : []);
        } catch {
          // Reminder migrations may trail the API during a rolling deploy.
          setReminders([]);
        }
      } else {
        setTasks([]);
        setReminders([]);
      }
    } catch (requestError) {
      setError(requestError.message || 'Compliance Plan data is unavailable.');
      setSourceStatus(requestError.status === 503 ? 'unavailable' : 'error');
      setObligations([]);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [activeBusinessId, apiUrl, headers, session]);

  useEffect(() => { loadWorkflow(); }, [loadWorkflow]);

  useEffect(() => {
    setAnswerDrafts(Object.fromEntries(questions.map(question => [question.key, question.current_value])));
  }, [questions]);

  const updateComplianceAnswer = async (key, value) => {
    if (!activeBusinessId || answeringKey) return;
    setAnsweringKey(key);
    setError('');
    try {
      const payload = key.startsWith('answers.')
        ? { answers: { [key.replace('answers.', '')]: value } }
        : { [key]: value };
      const response = await fetch(`${apiUrl}/api/workflow/businesses/${encodeURIComponent(activeBusinessId)}/compliance-profile`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(payload),
      });
      const updatedProfile = await parseResponse(response);
      onComplianceProfileUpdated?.(activeBusinessId, updatedProfile);
      captureEvent('compliance_profile_answered', { question_key: key, profile_version: profileVersion || 1 });
      await loadWorkflow();
    } catch (requestError) {
      captureException(requestError, { source: 'compliance_profile_update', question_key: key });
      setError(requestError.message || 'The compliance answer could not be saved.');
    } finally {
      setAnsweringKey(null);
    }
  };

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
          recurrence_rule: newTaskRecurrence ? { frequency: newTaskRecurrence } : null,
        }),
      });
      const task = await parseResponse(response);
      setTasks(current => [task, ...current]);
      captureEvent('workflow_task_created');
      setNewTaskTitle('');
      setNewTaskDueDate('');
      setNewTaskRecurrence('');
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
      captureEvent('workflow_task_updated', { status: changes.status || 'other' });
    } catch (requestError) {
      captureException(requestError, { source: 'workflow_task_update' });
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
      captureEvent('workflow_task_deleted');
    } catch (requestError) {
      captureException(requestError, { source: 'workflow_task_delete' });
      setError(requestError.message || 'The task could not be deleted.');
    } finally {
      setPendingDeleteId(null);
    }
  };

  const loadTaskDetails = async taskId => {
    if (taskDetails[taskId]?.open) {
      setTaskDetails(current => ({ ...current, [taskId]: { ...current[taskId], open: false } }));
      return;
    }
    try {
      const [evidence, history] = await Promise.all([
        fetch(`${apiUrl}/api/workflow/tasks/${encodeURIComponent(taskId)}/evidence`, { headers }).then(parseResponse),
        fetch(`${apiUrl}/api/workflow/tasks/${encodeURIComponent(taskId)}/history`, { headers }).then(parseResponse),
      ]);
      setTaskDetails(current => ({ ...current, [taskId]: { open: true, evidence, history } }));
    } catch (requestError) { setError(requestError.message || 'Task details are unavailable.'); }
  };

  const addTaskNote = async task => {
    const note = taskNote[task.id]?.trim();
    if (!note) return;
    try {
      const created = await fetch(`${apiUrl}/api/workflow/tasks/${encodeURIComponent(task.id)}/evidence`, {
        method: 'POST', headers,
        body: JSON.stringify({ business_id: task.business_id, evidence_type: 'note', title: 'Completion note', note }),
      }).then(parseResponse);
      setTaskDetails(current => ({ ...current, [task.id]: { ...(current[task.id] || {}), open: true, evidence: [created, ...(current[task.id]?.evidence || [])], history: current[task.id]?.history || [] } }));
      setTaskNote(current => ({ ...current, [task.id]: '' }));
    } catch (requestError) { setError(requestError.message || 'Task evidence could not be saved.'); }
  };

  const createReminder = async (event) => {
    event.preventDefault();
    if (!activeBusinessId || !newReminderTitle.trim() || !newReminderAt || saving) return;
    setSaving(true);
    setError('');
    try {
      const remindAt = new Date(newReminderAt);
      const response = await fetch(`${apiUrl}/api/workflow/reminders`, {
        method: 'POST', headers,
        body: JSON.stringify({
          business_id: activeBusinessId,
          task_id: newReminderTaskId || null,
          title: newReminderTitle.trim(),
          remind_at: remindAt.toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata',
          alert_offsets_days: [30, 14, 7, 1],
        }),
      });
      const reminder = await parseResponse(response);
      setReminders(current => [...current, reminder].sort((a, b) => new Date(a.remind_at) - new Date(b.remind_at)));
      setNewReminderTitle('');
      setNewReminderAt('');
      setNewReminderTaskId('');
      captureEvent('workflow_reminder_created');
    } catch (requestError) {
      setError(requestError.message || 'The reminder could not be created.');
    } finally {
      setSaving(false);
    }
  };

  const updateReminder = async (reminderId, changes) => {
    setError('');
    try {
      const response = await fetch(`${apiUrl}/api/workflow/reminders/${encodeURIComponent(reminderId)}`, {
        method: 'PATCH', headers, body: JSON.stringify(changes),
      });
      const reminder = await parseResponse(response);
      setReminders(current => current.map(item => item.id === reminderId ? reminder : item));
    } catch (requestError) {
      setError(requestError.message || 'The reminder could not be updated.');
    }
  };

  useEffect(() => {
    if (!session || typeof Notification === 'undefined' || Notification.permission !== 'granted') return undefined;
    let cancelled = false;
    const deliverDue = async () => {
      try {
        const response = await fetch(`${apiUrl}/api/workflow/reminders/due`, { headers });
        const due = await parseResponse(response);
        for (const reminder of Array.isArray(due) ? due : []) {
          if (cancelled) return;
          try { new Notification('BizGuide reminder', { body: reminder.title, icon: '/brand/bizguide-ai-app-icon.svg', badge: '/brand/bizguide-ai-app-icon.svg' }); } catch {}
          const delivered = await fetch(`${apiUrl}/api/workflow/reminders/${encodeURIComponent(reminder.id)}/delivered`, {
            method: 'POST', headers, body: JSON.stringify({
              delivered_at: new Date().toISOString(), alert_offset_days: reminder.alert_offset_days,
            }),
          });
          const updated = await parseResponse(delivered);
          setReminders(current => current.map(item => item.id === reminder.id ? updated : item));
        }
      } catch {
        // Delivery is opportunistic while the signed-in app is open. The
        // scheduled reminder remains intact for the next poll.
      }
    };
    deliverDue();
    const interval = window.setInterval(deliverDue, 60_000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [apiUrl, headers, session]);

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
          <BrandKicker icon={ClipboardCheck}>Source-backed workflow</BrandKicker>
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

          {sourceStatus === 'error' && (
            <div className="workflow-gated glass-panel" role="status">
              <ShieldAlert size={22} />
              <div>
                <h3>Published source records could not be verified</h3>
                <p>No obligation is shown because the catalog response failed its review or date checks. Try again later or verify the source catalog deployment.</p>
              </div>
            </div>
          )}

          {sourceStatus === 'empty' && (
            <div className="workflow-gated glass-panel" role="status">
              <ShieldAlert size={22} />
              <div>
                <h3>No confirmed applicable obligations</h3>
                <p>No active, qualified-review-backed record is confirmed for this business and date. This is not a complete compliance list; check missing inputs and coverage limitations below.</p>
              </div>
            </div>
          )}

          {coverage?.state && coverage.state.status !== 'available' && (
            <div className="workflow-coverage glass-panel" role="status">
              <ShieldAlert size={20} />
              <div>
                <h3>{coverage.state.jurisdiction || 'State'} catalog coverage: {coverage.state.status.replace('_', ' ')}</h3>
                <p>{coverage.state.message}</p>
                {coverage.state.blocked_modules?.length > 0 && <p><strong>Blocked modules:</strong> {coverage.state.blocked_modules.join(', ').replaceAll('_', ' ')}</p>}
              </div>
            </div>
          )}

          {coverage?.central && coverage.central.status !== 'available' && (
            <div className="workflow-coverage glass-panel" role="status">
              <ShieldAlert size={20} />
              <div><h3>Central catalog coverage: {coverage.central.status.replace('_', ' ')}</h3><p>{coverage.central.message}</p>{coverage.central.blocked_modules?.length > 0 && <p><strong>Blocked modules:</strong> {coverage.central.blocked_modules.join(', ').replaceAll('_', ' ')}</p>}</div>
            </div>
          )}

          {questions.length > 0 && (
            <section className="workflow-section workflow-questions" aria-labelledby="needs-input-title">
              <div className="workflow-section-heading">
                <div>
                  <h3 id="needs-input-title">Needs your input</h3>
                  <p>Uncertain requirements stay hidden until these facts are confirmed.</p>
                </div>
              </div>
              <div className="question-list">
                {questions.map(question => (
                  <div className="question-card glass-panel" key={question.key}>
                    <div>
                      <h4>{question.label}</h4>
                      <p>{question.description}</p>
                    </div>
                    {question.answer_type === 'multi_select' ? (
                      <div className="question-multi-options">
                        {question.options.map(option => {
                          const currentValues = Array.isArray(answerDrafts[question.key]) ? answerDrafts[question.key] : [];
                          const selected = currentValues.includes(option.value);
                          const nextValues = selected
                            ? currentValues.filter(value => value !== option.value)
                            : [...currentValues, option.value];
                          return (
                            <button
                              type="button"
                              key={option.value}
                              className={`question-option ${selected ? 'selected' : ''}`}
                              disabled={answeringKey === question.key}
                              onClick={() => setAnswerDrafts(current => ({ ...current, [question.key]: nextValues }))}
                              aria-pressed={selected}
                            >
                              {option.label}
                            </button>
                          );
                        })}
                        <button type="button" className="btn-ghost question-none" disabled={answeringKey === question.key} onClick={() => updateComplianceAnswer(question.key, answerDrafts[question.key] || [])}>Save activities</button>
                        <button type="button" className="btn-ghost question-none" disabled={answeringKey === question.key} onClick={() => updateComplianceAnswer(question.key, [])}>None apply</button>
                      </div>
                    ) : (
                      <select
                        className="form-input question-select"
                        aria-label={question.label}
                        defaultValue=""
                        disabled={answeringKey === question.key}
                        onChange={event => {
                          const raw = event.target.value;
                          const value = question.answer_type === 'boolean' ? raw === 'true' : raw;
                          if (raw) updateComplianceAnswer(question.key, value);
                        }}
                      >
                        <option value="" disabled>Select an answer</option>
                        {question.options.map(option => <option key={String(option.value)} value={String(option.value)}>{option.label}</option>)}
                      </select>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {obligations.length > 0 && (
            <section className="workflow-section" aria-labelledby="published-obligations-title">
              <div className="workflow-section-heading">
                <div>
                  <h3 id="published-obligations-title">Published obligations</h3>
                  <p>Only reviewed, current records confirmed applicable to this business are shown.</p>
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
                      {obligation.applicability_reason?.length > 0 && (
                        <div className="obligation-applicability">
                          <span>Why this applies</span>
                          <ul>{obligation.applicability_reason.map(reason => <li key={reason}>{reason}</li>)}</ul>
                        </div>
                      )}
                      <div className="obligation-citation">
                        <span>Source citation</span>
                        <p>{obligation.source_citation}</p>
                      </div>
                      <div className="obligation-review">
                        Reviewed by {obligation.review_owner} · {formatDate(obligation.reviewed_at?.slice(0, 10))}
                      </div>
                      <div className="obligation-deadline"><strong>Deadline:</strong> {obligation.deadline_status === 'determined' ? formatDate(obligation.due_date) : 'Not determined'} · {obligation.due_date_basis || 'No reviewed formula is available.'}</div>
                      {obligation.evidence_requirements?.length > 0 && <div className="obligation-evidence"><strong>Evidence checklist:</strong> {obligation.evidence_requirements.map(item => typeof item === 'string' ? item : item.label || item.type).join(', ')}</div>}
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
              <select className="form-input" aria-label="Task recurrence" value={newTaskRecurrence} onChange={event => setNewTaskRecurrence(event.target.value)} disabled={saving}>
                <option value="">Does not repeat</option><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option><option value="yearly">Yearly</option>
              </select>
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
                    <button type="button" className="btn-ghost" onClick={() => loadTaskDetails(task.id)}>{taskDetails[task.id]?.open ? 'Hide details' : 'Evidence & history'}</button>
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
                    {taskDetails[task.id]?.open && <div className="task-detail-panel">
                      <p><strong>Series:</strong> {task.recurrence_rule?.frequency ? `${task.recurrence_rule.frequency}, occurrence ${task.occurrence_number}` : 'One-time task'}</p>
                      <div><strong>Evidence:</strong>{taskDetails[task.id].evidence?.length ? <ul>{taskDetails[task.id].evidence.map(item => <li key={item.id}>{item.title}{item.note ? ` — ${item.note}` : ''}</li>)}</ul> : <p>No evidence attached.</p>}</div>
                      <div className="task-note-form"><input className="form-input" aria-label={`Completion note for ${task.title}`} value={taskNote[task.id] || ''} onChange={event => setTaskNote(current => ({ ...current, [task.id]: event.target.value }))} placeholder="Add completion evidence note" /><button type="button" className="btn-ghost" onClick={() => addTaskNote(task)}>Add note</button></div>
                      <div><strong>Status history:</strong>{taskDetails[task.id].history?.length ? <ul>{taskDetails[task.id].history.map(item => <li key={item.id}>{item.from_status || 'created'} → {item.to_status} · {formatDateTime(item.changed_at)}</li>)}</ul> : <p>No status changes yet.</p>}</div>
                    </div>}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="workflow-section" aria-labelledby="reminders-title">
            <div className="workflow-section-heading">
              <div><h3 id="reminders-title">In-app reminders</h3><p>Default alerts are scheduled 30, 14, 7, and 1 day before the reminder date in your timezone.</p></div>
            </div>
            <form className="workflow-reminder-form glass-panel" onSubmit={createReminder}>
              <input className="form-input" value={newReminderTitle} onChange={event => setNewReminderTitle(event.target.value)} placeholder="Reminder title" maxLength={240} />
              <select className="form-input" value={newReminderTaskId} onChange={event => setNewReminderTaskId(event.target.value)}>
                <option value="">General business reminder</option>
                {tasks.filter(task => task.status !== 'dismissed').map((task, index) => <option key={task.id} value={task.id}>Task {index + 1}</option>)}
              </select>
              <input className="form-input" type="datetime-local" value={newReminderAt} onChange={event => setNewReminderAt(event.target.value)} />
              <button type="submit" className="btn-primary" disabled={saving || !newReminderTitle.trim() || !newReminderAt}><Bell size={16} /> Add reminder</button>
            </form>
            {reminders.filter(reminder => reminder.status !== 'dismissed').length === 0 ? (
              <div className="workflow-task-empty"><Bell size={18} /> No scheduled reminders.</div>
            ) : (
              <div className="workflow-task-list">
                {reminders.filter(reminder => reminder.status !== 'dismissed').map(reminder => (
                  <div className="workflow-task-row glass-panel" key={reminder.id}>
                    <div className="workflow-task-main"><div className="workflow-task-title">{reminder.title}</div><div className="workflow-task-meta">{formatDateTime(reminder.snoozed_until || reminder.remind_at)} · {reminder.timezone}</div></div>
                    <button type="button" className="btn-ghost" onClick={() => updateReminder(reminder.id, { status: 'snoozed', snoozed_until: new Date(Date.now() + 86400000).toISOString() })}>Snooze 1 day</button>
                    <button type="button" className="icon-btn task-delete-button" onClick={() => updateReminder(reminder.id, { status: 'dismissed' })} aria-label={`Dismiss reminder ${reminder.title}`}><Trash2 size={16} /></button>
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
