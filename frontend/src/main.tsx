import './index.css';
import { StrictMode, type ReactElement } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { configure } from '@/lib/api';
import { Notifications } from '@/pages/Notifications';

const pages: Record<string, () => ReactElement> = { notifications: Notifications };

const el = document.getElementById('react-root');
const Page = el && pages[el.dataset.page ?? ''];
if (el && Page) {
  configure({ api: el.dataset.api ?? '/ui-api/v1/', csrf: el.dataset.csrf ?? '' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } });
  createRoot(el).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <Page />
      </QueryClientProvider>
    </StrictMode>,
  );
}
