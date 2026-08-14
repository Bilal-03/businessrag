import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, Mail, User, ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { captureEvent } from '../lib/observability';
import Logo from './Logo';
import './Auth.css';

export default function Auth() {
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);
    captureEvent('auth_submitted', { mode: isLogin ? 'sign_in' : 'sign_up' });

    try {
      if (isLogin) {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        captureEvent('auth_completed', { mode: 'sign_in' });
      } else {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { full_name: name }
          }
        });
        if (error) throw error;
        captureEvent('auth_completed', { mode: 'sign_up' });
        setMessage('Check your email for the confirmation link!');
      }
    } catch (err) {
      captureEvent('auth_failed', { mode: isLogin ? 'sign_in' : 'sign_up' });
      setError(err.message || 'An error occurred during authentication');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <section className="auth-story" aria-label="About BizGuide">
        <Logo size={46} showText tone="dark" />
        <div className="auth-story-copy">
          <span className="auth-eyebrow">India-focused compliance workspace</span>
          <h1>Compliance work deserves a clearer starting point.</h1>
          <p>Bring your business context, source documents, obligations, and next questions into one calm workspace.</p>
        </div>
        <div className="auth-trust-list" aria-label="Product safeguards">
          <span><CheckCircle2 size={17} /> Source-aware answers</span>
          <span><CheckCircle2 size={17} /> Business-scoped workspaces</span>
          <span><CheckCircle2 size={17} /> Clear evidence and coverage limits</span>
        </div>
        <p className="auth-disclaimer">Educational guidance only. Verify important legal and tax decisions with the original source and a qualified professional.</p>
      </section>

      <motion.div 
        className="auth-card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="auth-header">
          <span className="auth-card-kicker">Your workspace</span>
          <h2 className="auth-title">{isLogin ? 'Welcome back' : 'Create your account'}</h2>
          <p className="auth-subtitle">
            {isLogin ? 'Sign in to continue your compliance work.' : 'Set up a secure place for your business guidance.'}
          </p>
        </div>

        <form onSubmit={handleAuth} className="auth-form">
          <AnimatePresence mode="wait">
            {error && (
              <motion.div 
                key="error"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="auth-alert error"
                role="alert"
                aria-live="assertive"
              >
                <AlertCircle size={16} /> {error}
              </motion.div>
            )}
            {message && (
              <motion.div 
                key="message"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="auth-alert success"
                role="status"
                aria-live="polite"
              >
                <CheckCircle2 size={16} /> {message}
              </motion.div>
            )}
          </AnimatePresence>

          {!isLogin && (
            <div className="form-group full">
              <label htmlFor="auth-name">Full Name</label>
              <div className="input-with-icon">
                <User size={18} className="input-icon" />
                <input
                  type="text" 
                  id="auth-name"
                  className="form-input with-icon" 
                  placeholder="Rajesh Kumar"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            </div>
          )}

          <div className="form-group full">
            <label htmlFor="auth-email">Email Address</label>
            <div className="input-with-icon">
              <Mail size={18} className="input-icon" />
              <input
                type="email"
                id="auth-email"
                className="form-input with-icon"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group full">
            <label htmlFor="auth-password">Password</label>
            <div className="input-with-icon">
              <Lock size={18} className="input-icon" />
              <input
                type="password"
                id="auth-password"
                className="form-input with-icon"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <motion.button 
            whileHover={{ y: -1 }}
            whileTap={{ y: 0 }}
            className="btn-primary auth-submit"
            type="submit"
            disabled={loading}
            aria-busy={loading}
          >
            {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Create Account')}
            {!loading && <ArrowRight size={18} />}
          </motion.button>
        </form>

        <div className="auth-footer">
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button className="text-link" onClick={() => setIsLogin(!isLogin)} type="button">
            {isLogin ? 'Sign up' : 'Sign in'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
