import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px',
          maxWidth: '800px',
          margin: '40px auto',
          background: 'var(--bg-surface-1, #151C24)',
          border: '1px solid #FF4D5F',
          borderRadius: '8px',
          color: '#F3F6FA'
        }}>
          <h2 style={{ color: '#FF4D5F', marginTop: 0 }}>Application Render Error</h2>
          <p style={{ color: 'var(--text-secondary, #A0AEC0)' }}>
            The page encountered an uncaught runtime error during rendering:
          </p>
          <pre style={{
            background: 'var(--bg-surface-2, #0B0E14)',
            padding: '16px',
            borderRadius: '6px',
            color: '#FF8C42',
            overflowX: 'auto',
            fontSize: '13px'
          }}>
            {this.state.error?.toString()}
            {"\n\nStack Trace:\n"}
            {this.state.errorInfo?.componentStack}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '8px 16px',
              background: '#4F8CFF',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 600
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

