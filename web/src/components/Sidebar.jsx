import React from 'react';
import { Home, FileText, Settings, UploadCloud, Folder, Plus } from 'lucide-react';

const Sidebar = () => {
  return (
    <div className="sidebar">
      <div className="logo-container">
        <div className="logo-icon">B</div>
        <span>BizGuide</span>
      </div>

      <button className="glass-panel" style={{ 
        padding: '12px 16px', 
        display: 'flex', 
        alignItems: 'center', 
        gap: '12px',
        background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.2))',
        border: '1px solid rgba(99,102,241,0.3)',
        color: 'white',
        fontWeight: '600',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        width: '100%'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 8px 16px rgba(99,102,241,0.2)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
      >
        <Plus size={20} />
        New Consultation
      </button>

      <div className="nav-links" style={{ marginTop: '16px' }}>
        <div className="nav-item active">
          <Home size={20} />
          <span>Home</span>
        </div>
        <div className="nav-item">
          <Folder size={20} />
          <span>My Businesses</span>
        </div>
        <div className="nav-item">
          <UploadCloud size={20} />
          <span>Upload Documents</span>
        </div>
        <div className="nav-item">
          <FileText size={20} />
          <span>Checklists</span>
        </div>
      </div>

      <div style={{ marginTop: 'auto' }}>
        <div className="nav-item">
          <Settings size={20} />
          <span>Settings</span>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
