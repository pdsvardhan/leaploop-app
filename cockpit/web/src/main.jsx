import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from './components.jsx';
import { App } from './App.jsx';
import './theme.css';

const qc = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 15000 } },
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
