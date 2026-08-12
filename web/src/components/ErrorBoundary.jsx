import React from 'react';
import { captureException } from '../lib/observability';

export default class ErrorBoundary extends React.Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    captureException(error, { source: 'react_render' });
    // Keep production failures visible without sending prompts or document contents.
    if (import.meta.env.DEV) console.error('BizGuide render error', error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <main className="app-container error-state" role="alert">
        <div className="error-state-card glass-panel">
          <h1>BizGuide needs to reload</h1>
          <p>Something went wrong while rendering this workspace. Your saved account data is not deleted.</p>
          <button type="button" className="btn-primary" onClick={() => window.location.reload()}>
            Reload workspace
          </button>
        </div>
      </main>
    );
  }
}
