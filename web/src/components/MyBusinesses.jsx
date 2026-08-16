import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Building2, Trash2, Edit2, ChevronRight, X, Check, ChevronDown } from 'lucide-react';
import { captureEvent } from '../lib/observability';
import { INDUSTRY_CODE_BY_LABEL, INDUSTRY_OPTIONS, activityOptionsFor } from '../lib/complianceCatalog';

const BUSINESS_TYPES = ['Private Limited (Pvt Ltd)', 'Limited Liability Partnership (LLP)', 'One Person Company (OPC)', 'Sole Proprietorship', 'Partnership Firm', 'Public Limited'];
const INDUSTRIES = INDUSTRY_OPTIONS.map(option => option.label);
const STATUS_OPTIONS = ['Planning', 'Registered', 'Operating', 'On Hold'];
const STATE_OPTIONS = ['Andhra Pradesh', 'Delhi', 'Gujarat', 'Karnataka', 'Kerala', 'Maharashtra', 'Tamil Nadu', 'Telangana', 'Uttar Pradesh', 'West Bengal', 'Other / Multi-state'];
const GST_OPTIONS = ['Unknown', 'Registered', 'Not registered', 'Not applicable'];
const GST_VALUE = { Unknown: null, Registered: 'registered', 'Not registered': 'not_registered', 'Not applicable': 'not_applicable' };
const GST_LABEL = Object.fromEntries(Object.entries(GST_VALUE).map(([label, value]) => [value, label]));
const WORKFORCE_OPTIONS = ['Unknown', '0', '1–9', '10–19', '20–49', '50–99', '100+'];
const WORKFORCE_VALUE = { Unknown: null, '0': '0', '1–9': '1_to_9', '10–19': '10_to_19', '20–49': '20_to_49', '50–99': '50_to_99', '100+': '100_plus' };
const WORKFORCE_LABEL = Object.fromEntries(Object.entries(WORKFORCE_VALUE).map(([label, value]) => [value, label]));
const TURNOVER_OPTIONS = ['Unknown', 'Under ₹20 lakh', '₹20 lakh–₹1 crore', '₹1–₹5 crore', 'Over ₹5 crore'];
const TURNOVER_VALUE = { Unknown: null, 'Under ₹20 lakh': 'under_20_lakh', '₹20 lakh–₹1 crore': '20_lakh_to_1_crore', '₹1–₹5 crore': '1_to_5_crore', 'Over ₹5 crore': 'over_5_crore' };
const TURNOVER_LABEL = Object.fromEntries(Object.entries(TURNOVER_VALUE).map(([label, value]) => [value, label]));

/* ── Custom styled dropdown ── */
const CustomSelect = ({ id, value, onChange, options, placeholder, ariaLabel }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const triggerRef = useRef(null);

  const focusOption = (index) => {
    const nextIndex = Math.max(0, Math.min(options.length - 1, index));
    window.requestAnimationFrame(() => {
      ref.current?.querySelector(`[data-option-index="${nextIndex}"]`)?.focus();
    });
  };

  const openMenu = () => {
    const selectedIndex = Math.max(0, options.indexOf(value));
    setOpen(true);
    window.requestAnimationFrame(() => {
      ref.current?.querySelector(`[data-option-index="${selectedIndex}"]`)?.focus();
    });
  };

  const closeMenu = (restoreFocus = true) => {
    setOpen(false);
    if (restoreFocus) window.requestAnimationFrame(() => triggerRef.current?.focus());
  };

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="custom-select" ref={ref}>
      <button
        type="button"
        ref={triggerRef}
        id={id}
        className="custom-select-trigger form-input"
        onClick={() => (open ? closeMenu(false) : openMenu())}
        onKeyDown={e => {
          if (e.key === 'Escape') closeMenu(false);
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!open) openMenu();
            else if (e.key === 'ArrowDown') focusOption(options.indexOf(value) + 1);
            else if (e.key === 'ArrowUp') focusOption(options.indexOf(value) - 1);
          }
        }}
        aria-label={ariaLabel || placeholder || 'Select an option'}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${id}-options` : undefined}
      >
        <span className="custom-select-value">{value || placeholder || 'Select…'}</span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }} className="custom-select-chevron">
          <ChevronDown size={16} />
        </motion.span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul
            className="custom-select-menu"
            id={`${id}-options`}
            role="listbox"
            aria-label={ariaLabel || placeholder || 'Options'}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
          >
            {options.map((opt, optionIndex) => (
              <li
                key={opt}
                className={`custom-select-option ${opt === value ? 'selected' : ''}`}
                data-option-index={optionIndex}
                onClick={() => { onChange(opt); closeMenu(); }}
                onKeyDown={e => {
                  if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    focusOption(optionIndex + 1);
                  } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    focusOption(optionIndex - 1);
                  } else if (e.key === 'Home') {
                    e.preventDefault();
                    focusOption(0);
                  } else if (e.key === 'End') {
                    e.preventDefault();
                    focusOption(options.length - 1);
                  } else if (e.key === 'Escape') {
                    e.preventDefault();
                    closeMenu();
                  } else if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onChange(opt);
                    closeMenu();
                  }
                }}
                role="option"
                aria-selected={opt === value}
                tabIndex={0}
              >
                {opt}
                {opt === value && <Check size={14} className="custom-select-check" />}
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
};

const STATUS_COLORS = {
  'Planning':   { bg: 'rgba(234, 179, 8, 0.15)',  text: '#fbbf24', border: 'rgba(234,179,8,0.3)' },
  'Registered': { bg: 'rgba(159, 63, 41, 0.15)', text: '#9f3f29', border: 'rgba(159,63,41,0.3)' },
  'Operating':  { bg: 'rgba(34, 197, 94, 0.15)',  text: '#4ade80', border: 'rgba(34,197,94,0.3)' },
  'On Hold':    { bg: 'rgba(148, 163, 184, 0.1)', text: '#94a3b8', border: 'rgba(148,163,184,0.2)' },
};

const QUICK_ACTIONS = [
  { label: 'GST Registration', query: 'How do I register for GST for my business?' },
  { label: 'Tax Filing', query: 'What are the income tax filing requirements for my business type?' },
  { label: 'Compliance', query: 'What are the annual compliance requirements?' },
  { label: 'Licenses', query: 'What licenses do I need for my business?' },
];

const defaultForm = {
  name: '',
  type: BUSINESS_TYPES[0],
  industry: INDUSTRIES[0],
  industryCode: INDUSTRY_OPTIONS[0].code,
  regulatedActivities: [],
  gstRegistrationStatus: null,
  employeeCountBand: null,
  turnoverBand: null,
  hasPhysicalEstablishment: null,
  usesContractors: null,
  handlesPersonalData: null,
  state: '',
  status: STATUS_OPTIONS[0],
  description: '',
};

const MyBusinesses = ({ businesses = [], onBusinessesChange, onAskQuestion, activeBusinessId, onSelectBusiness }) => {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(defaultForm);
  const [expandedId, setExpandedId] = useState(null);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const activeBusiness = businesses.find(business => business.id === activeBusinessId);

  const save = (updated) => {
    onBusinessesChange?.(updated);
  };

  const handleSubmit = () => {
    if (!form.name.trim()) return;
    if (editingId) {
      save(businesses.map(b => b.id === editingId ? { ...b, ...form } : b));
      captureEvent('business_updated');
      setEditingId(null);
    } else {
      const newBusiness = {
        ...form,
        id: globalThis.crypto?.randomUUID?.() || Date.now().toString(),
        createdAt: new Date().toLocaleDateString('en-IN'),
      };
      save([...businesses, newBusiness]);
      captureEvent('business_created');
      onSelectBusiness?.(newBusiness.id, newBusiness);
    }
    setForm(defaultForm);
    setShowForm(false);
  };

  const handleEdit = (b) => {
    setForm({
      name: b.name,
      type: b.type,
      industry: b.industry,
      industryCode: b.industryCode || INDUSTRY_CODE_BY_LABEL[b.industry] || 'other',
      regulatedActivities: b.regulatedActivities || [],
      gstRegistrationStatus: b.gstRegistrationStatus ?? null,
      employeeCountBand: b.employeeCountBand ?? null,
      turnoverBand: b.turnoverBand ?? null,
      hasPhysicalEstablishment: b.hasPhysicalEstablishment ?? null,
      usesContractors: b.usesContractors ?? null,
      handlesPersonalData: b.handlesPersonalData ?? null,
      state: b.state || '',
      status: b.status,
      description: b.description || '',
    });
    setEditingId(b.id);
    setShowForm(true);
  };

  const handleDelete = (id) => {
    if (pendingDeleteId !== id) {
      setPendingDeleteId(id);
      window.setTimeout(() => setPendingDeleteId(current => current === id ? null : current), 4000);
      return;
    }
    save(businesses.filter(b => b.id !== id));
    captureEvent('business_deleted');
    if (expandedId === id) setExpandedId(null);
    if (activeBusinessId === id) onSelectBusiness?.(null, null);
    setPendingDeleteId(null);
  };

  const handleCancel = () => {
    setForm(defaultForm);
    setEditingId(null);
    setShowForm(false);
  };

  useEffect(() => {
    if (!showForm) return undefined;
    const previousActive = document.activeElement;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        handleCancel();
        return;
      }
      if (event.key !== 'Tab') return;
      const dialog = document.querySelector('[role="dialog"]');
      if (!dialog) return;
      const focusable = [...dialog.querySelectorAll('button, input, textarea, [tabindex]:not([tabindex="-1"])')].filter(element => !element.disabled);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    window.requestAnimationFrame(() => document.getElementById('business-name')?.focus());
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previousActive?.focus?.();
    };
  }, [showForm]);

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">My Businesses</h2>
          <p className="panel-subtitle">Manage your registered business profiles and get tailored compliance guidance.</p>
        </div>
        <div className="panel-header-actions">
          {activeBusiness && (
            <div className="panel-context-badge" role="status">
              <span className="panel-context-dot" aria-hidden="true" />
              Selected: {activeBusiness.name}
            </div>
          )}
          <motion.button
            whileHover={{ y: -1 }}
            whileTap={{ y: 0 }}
            className="btn-primary"
            onClick={() => { setShowForm(true); setEditingId(null); setForm(defaultForm); }}
          >
            <Plus size={18} /> Add Business
          </motion.button>
        </div>
      </div>

      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            onClick={handleCancel}
            role="presentation"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.92, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92, y: 20 }}
              className="modal-card"
              onClick={e => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-labelledby="business-modal-title"
            >
              <div className="modal-header">
                <h3 id="business-modal-title">{editingId ? 'Edit Business' : 'Add New Business'}</h3>
                <button className="icon-btn" onClick={handleCancel} aria-label="Close business form"><X size={20} /></button>
              </div>
              <div className="form-grid">
                <div className="form-group full">
                  <label htmlFor="business-name">Business Name *</label>
                  <input id="business-name" className="form-input" placeholder="e.g. Acme Technologies" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div className="form-group">
                  <label htmlFor="business-type">Business Type</label>
                  <CustomSelect id="business-type" ariaLabel="Business type" value={form.type} onChange={v => setForm({ ...form, type: v })} options={BUSINESS_TYPES} />
                </div>
                <div className="form-group">
                  <label htmlFor="business-industry">Industry</label>
                  <CustomSelect
                    id="business-industry"
                    ariaLabel="Industry"
                    value={form.industry}
                    onChange={v => setForm({ ...form, industry: v, industryCode: INDUSTRY_CODE_BY_LABEL[v] || 'other' })}
                    options={INDUSTRIES}
                  />
                </div>
                <fieldset className="form-group full activity-fieldset">
                  <legend>Regulated activities</legend>
                  <p>Choose every activity this business actually performs. Industry alone does not prove that a requirement applies.</p>
                  <div className="activity-option-grid">
                    {activityOptionsFor(form.industryCode, form.regulatedActivities).map(option => (
                      <label className="activity-option" key={option.value}>
                        <input
                          type="checkbox"
                          checked={form.regulatedActivities.includes(option.value)}
                          onChange={event => setForm(current => ({
                            ...current,
                            regulatedActivities: event.target.checked
                              ? [...new Set([...current.regulatedActivities, option.value])]
                              : current.regulatedActivities.filter(value => value !== option.value),
                          }))}
                        />
                        <span>{option.label}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
                <div className="form-group">
                  <label htmlFor="business-state">Primary state / jurisdiction</label>
                  <CustomSelect id="business-state" ariaLabel="Primary state or jurisdiction" value={form.state} onChange={v => setForm({ ...form, state: v })} options={STATE_OPTIONS} placeholder="Choose a state" />
                </div>
                <div className="form-group">
                  <label htmlFor="business-status">Status</label>
                  <CustomSelect id="business-status" ariaLabel="Business status" value={form.status} onChange={v => setForm({ ...form, status: v })} options={STATUS_OPTIONS} />
                </div>
                <div className="form-group">
                  <label htmlFor="business-gst-status">GST registration</label>
                  <CustomSelect id="business-gst-status" ariaLabel="GST registration status" value={GST_LABEL[form.gstRegistrationStatus] || 'Unknown'} onChange={v => setForm({ ...form, gstRegistrationStatus: GST_VALUE[v] })} options={GST_OPTIONS} />
                </div>
                <div className="form-group">
                  <label htmlFor="business-turnover">Annual turnover band</label>
                  <CustomSelect id="business-turnover" ariaLabel="Annual turnover band" value={TURNOVER_LABEL[form.turnoverBand] || 'Unknown'} onChange={v => setForm({ ...form, turnoverBand: TURNOVER_VALUE[v] })} options={TURNOVER_OPTIONS} />
                </div>
                <div className="form-group">
                  <label htmlFor="business-workforce">Employee-count band</label>
                  <CustomSelect id="business-workforce" ariaLabel="Employee count band" value={WORKFORCE_LABEL[form.employeeCountBand] || 'Unknown'} onChange={v => setForm({ ...form, employeeCountBand: WORKFORCE_VALUE[v] })} options={WORKFORCE_OPTIONS} />
                </div>
                <fieldset className="form-group profile-facts">
                  <legend>Confirmed operating facts</legend>
                  {[
                    ['hasPhysicalEstablishment', 'Uses a physical establishment'],
                    ['usesContractors', 'Engages contractors or contract workers'],
                    ['handlesPersonalData', 'Processes personal data'],
                  ].map(([key, label]) => (
                    <label key={key} className="activity-option">
                      <input type="checkbox" checked={form[key] === true} onChange={event => setForm(current => ({ ...current, [key]: event.target.checked ? true : null }))} />
                      <span>{label}</span>
                    </label>
                  ))}
                  <p>Unchecked means unknown, not “no”; confirm negative answers in Compliance Plan when a reviewed rule asks.</p>
                </fieldset>
                <div className="form-group full">
                  <label htmlFor="business-description">Description (optional)</label>
                  <textarea id="business-description" className="form-input" rows={3} placeholder="Brief description of your business..." value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
                </div>
              </div>
              <div className="modal-actions">
                <button className="btn-ghost" onClick={handleCancel}>Cancel</button>
                <motion.button whileHover={{ y: -1 }} className="btn-primary" onClick={handleSubmit}>
                  <Check size={16} /> {editingId ? 'Save Changes' : 'Add Business'}
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {businesses.length === 0 ? (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="empty-state">
          <div className="empty-icon"><Building2 size={48} /></div>
          <h3>No businesses yet</h3>
          <p>Add your first business profile to get personalized compliance guidance and track your requirements.</p>
          <motion.button whileHover={{ y: -1 }} className="btn-primary" onClick={() => setShowForm(true)}>
            <Plus size={18} /> Add Your First Business
          </motion.button>
        </motion.div>
      ) : (
        <div className="business-grid">
          <AnimatePresence>
            {businesses.map((b, idx) => {
              const statusColor = STATUS_COLORS[b.status] || STATUS_COLORS['Planning'];
              const isExpanded = expandedId === b.id;
              return (
                <motion.div
                  key={b.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ delay: idx * 0.05 }}
                  className={`business-card glass-panel ${activeBusinessId === b.id ? 'selected-business' : ''}`}
                >
              <button
                type="button"
                className="biz-card-header"
                onClick={() => setExpandedId(isExpanded ? null : b.id)}
                aria-expanded={isExpanded}
                aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${b.name}`}
                aria-controls={`business-details-${b.id}`}
              >
                    <div className="biz-avatar">
                      <span>{b.name.charAt(0).toUpperCase()}</span>
                    </div>
                    <div className="biz-info">
                      <div className="biz-name">{b.name}</div>
                      <div className="biz-meta">{b.type} · {b.industry}{b.state ? ` · ${b.state}` : ''}</div>
                    </div>
                    <div className="biz-card-status">
                      <span className="status-badge" style={{ background: statusColor.bg, color: statusColor.text, border: `1px solid ${statusColor.border}` }}>{b.status}</span>
                      <motion.span animate={{ rotate: isExpanded ? 90 : 0 }} className="biz-chevron" aria-hidden="true">
                        <ChevronRight size={18} />
                      </motion.span>
                    </div>
              </button>

                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        style={{ overflow: 'hidden' }}
                        id={`business-details-${b.id}`}
                      >
                        <div className="biz-expanded">
                          <button
                            type="button"
                            className={`business-context-button ${activeBusinessId === b.id ? 'active' : ''}`}
                            onClick={() => onSelectBusiness?.(activeBusinessId === b.id ? null : b.id, activeBusinessId === b.id ? null : b)}
                            aria-pressed={activeBusinessId === b.id}
                          >
                            {activeBusinessId === b.id ? 'Selected business' : 'Select for chat'}
                          </button>
                          {b.description && <p className="biz-description">{b.description}</p>}
                          {!b.state && <p className="business-context-warning" role="status">Add a primary state so future obligation guidance can be jurisdiction-aware.</p>}
                          <div className="biz-detail-row">
                            <span className="biz-detail-label">Added:</span>
                            <span className="biz-detail-value">{b.createdAt}</span>
                          </div>
                          <div className="quick-actions-label">Quick Ask BizGuide:</div>
                          <div className="quick-action-chips">
                            {QUICK_ACTIONS.map(qa => (
                              <motion.button
                                key={qa.label}
                                whileHover={{ y: -1 }}
                                whileTap={{ y: 0 }}
                                className="chip-btn"
                                onClick={() => {
                                  onSelectBusiness?.(b.id, b);
                                  onAskQuestion(`For my ${b.type} business in ${b.industry}${b.state ? ` in ${b.state}` : ''}: ${qa.query}`);
                                }}
                              >
                                {qa.label} <ChevronRight size={14} />
                              </motion.button>
                            ))}
                          </div>
                          <div className="biz-card-actions">
                            <button className="icon-btn-text" onClick={() => handleEdit(b)}><Edit2 size={15} /> Edit</button>
                            <button className="icon-btn-text danger" onClick={() => handleDelete(b.id)} aria-label={`${pendingDeleteId === b.id ? 'Confirm deletion of' : 'Delete'} ${b.name}`}><Trash2 size={15} /> {pendingDeleteId === b.id ? 'Confirm delete' : 'Delete'}</button>
                          </div>
                          {pendingDeleteId === b.id && <div className="destructive-hint" role="status">Click Confirm delete again to permanently remove this business.</div>}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
};

export default MyBusinesses;
