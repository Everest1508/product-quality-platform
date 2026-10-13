import { useEffect } from 'react';
import { matchPath, Route, Routes, useLocation } from 'react-router-dom';
import { useBootstrap } from '@/lib/bootstrap';
import { showFlash } from '@/lib/toast';
import { publicRoutes, shellRoutes } from '@/routes';
import { AppShell } from '@/shell/AppShell';
import { Toaster } from '@/shell/Toaster';

// Pages that work without a login (a survey's public link, later the sign-in pages) get no sidebar and no bootstrap.
export function Gate() {
  const { pathname } = useLocation();
  if (publicRoutes.some((r) => matchPath(r.path as string, pathname))) {
    return (
      <>
        <Routes>
          {publicRoutes.map((r) => (
            <Route key={r.path} path={r.path} element={r.element} />
          ))}
        </Routes>
        <Toaster />
      </>
    );
  }
  return <PrivateApp />;
}

function PrivateApp() {
  const boot = useBootstrap();
  const flash = boot.data?.messages;
  useEffect(() => {
    if (flash) showFlash(flash);
  }, [flash]);
  if (boot.isPending) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  // A failed background refresh keeps the previous data; only a failed first load blocks the app.
  if (boot.isError && !boot.data) {
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
