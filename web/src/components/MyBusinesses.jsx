import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Building2, Briefcase, Store, Trash2, Edit2, ChevronRight, X, Check } from 'lucide-react';
import { getUserData, updateUserData } from '../lib/supabase';

const BUSINESS_TYPES = ['Private Limited (Pvt Ltd)', 'Limited Liability Partnership (LLP)', 'One Person Company (OPC)', 'Sole Proprietorship', 'Partnership Firm', 'Public Limited'];
const INDUSTRIES = ['Food & Beverage', 'Technology/IT', 'Healthcare', 'Education', 'Manufacturing', 'Retail & E-Commerce', 'Consulting/Services', 'Real Estate', 'Finance', 'Other'];
const STATUS_OPTIONS = ['Planning', 'Registered', 'Operating', 'On Hold'];

const STATUS_COLORS = {
  'Planning':   { bg: 'rgba(234, 179, 8, 0.15)',  text: '#fbbf24', border: 'rgba(234,179,8,0.3)' },
  'Registered': { bg: 'rgba(99, 102, 241, 0.15)', text: '#818cf8', border: 'rgba(99,102,241,0.3)' },
  'Operating':  { bg: 'rgba(34, 197, 94, 0.15)',  text: '#4ade80', border: 'rgba(34,197,94,0.3)' },
  'On Hold':    { bg: 'rgba(148, 163, 184, 0.1)', text: '#94a3b8', border: 'rgba(148,163,184,0.2)' },
};

const QUICK_ACTIONS = [
  { label: 'GST Registration', query: 'How do I register for GST for my business?' },
  { label: 'Tax Filing', query: 'What are the income tax filing requirements for my business type?' },
  { label: 'Compliance', query: 'What are the annual compliance requirements?' },
  { label: 'Licenses', query: 'What licenses do I need for my business?' },
];

const defaultForm = { name: '', type: BUSINESS_TYPES[0], industry: INDUSTRIES[0], status: STATUS_OPTIONS[0], description: '' };

const MyBusinesses = ({ session, onAskQuestion }) => {
  const [businesses, setBusinesses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(defaultForm);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    if (session) {
      getUserData(session.user.id).then(data => {
        if (data && data.businesses) setBusinesses(data.businesses);
      });
    }
  }, [session]);

  const save = (updated) => {
    setBusinesses(updated);
    if (session) updateUserData(session.user.id, { businesses: updated });
  };

  const handleSubmit = () => {
    if (!form.name.trim()) return;
    if (editingId) {
      save(businesses.map(b => b.id === editingId ? { ...b, ...form } : b));
      setEditingId(null);
    } else {
      save([...businesses, { ...form, id: Date.now().toString(), createdAt: new Date().toLocaleDateString('en-IN') }]);
    }
    setForm(defaultForm);
    setShowForm(false);
  };

  const handleEdit = (b) => {
    setForm({ name: b.name, type: b.type, industry: b.industry, status: b.status, description: b.description || '' });
    setEditingId(b.id);
    setShowForm(true);
  };

  const handleDelete = (id) => {
    save(businesses.filter(b => b.id !== id));
    if (expandedId === id) setExpandedId(null);
  };

  const handleCancel = () => {
    setForm(defaultForm);
    setEditingId(null);
    setShowForm(false);
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">My Businesses</h2>
          <p className="panel-subtitle">Manage your registered business profiles and get tailored compliance guidance.</p>
        </div>
        <motion.button
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.97 }}
          className="btn-primary"
          onClick={() => { setShowForm(true); setEditingId(null); setForm(defaultForm); }}
        >
          <Plus size={18} /> Add Business
        </motion.button>
      </div>

      {/* Add/Edit Form Modal */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            onClick={handleCancel}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.92, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92, y: 20 }}
              className="modal-card"
              onClick={e => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3>{editingId ? 'Edit Business' : 'Add New Business'}</h3>
                <button className="icon-btn" onClick={handleCancel}><X size={20} /></button>
              </div>
              <div className="form-grid">
                <div className="form-group full">
                  <label>Business Name *</label>
                  <input className="form-input" placeholder="e.g. Acme Technologies" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Business Type</label>
                  <select className="form-input" value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
                    {BUSINESS_TYPES.map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Industry</label>
                  <select className="form-input" value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })}>
                    {INDUSTRIES.map(i => <option key={i}>{i}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Status</label>
                  <select className="form-input" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
                    {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div className="form-group full">
                  <label>Description (optional)</label>
                  <textarea className="form-input" rows={3} placeholder="Brief description of your business..." value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
                </div>
              </div>
              <div className="modal-actions">
                <button className="btn-ghost" onClick={handleCancel}>Cancel</button>
                <motion.button whileHover={{ scale: 1.03 }} className="btn-primary" onClick={handleSubmit}>
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
          <motion.button whileHover={{ scale: 1.04 }} className="btn-primary" onClick={() => setShowForm(true)}>
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
                  className="business-card glass-panel"
                >
                  <div className="biz-card-header" onClick={() => setExpandedId(isExpanded ? null : b.id)}>
                    <div className="biz-avatar">
                      <span>{b.name.charAt(0).toUpperCase()}</span>
                    </div>
                    <div className="biz-info">
                      <div className="biz-name">{b.name}</div>
                      <div className="biz-meta">{b.type} · {b.industry}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto' }}>
                      <span className="status-badge" style={{ background: statusColor.bg, color: statusColor.text, border: `1px solid ${statusColor.border}` }}>{b.status}</span>
                      <motion.span animate={{ rotate: isExpanded ? 90 : 0 }} style={{ color: 'var(--text-secondary)', cursor: 'pointer' }}>
                        <ChevronRight size={18} />
                      </motion.span>
                    </div>
                  </div>

                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        style={{ overflow: 'hidden' }}
                      >
                        <div className="biz-expanded">
                          {b.description && <p className="biz-description">{b.description}</p>}
                          <div className="biz-detail-row">
                            <span className="biz-detail-label">Added:</span>
                            <span className="biz-detail-value">{b.createdAt}</span>
                          </div>
                          <div className="quick-actions-label">Quick Ask BizGuide:</div>
                          <div className="quick-action-chips">
                            {QUICK_ACTIONS.map(qa => (
                              <motion.button
                                key={qa.label}
                                whileHover={{ scale: 1.03 }}
                                whileTap={{ scale: 0.97 }}
                                className="chip-btn"
                                onClick={() => onAskQuestion(`For my ${b.type} in ${b.industry}: ${qa.query}`)}
                              >
                                {qa.label} <ChevronRight size={14} />
                              </motion.button>
                            ))}
                          </div>
                          <div className="biz-card-actions">
                            <button className="icon-btn-text" onClick={() => handleEdit(b)}><Edit2 size={15} /> Edit</button>
                            <button className="icon-btn-text danger" onClick={() => handleDelete(b.id)}><Trash2 size={15} /> Delete</button>
                          </div>
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
