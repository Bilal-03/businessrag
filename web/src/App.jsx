import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, FileText, Scale, Building2, Briefcase, ChevronRight, UploadCloud } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import Sidebar from './components/Sidebar';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);

  const handleSend = async (query) => {
    if (!query.trim()) return;
    
    const userMsg = { role: 'user', content: query };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await response.json();
      setMessages((prev) => [...prev, { role: 'ai', content: data.answer }]);
    } catch (error) {
      setMessages((prev) => [...prev, { role: 'ai', content: '⚠️ Error connecting to the agent.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsUploading(true);
    setMessages((prev) => [...prev, { role: 'user', content: `📎 Uploading ${file.name}...` }]);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/documents/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      
      if (response.ok) {
        setMessages((prev) => [...prev, { role: 'ai', content: `✅ **Success!** ${data.message}. You can now ask questions about this document.` }]);
      } else {
        setMessages((prev) => [...prev, { role: 'ai', content: `❌ **Upload Failed:** ${data.detail}` }]);
      }
    } catch (error) {
      setMessages((prev) => [...prev, { role: 'ai', content: '⚠️ Error connecting to the server for upload.' }]);
    } finally {
      setIsUploading(false);
      // Reset input
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };
  
  return (
    <div className="app-container">
      <Sidebar />
      <main className="main-content">
        <div className="chat-container">
          {messages.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
              className="hero-section"
            >
              <div className="hero-badge">BizGuide AI</div>
              <h1 className="hero-title">
                Your <span className="gradient-text">Personal Agent</span><br />
                for Business Compliance
              </h1>
              <p className="hero-subtitle">
                Ask anything about starting a business, getting licenses, or filing taxes in India. Our multi-agent AI system sources the latest government laws to give you accurate answers.
              </p>

              <div className="quick-actions">
                <motion.div whileHover={{ scale: 1.02 }} className="glass-panel action-card" onClick={() => handleSend('What are the steps to register a Private Limited Company?')}>
                  <div className="action-icon">🏢</div>
                  <div className="action-title">Company Registration</div>
                  <div className="action-desc">Steps to incorporate a Pvt Ltd</div>
                </motion.div>
                <motion.div whileHover={{ scale: 1.02 }} className="glass-panel action-card" onClick={() => handleSend('How do I apply for FSSAI food license?')}>
                  <div className="action-icon">🍽️</div>
                  <div className="action-title">FSSAI License</div>
                  <div className="action-desc">Get your food business permits</div>
                </motion.div>
                <motion.div whileHover={{ scale: 1.02 }} className="glass-panel action-card" onClick={() => handleSend('What are the benefits of Startup India?')}>
                  <div className="action-icon">🚀</div>
                  <div className="action-title">Startup India</div>
                  <div className="action-desc">Tax exemptions and funding</div>
                </motion.div>
              </div>
            </motion.div>
          ) : (
            <div className="messages-list">
              <AnimatePresence>
                {messages.map((msg, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    className={`message-bubble ${msg.role === 'user' ? 'message-user' : 'message-ai'}`}
                  >
                    {msg.role === 'ai' ? (
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    ) : (
                      msg.content
                    )}
                  </motion.div>
                ))}
                {(isTyping || isUploading) && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="message-bubble message-ai"
                  >
                    <span style={{ fontStyle: 'italic', color: '#8b5cf6' }}>
                      {isUploading ? 'Processing document chunks and creating embeddings...' : 'Consulting Specialized Agents...'}
                    </span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>

        <div className="input-container">
          <div className="chat-input-wrapper">
            <button 
              className="upload-button" 
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading || isTyping}
              title="Upload PDF Document"
            >
              <Paperclip size={20} />
            </button>
            <input 
              type="file" 
              accept=".pdf"
              style={{ display: 'none' }} 
              ref={fileInputRef}
              onChange={handleFileUpload}
            />
            <input 
              type="text" 
              className="chat-input"
              placeholder="Ask about business structures, GST, licenses..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && input.trim() && !isTyping && !isUploading) {
                  handleSend(input);
                }
              }}
              disabled={isUploading || isTyping}
            />
            <button 
              className="send-button" 
              onClick={() => handleSend(input)}
              disabled={!input.trim() || isTyping || isUploading}
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
