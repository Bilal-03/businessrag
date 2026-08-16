import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, CheckCircle2, XCircle, Clock, Trash2, LoaderCircle, FileText, Building2 } from 'lucide-react';
import { documentHistoryEntry, pollDocumentStatus } from '../lib/documentJobs';
import { captureEvent, captureException, sizeBucket } from '../lib/observability';
import BrandKicker from './BrandKicker';

const UploadDocuments = ({ session, apiUrl, businessId }) => {
  const deleteConfirmationWindow = 8000;
  const [uploadHistory, setUploadHistory] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [currentFileName, setCurrentFileName] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [inventoryLoading, setInventoryLoading] = useState(true);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const fileInputRef = useRef(null);
  const pollControllersRef = useRef(new Map());

  const updateHistoryEntry = useCallback((id, nextEntry) => {
    setUploadHistory(current => current.map(item => item.id === id ? { ...item, ...nextEntry } : item));
  }, []);

  const trackDocument = useCallback(async (documentId, fallbackEntry) => {
    if (!documentId || pollControllersRef.current.has(documentId) || !session?.access_token) return;
    const controller = new AbortController();
    pollControllersRef.current.set(documentId, controller);
    try {
      const result = await pollDocumentStatus({
        apiUrl,
        accessToken: session.access_token,
        documentId,
        signal: controller.signal,
        onStatus: ({ document, job }) => {
          const entry = documentHistoryEntry(document, {
            ...fallbackEntry,
            progress: job?.processing_progress,
            stage: job?.processing_stage,
          });
          updateHistoryEntry(documentId, entry);
        },
      });
      if (result.document?.status === 'failed') {
        const message = result.document.error_message || 'Document processing failed. Please try again.';
        updateHistoryEntry(documentId, { status: 'error', message, stage: 'failed', progress: 0 });
        setUploadStatus(message);
        captureEvent('document_processing_failed');
      } else if (result.document?.status === 'indexed') {
        setUploadStatus('Document processing finished.');
        // Queued uploads emit `upload_queued` at submission time. Emit the
        // terminal outcome as well so PostHog can measure the queued → indexed
        // conversion for the background-worker path.
        captureEvent('upload_indexed');
        captureEvent('document_processing_completed');
      } else {
        setUploadStatus('Document processing finished with an unexpected status.');
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      updateHistoryEntry(documentId, {
        status: 'error',
        message: error.message || 'Document processing status is unavailable.',
      });
      setUploadStatus(error.message || 'Document processing status is unavailable.');
    } finally {
      pollControllersRef.current.delete(documentId);
    }
  }, [apiUrl, session?.access_token, updateHistoryEntry]);

  useEffect(() => {
    let cancelled = false;
    const pollControllers = pollControllersRef.current;
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
        if (!cancelled) {
          const entries = Array.isArray(data) ? data.map(item => documentHistoryEntry(item)) : [];
          setUploadHistory(entries);
          entries.filter(item => item.status === 'processing').forEach(item => trackDocument(item.id, item));
        }
      })
      .catch(error => {
        if (!cancelled) setUploadStatus(error.message || 'Document inventory is unavailable.');
      })
      .finally(() => { if (!cancelled) setInventoryLoading(false); });
    return () => {
      cancelled = true;
      pollControllers.forEach(controller => controller.abort());
      pollControllers.clear();
    };
  }, [apiUrl, businessId, session?.access_token, trackDocument]);

  const handleUpload = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      captureEvent('upload_rejected', { reason: 'file_type' });
      setUploadStatus('Please choose a PDF file.');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      captureEvent('upload_rejected', { reason: 'file_size', size: sizeBucket(file.size) });
      setUploadStatus('This PDF is larger than the 50MB upload limit.');
      return;
    }
    setUploading(true);
    captureEvent('upload_started', { size: sizeBucket(file.size), has_active_business: Boolean(businessId) });
    setCurrentFileName(file.name);
    setUploadStatus('Uploading and processing your PDF. This may take a moment.');

    const formData = new FormData();
    formData.append('file', file);
    if (businessId) formData.append('business_id', businessId);

    try {
      const response = await fetch(`${apiUrl}/api/documents/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'X-Idempotency-Key': globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        },
        body: formData,
      });
      let data = {};
      try { data = await response.json(); } catch {}

      const newEntry = response.ok
        ? documentHistoryEntry({
          id: data.document_id,
          file_name: data.file_name || file.name,
          byte_size: file.size,
          status: data.status || 'processing',
          created_at: data.created_at,
          processing_stage: data.status === 'indexed' ? 'complete' : 'queued',
          processing_progress: data.status === 'indexed' ? 100 : 0,
        }, {
          name: file.name,
          message: data.message,
        })
        : {
          id: data.document_id || Date.now().toString(),
          name: file.name,
          size: (file.size / 1024).toFixed(1) + ' KB',
          date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
          status: 'error',
          progress: 0,
          stage: 'failed',
          message: data.detail || 'Upload failed',
        };
      setUploadHistory(current => [newEntry, ...current]);
      setUploadStatus(response.ok
        ? (data.status === 'indexed' ? 'Upload complete.' : 'Upload queued. Processing will continue in the background.')
        : (data.detail || 'Upload failed. Please try again.'));
      if (response.ok && data.document_id && data.status !== 'indexed') {
        void trackDocument(data.document_id, newEntry);
      }
      if (response.ok) captureEvent(data.status === 'indexed' ? 'upload_indexed' : 'upload_queued');
      else captureEvent('upload_failed', { status: response.status });
    } catch (error) {
      captureException(error, { source: 'documents_upload' });
      captureEvent('upload_failed', { reason: 'network' });
      const newEntry = {
        id: Date.now().toString(),
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
        status: 'error',
        message: 'Network error. Please check your connection.',
      };
      setUploadHistory(current => [newEntry, ...current]);
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
    if (pendingDeleteId !== id) {
      setPendingDeleteId(id);
      window.setTimeout(() => setPendingDeleteId(current => current === id ? null : current), deleteConfirmationWindow);
      return;
    }
    setPendingDeleteId(null);
    try {
      const response = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      let data = {};
      try { data = await response.json(); } catch {}
      if (!response.ok) throw new Error(data.detail || 'The document could not be removed.');
      setUploadHistory(current => current.filter(u => u.id !== id));
      setUploadStatus('Document removed from your workspace.');
    } catch (error) {
      setUploadStatus(error.message || 'The document could not be removed.');
    }
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div>
          <BrandKicker icon={FileText}>Source library</BrandKicker>
          <h2 className="panel-title">Source Library</h2>
          <p className="panel-subtitle">Upload PDFs to ground answers in your source documents. {businessId ? 'Showing documents for the selected business.' : 'Select a business to keep documents scoped to one workspace.'}</p>
        </div>
        <div className="panel-context-badge" role="status">
          <Building2 size={14} />
          {businessId ? 'Business-scoped uploads' : 'Personal workspace'}
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
        whileHover={!uploading ? { y: -1, borderColor: 'rgba(159,63,41,0.6)' } : {}}
        animate={isDragging ? { y: -2, borderColor: '#9f3f29' } : {}}
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
                style={{ color: '#9f3f29' }}
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
              <motion.div animate={isDragging ? { y: -6 } : { y: 0 }} style={{ color: isDragging ? '#9f3f29' : 'var(--text-secondary)' }}>
                <UploadCloud size={52} />
              </motion.div>
              <div className="drop-zone-title">{isDragging ? 'Drop your PDF here!' : 'Drag & drop a PDF or click to browse'}</div>
              <div className="drop-zone-subtitle">Supports: PDF files only · Max file size: 50MB</div>
              <motion.button
                whileHover={{ y: -1 }}
                whileTap={{ y: 0 }}
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
      {!inventoryLoading && (
        <div className="upload-history" aria-live="polite">
          <div className="section-heading-row">
            <div>
              <div className="section-label">Upload History</div>
              <p className="section-helper">Only documents in the selected workspace appear here.</p>
            </div>
            {uploadHistory.length > 0 && <span className="section-count">{uploadHistory.length} {uploadHistory.length === 1 ? 'document' : 'documents'}</span>}
          </div>
          {uploadHistory.length === 0 && (
            <div className="upload-empty glass-panel">
              <div className="upload-empty-icon"><FileText size={24} /></div>
              <div>
                <h3>No source documents yet</h3>
                <p>Upload a PDF to ground answers in your own policies, notices, or business records.</p>
              </div>
            </div>
          )}
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
                  {item.status === 'success' && <CheckCircle2 size={20} color="#4ade80" />}
                  {item.status === 'error' && <XCircle size={20} color="#f87171" />}
                  {item.status === 'processing' && <LoaderCircle size={20} color="var(--accent-primary)" className="spin" />}
                </div>
                <div className="upload-file-info">
                  <div className="upload-file-name">{item.name}</div>
                  <div className="upload-file-meta">
                    <Clock size={12} /> {item.date} · {item.size}
                    {item.status === 'success' && <span className="upload-success-label">· Indexed</span>}
                    {item.status === 'processing' && <span>· {item.progress || 0}%</span>}
                  </div>
                  {item.status === 'processing' && (
                    <div className="document-progress" aria-label={`${item.progress || 0}% processed`}>
                      <div className="document-progress-fill" style={{ width: `${Math.max(4, Math.min(100, item.progress || 0))}%` }} />
                    </div>
                  )}
                  {item.message && <div className="upload-message">{item.message}</div>}
                </div>
                <button className={`icon-btn document-delete-button ${pendingDeleteId === item.id ? 'confirming' : ''}`} onClick={() => handleDeleteHistory(item.id)} title={pendingDeleteId === item.id ? 'Click again to confirm removal' : 'Remove document'} aria-label={`${pendingDeleteId === item.id ? 'Confirm removal of' : 'Remove document'} ${item.name}`}>
                  {pendingDeleteId === item.id ? <CheckCircle2 size={16} /> : <Trash2 size={16} />}
                  {pendingDeleteId === item.id && <span>Confirm</span>}
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
