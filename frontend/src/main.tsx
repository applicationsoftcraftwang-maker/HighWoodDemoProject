import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App.tsx';
import { ApiError } from './lib/api';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          if ([400, 401, 403, 404, 409, 422].includes(error.status ?? 0)) {
            return false;
          }
        }

        return failureCount < 2;
      },
    },
    mutations: {
      retry: false,
    },
  },
});

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Application root element #root was not found.');
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);