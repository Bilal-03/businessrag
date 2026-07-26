import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, FileText, CheckCircle2, XCircle, Clock, Trash2, ChevronDown, ChevronUp } from 'lucide-react';

const UploadDocuments = ({ session, apiUrl }) => {
  const [uploadHistory, setUploadHistory] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [currentFileName, setCurrentFileName] = useState('');
  const fileInputRef = useRef(null);

  useEffect(() => {
    const saved = localStorage.getItem('bizguide_uploads');
    if (saved) setUploadHistory(JSON.parse(saved));
  }, []);

  const saveHistory = (updated) => {
    setUploadHistory(updated);
    localStorage.setItem('bizguide_uploads', JSON.stringify(updated));
  };

  const simulateProgress = () => {
    setUploadProgress(0);
    const interval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 90) { clearInterval(interval); return 90; }
        return prev + Math.random() * 15;
      });
    }, 300);
    return interval;
  };

  const handleUpload = async (file) => {
    if (!file || !file.name.endsWith('.pdf')) {
      alert('Only PDF files are supported.');
      return;
    }
    setUploading(true);
    setCurrentFileName(file.name);
    const progressInterval = simulateProgress();

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${apiUrl}/api/documents/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`
        },
        body: formData,
      });
      const data = await response.json();
      clearInterval(progressInterval);
      setUploadProgress(100);

      const newEntry = {
        id: Date.now().toString(),
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
        status: response.ok ? 'success' : 'error',
        message: response.ok ? data.message : (data.detail || 'Upload failed'),
      };
      saveHistory([newEntry, ...uploadHistory]);

      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
        setCurrentFileName('');
      }, 1000);
    } catch (err) {
      clearInterval(progressInterval);
      const newEntry = {
        id: Date.now().toString(),
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
        status: 'error',
        message: 'Network error. Please check your connection.',
      };
      saveHistory([newEntry, ...uploadHistory]);
      setUploading(false);
      setUploadProgress(0);
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

  const handleDeleteHistory = (id) => {
    saveHistory(uploadHistory.filter(u => u.id !== id));
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Upload Documents</h2>
          <p className="panel-subtitle">Upload your business PDFs to make BizGuide answer questions based on your specific documents.</p>
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
        whileHover={!uploading ? { scale: 1.01, borderColor: 'rgba(99,102,241,0.6)' } : {}}
        animate={isDragging ? { scale: 1.02, borderColor: '#6366f1' } : {}}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
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
              <div className="progress-bar-container">
                <motion.div
                  className="progress-bar-fill"
                  initial={{ width: 0 }}
                  animate={{ width: `${uploadProgress}%` }}
                  transition={{ ease: 'easeOut' }}
                />
              </div>
              <div className="upload-progress-label">
                {uploadProgress < 100 ? `Processing... ${Math.round(uploadProgress)}%` : '✅ Complete!'}
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

      {/* Info Box */}
      <div className="info-box">
        <div className="info-icon">💡</div>
        <div>
          <div className="info-title">How it works</div>
          <div className="info-text">Uploaded PDFs are split into chunks and stored in our vector database. BizGuide will then use this context to answer your questions accurately based on your actual business documents.</div>
        </div>
      </div>

      {/* Upload History */}
      {uploadHistory.length > 0 && (
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
                <button className="icon-btn" onClick={() => handleDeleteHistory(item.id)} title="Remove from history">
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
