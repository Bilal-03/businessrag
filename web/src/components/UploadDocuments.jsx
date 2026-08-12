import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, CheckCircle2, XCircle, Clock, Trash2 } from 'lucide-react';

const UploadDocuments = ({ session, apiUrl, businessId }) => {
  const [uploadHistory, setUploadHistory] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [currentFileName, setCurrentFileName] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [inventoryLoading, setInventoryLoading] = useState(true);
  const fileInputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    if (!session?.access_token) return undefined;
    setInventoryLoading(true);
    const inventoryUrl = businessId
      ? `${apiUrl}/api/documents?business_id=${encodeURIComponent(businessId)}`
      : `${apiUrl}/api/documents`;
    fetch(inventoryUrl, { headers: { Authorization: `Bearer ${session.access_token}` } })
      .then(async response => {
        let data = [];
        try { data = await response.json(); } catch {}
        if (!response.ok) throw new Error(data.detail || 'Document inventory is unavailable.');
        if (!cancelled) setUploadHistory(Array.isArray(data) ? data.map(item => ({
          id: item.id,
          name: item.file_name,
          size: item.byte_size ? `${(item.byte_size / 1024).toFixed(1)} KB` : 'Size unavailable',
          date: item.created_at ? new Date(item.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'Date unavailable',
          status: item.status === 'indexed' ? 'success' : item.status === 'failed' ? 'error' : 'processing',
          message: item.status === 'indexed' ? 'Indexed for document-grounded answers.' : item.status,
        })) : []);
      })
      .catch(error => {
        if (!cancelled) setUploadStatus(error.message || 'Document inventory is unavailable.');
      })
      .finally(() => { if (!cancelled) setInventoryLoading(false); });
    return () => { cancelled = true; };
  }, [apiUrl, businessId, session]);

  const saveHistory = (updated) => {
    setUploadHistory(updated);
  };

  const handleUpload = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setUploadStatus('Please choose a PDF file.');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setUploadStatus('This PDF is larger than the 50MB upload limit.');
      return;
    }
    setUploading(true);
    setCurrentFileName(file.name);
    setUploadStatus('Uploading and processing your PDF. This may take a moment.');

    const formData = new FormData();
    formData.append('file', file);
    if (businessId) formData.append('business_id', businessId);

    try {
      const response = await fetch(`${apiUrl}/api/documents/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`
        },
        body: formData,
      });
      let data = {};
      try { data = await response.json(); } catch {}

      const newEntry = {
        id: data.document_id || Date.now().toString(),
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
        status: response.ok ? (data.status === 'processing' ? 'processing' : 'success') : 'error',
        message: response.ok ? data.message : (data.detail || 'Upload failed'),
      };
      saveHistory([newEntry, ...uploadHistory]);
      setUploadStatus(response.ok ? 'Upload complete.' : (data.detail || 'Upload failed. Please try again.'));
    } catch {
      const newEntry = {
        id: Date.now().toString(),
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
        status: 'error',
        message: 'Network error. Please check your connection.',
      };
      saveHistory([newEntry, ...uploadHistory]);
      setUploadStatus('Network error. Please check your connection and try again.');
    } finally {
      setUploading(false);
      setCurrentFileName('');
    }

    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleDeleteHistory = async (id) => {
    if (!id) return;
    try {
      const response = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      let data = {};
      try { data = await response.json(); } catch {}
      if (!response.ok) throw new Error(data.detail || 'The document could not be removed.');
      saveHistory(uploadHistory.filter(u => u.id !== id));
      setUploadStatus('Document removed from your workspace.');
    } catch (error) {
      setUploadStatus(error.message || 'The document could not be removed.');
    }
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Upload Documents</h2>
          <p className="panel-subtitle">Upload PDFs to ground answers in your source documents. {businessId ? 'Showing documents for the selected business.' : 'Select a business to keep documents scoped to one workspace.'}</p>
        </div>
      </div>

      {/* Drop Zone */}
      <motion.div
        className={`drop-zone ${isDragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`}
        onDragEnter={() => !uploading && setIsDragging(true)}
        onDragLeave={() => setIsDragging(false)}
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        onKeyDown={e => {
          if (!uploading && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={uploading ? -1 : 0}
        aria-label="Choose a PDF document to upload"
        aria-busy={uploading}
        whileHover={!uploading ? { scale: 1.01, borderColor: 'rgba(99,102,241,0.6)' } : {}}
        animate={isDragging ? { scale: 1.02, borderColor: '#6366f1' } : {}}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          aria-label="PDF document"
          style={{ display: 'none' }}
          onChange={e => handleUpload(e.target.files[0])}
        />
        <AnimatePresence mode="wait">
          {uploading ? (
            <motion.div key="uploading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="drop-zone-content">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
                style={{ color: '#6366f1' }}
              >
                <UploadCloud size={48} />
              </motion.div>
              <div className="upload-filename">{currentFileName}</div>
              <div className="progress-bar-container" aria-hidden="true"><div className="progress-bar-indeterminate" /></div>
              <div className="upload-progress-label" role="status" aria-live="polite">
                {uploadStatus}
              </div>
            </motion.div>
          ) : (
            <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="drop-zone-content">
              <motion.div animate={isDragging ? { scale: 1.2, y: -8 } : { scale: 1, y: 0 }} style={{ color: isDragging ? '#6366f1' : 'var(--text-secondary)' }}>
                <UploadCloud size={52} />
              </motion.div>
              <div className="drop-zone-title">{isDragging ? 'Drop your PDF here!' : 'Drag & drop a PDF or click to browse'}</div>
              <div className="drop-zone-subtitle">Supports: PDF files only · Max file size: 50MB</div>
              <motion.button
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.97 }}
                className="btn-primary"
                style={{ marginTop: '8px', pointerEvents: 'none' }}
              >
                <UploadCloud size={16} /> Choose PDF File
              </motion.button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
      {uploadStatus && !uploading && <div className="upload-status-message" role="status">{uploadStatus}</div>}

      {/* Info Box */}
      <div className="info-box">
        <div className="info-icon">💡</div>
        <div>
          <div className="info-title">How it works</div>
          <div className="info-text">We process your PDF to support answers in this account. Verify important legal and tax information against the original source or with a qualified professional.</div>
        </div>
      </div>

      {/* Upload History */}
      {inventoryLoading && <div className="upload-status-message" role="status">Loading your document inventory…</div>}
      {!inventoryLoading && uploadHistory.length > 0 && (
        <div className="upload-history">
          <div className="section-label">Upload History</div>
          <AnimatePresence>
            {uploadHistory.map((item, idx) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ delay: idx * 0.04 }}
                className="upload-history-item glass-panel"
              >
                <div className="upload-file-icon">
                  {item.status === 'success' ? <CheckCircle2 size={20} color="#4ade80" /> : <XCircle size={20} color="#f87171" />}
                </div>
                <div className="upload-file-info">
                  <div className="upload-file-name">{item.name}</div>
                  <div className="upload-file-meta">
                    <Clock size={12} /> {item.date} · {item.size}
                    {item.status === 'success' && <span className="upload-success-label">· Indexed</span>}
                  </div>
                  {item.message && <div className="upload-message">{item.message}</div>}
                </div>
                <button className="icon-btn" onClick={() => handleDeleteHistory(item.id)} title="Remove local record" aria-label={`Remove local record for ${item.name}`}>
                  <Trash2 size={16} />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
};

export default UploadDocuments;
