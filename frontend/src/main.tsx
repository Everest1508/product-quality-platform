import './index.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { configure } from '@/lib/api';
import { registerServiceWorker } from '@/lib/pwa';
import { Gate } from '@/Gate';
import { applyTheme } from '@/lib/theme';

const el = document.getElementById('root');
registerServiceWorker();
applyTheme();
if (typeof matchMedia === 'function') matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => applyTheme());
if (el) {
  configure({ api: '/ui-api/v1/', csrf: el.dataset.csrf ?? '' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } });
  createRoot(el).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <BrowserRouter>
          <Gate />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}
