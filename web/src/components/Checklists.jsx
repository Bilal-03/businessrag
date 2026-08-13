import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Circle, ChevronRight, RotateCcw, ExternalLink, Building2, BarChart3, UtensilsCrossed, Rocket, Store } from 'lucide-react';
import { getUserData, updateUserData } from '../lib/supabase';

const CHECKLISTS = [
  {
    id: 'pvt-ltd',
    title: 'Private Limited Company Registration',
    description: 'Complete step-by-step guide to incorporate a Pvt Ltd company in India with MCA.',
    icon: <Building2 size={24} />,
    accentColor: '#9f3f29',
    items: [
      { id: 'pl1', text: 'Obtain Digital Signature Certificate (DSC) for all directors', link: 'https://www.mca.gov.in' },
      { id: 'pl2', text: 'Apply for Director Identification Number (DIN) via MCA portal' },
      { id: 'pl3', text: 'Reserve company name via RUN (Reserve Unique Name) form on MCA' },
      { id: 'pl4', text: 'Draft Memorandum of Association (MOA) and Articles of Association (AOA)' },
      { id: 'pl5', text: 'File SPICe+ form (incorporation form) on MCA portal' },
      { id: 'pl6', text: 'Pay stamp duty and incorporation fees' },
      { id: 'pl7', text: 'Receive Certificate of Incorporation (COI) from Registrar of Companies' },
      { id: 'pl8', text: 'Apply for PAN and TAN for the company' },
      { id: 'pl9', text: 'Open a current bank account in the company name' },
      { id: 'pl10', text: 'Register for GST if annual turnover exceeds ₹20 Lakhs (₹10L for special states)' },
    ]
  },
  {
    id: 'gst',
    title: 'GST Registration',
    description: 'Get your GSTIN for your business. Mandatory if turnover exceeds the threshold.',
    icon: <BarChart3 size={24} />,
    accentColor: '#10b981',
    items: [
      { id: 'gst1', text: 'Gather business documents: PAN, Aadhaar, bank statement, address proof' },
      { id: 'gst2', text: 'Visit GST portal (gst.gov.in) and click "Register Now"' },
      { id: 'gst3', text: 'Fill Part A of REG-01 — basic details and get TRN (Temporary Reference Number)' },
      { id: 'gst4', text: 'Complete Part B — business details, promoter info, business address' },
      { id: 'gst5', text: 'Upload required documents (photo, address proof, bank proof)' },
      { id: 'gst6', text: 'Complete Aadhaar authentication for faster processing' },
      { id: 'gst7', text: 'Submit with DSC or EVC (OTP-based) verification' },
      { id: 'gst8', text: 'Receive ARN (Application Reference Number) for tracking' },
      { id: 'gst9', text: 'Verification by GST Officer within 7 working days' },
      { id: 'gst10', text: 'Receive GSTIN certificate on approval' },
    ]
  },
  {
    id: 'fssai',
    title: 'FSSAI Food License',
    description: 'Mandatory for all food businesses including restaurants, home bakers, and cloud kitchens.',
    icon: <UtensilsCrossed size={24} />,
    accentColor: '#f59e0b',
    items: [
      { id: 'fssai1', text: 'Determine license type: Basic (turnover < ₹12L), State (₹12L–20Cr), Central (>₹20Cr)' },
      { id: 'fssai2', text: 'Visit FoSCoS portal (foscos.fssai.gov.in) and register/login' },
      { id: 'fssai3', text: 'Fill Form B (State/Central) or Form A (Basic registration)' },
      { id: 'fssai4', text: 'Prepare documents: ID proof, address proof, food safety management plan' },
      { id: 'fssai5', text: 'Upload: List of food products, layout plan of premises' },
      { id: 'fssai6', text: 'Pay prescribed fees based on license category and validity' },
      { id: 'fssai7', text: 'Await inspection by designated officer (State/Central license)' },
      { id: 'fssai8', text: 'Receive FSSAI License Number (14-digit) after approval' },
      { id: 'fssai9', text: 'Display FSSAI license prominently at business premises' },
      { id: 'fssai10', text: 'Set renewal reminder 30 days before expiry date' },
    ]
  },
  {
    id: 'startup-india',
    title: 'Startup India Registration',
    description: 'DPIIT recognition for tax benefits, funding access, and government scheme eligibility.',
    icon: <Rocket size={24} />,
    accentColor: '#7f321f',
    items: [
      { id: 'si1', text: 'Ensure entity is Pvt Ltd, LLP, or Partnership (not older than 10 years)' },
      { id: 'si2', text: 'Confirm annual turnover not exceeding ₹100 Crore' },
      { id: 'si3', text: 'Ensure company is working towards innovation, development, or improvement' },
      { id: 'si4', text: 'Visit Startup India hub (startupindia.gov.in) and create account' },
      { id: 'si5', text: 'Apply for DPIIT Recognition via the portal' },
      { id: 'si6', text: 'Provide incorporation certificate, PAN, funding info, awards (if any)' },
      { id: 'si7', text: 'Submit self-certification for tax exemptions (80-IAC, 56(2)(viib))' },
      { id: 'si8', text: 'Receive DPIIT Certificate of Recognition' },
      { id: 'si9', text: 'Apply for income tax exemption under Section 80-IAC separately' },
      { id: 'si10', text: 'Register on GeM (Government e-Marketplace) for B2G opportunities' },
    ]
  },
  {
    id: 'shop-estab',
    title: 'Shop & Establishment Act',
    description: 'Mandatory registration for all commercial establishments under state law.',
    icon: <Store size={24} />,
    accentColor: '#ec4899',
    items: [
      { id: 'se1', text: 'Identify applicable state law (each state has its own S&E Act)' },
      { id: 'se2', text: 'Prepare documents: ID proof, address proof, rent agreement, photos' },
      { id: 'se3', text: 'Visit state labour department portal or local municipal office' },
      { id: 'se4', text: 'Fill registration form with business name, address, owner details' },
      { id: 'se5', text: 'Specify number of employees and working hours' },
      { id: 'se6', text: 'Pay registration fee (varies by state, typically ₹100–₹5000)' },
      { id: 'se7', text: 'Receive Registration Certificate (within 7–30 days depending on state)' },
      { id: 'se8', text: 'Display certificate at the establishment premises' },
      { id: 'se9', text: 'Renew annually as per state requirements' },
    ]
  },
];

const Checklists = ({ session, onAskQuestion }) => {
  const [checkedItems, setCheckedItems] = useState({});
  const [expandedId, setExpandedId] = useState(CHECKLISTS[0].id);

  useEffect(() => {
    if (session) {
      getUserData(session.user.id).then(data => {
        if (data && data.checklists) setCheckedItems(data.checklists);
      });
    }
  }, [session]);

  const toggleItem = (checklistId, itemId) => {
    const key = `${checklistId}_${itemId}`;
    const updated = { ...checkedItems, [key]: !checkedItems[key] };
    setCheckedItems(updated);
    if (session) updateUserData(session.user.id, { checklists: updated });
  };

  const getProgress = (checklist) => {
    const checked = checklist.items.filter(item => checkedItems[`${checklist.id}_${item.id}`]).length;
    return { checked, total: checklist.items.length, pct: Math.round((checked / checklist.items.length) * 100) };
  };

  const resetChecklist = (checklist) => {
    const updated = { ...checkedItems };
    checklist.items.forEach(item => { delete updated[`${checklist.id}_${item.id}`]; });
    setCheckedItems(updated);
    if (session) updateUserData(session.user.id, { checklists: updated });
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Compliance Checklists</h2>
          <p className="panel-subtitle">Step-by-step checklists for common business registrations and licenses in India.</p>
        </div>
      </div>

      <div className="checklists-layout">
        {/* Sidebar: list of checklists */}
        <div className="checklist-nav">
          {CHECKLISTS.map(cl => {
            const prog = getProgress(cl);
            const isActive = expandedId === cl.id;
            return (
              <motion.button
                key={cl.id}
                whileHover={{ x: 2 }}
                className={`checklist-nav-item ${isActive ? 'active' : ''}`}
                onClick={() => setExpandedId(cl.id)}
                style={isActive ? { borderColor: cl.accentColor, background: `${cl.accentColor}18` } : {}}
              >
                <span className="checklist-nav-icon">{cl.icon}</span>
                <div className="checklist-nav-info">
                  <div className="checklist-nav-title">{cl.title}</div>
                  <div className="checklist-progress-mini">
                    <div className="checklist-progress-mini-bar">
                      <div className="checklist-progress-mini-fill" style={{ width: `${prog.pct}%`, background: cl.accentColor }} />
                    </div>
                    <span>{prog.checked}/{prog.total}</span>
                  </div>
                </div>
                <ChevronRight size={16} style={{ color: isActive ? cl.accentColor : 'var(--text-secondary)', flexShrink: 0 }} />
              </motion.button>
            );
          })}
        </div>

        {/* Main: expanded checklist */}
        <div className="checklist-main">
          <AnimatePresence mode="wait">
            {CHECKLISTS.filter(cl => cl.id === expandedId).map(cl => {
              const prog = getProgress(cl);
              return (
                <motion.div
                  key={cl.id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <div className="checklist-detail-header">
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '32px' }}>{cl.icon}</span>
                        <div>
                          <h3 className="checklist-detail-title" style={{ color: cl.accentColor }}>{cl.title}</h3>
                          <p className="checklist-detail-desc">{cl.description}</p>
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <button className="icon-btn-text" onClick={() => resetChecklist(cl)} title="Reset checklist">
                        <RotateCcw size={15} /> Reset
                      </button>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="checklist-progress-bar-container">
                    <div className="checklist-progress-top">
                      <span>{prog.checked} of {prog.total} steps completed</span>
                      <span style={{ color: cl.accentColor, fontWeight: 700 }}>{prog.pct}%</span>
                    </div>
                    <div className="checklist-progress-track">
                      <motion.div
                        className="checklist-progress-fill"
                        initial={{ width: 0 }}
                        animate={{ width: `${prog.pct}%` }}
                        transition={{ ease: 'easeOut', duration: 0.5 }}
                        style={{ background: `linear-gradient(90deg, ${cl.accentColor}bb, ${cl.accentColor})` }}
                      />
                    </div>
                  </div>

                  {/* Items */}
                  <div className="checklist-items">
                    {cl.items.map((item, idx) => {
                      const key = `${cl.id}_${item.id}`;
                      const done = !!checkedItems[key];
                      return (
                        <motion.div
                          key={item.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: idx * 0.04 }}
                          className={`checklist-item ${done ? 'done' : ''}`}
                          onClick={() => toggleItem(cl.id, item.id)}
                        >
                          <motion.div whileTap={{ scale: 0.85 }} className="checklist-checkbox">
                            {done
                              ? <CheckCircle2 size={22} color={cl.accentColor} />
                              : <Circle size={22} color="var(--text-secondary)" />
                            }
                          </motion.div>
                          <div className="checklist-item-content">
                            <span className={`checklist-item-text ${done ? 'checked' : ''}`}>
                              <span className="step-number">{idx + 1}.</span> {item.text}
                            </span>
                            {item.link && (
                              <a href={item.link} target="_blank" rel="noreferrer" className="checklist-link" onClick={e => e.stopPropagation()}>
                                Official Portal <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>

                  {/* Ask AI Button */}
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.97 }}
                    className="btn-primary full-width"
                    style={{ marginTop: '24px', background: `linear-gradient(135deg, ${cl.accentColor}cc, ${cl.accentColor})` }}
                    onClick={() => onAskQuestion(`Explain the process for ${cl.title} in India in detail with all requirements and fees.`)}
                  >
                    <ChevronRight size={18} /> Ask BizGuide about {cl.title}
                  </motion.button>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default Checklists;
