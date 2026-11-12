import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AlertProvider } from './context/AlertContext';
import './styles/global.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AlertProvider>
        <App />
      </AlertProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
