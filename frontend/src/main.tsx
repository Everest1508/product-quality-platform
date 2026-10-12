import './index.css';
import { StrictMode, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { configure } from '@/lib/api';
import { useBootstrap } from '@/lib/bootstrap';
import { registerServiceWorker } from '@/lib/pwa';
import { showFlash } from '@/lib/toast';
import { AppShell } from '@/shell/AppShell';
import { Toaster } from '@/shell/Toaster';
import { shellRoutes } from '@/routes';

function Gate() {
  const boot = useBootstrap();
  const flash = boot.data?.messages;
  useEffect(() => {
    if (flash) showFlash(flash);
  }, [flash]);
  if (boot.isPending) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  if (boot.isError) {
    return (
      <div className="p-6 text-sm">
        Couldn’t load the app.{' '}
        <button className="underline" onClick={() => boot.refetch()}>
          Try again
        </button>
      </div>
    );
  }
  return (
    <>
    <AppShell>
      <Routes>
        {shellRoutes.map((r) => (
          <Route key={r.path} path={r.path} element={r.element} />
        ))}
        <Route path="*" element={<p className="text-sm text-muted-foreground">Page not found.</p>} />
      </Routes>
    </AppShell>
    <Toaster />
    </>
  );
}

const el = document.getElementById('root');
registerServiceWorker();
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
