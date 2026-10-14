import { Suspense, useEffect } from 'react';
import { matchPath, Route, Routes, useLocation } from 'react-router-dom';
import { useBootstrap } from '@/lib/bootstrap';
import { showFlash } from '@/lib/toast';
import { publicRoutes, shellRoutes } from '@/routes';
import { AppShell } from '@/shell/AppShell';
import { CrashBoundary } from '@/components/fun/CrashBoundary';
import { NotFound } from '@/components/fun/NotFound';
import { Toaster } from '@/shell/Toaster';
import { Skeleton } from '@/components/ui/skeleton';

const pageLoading = <div className="space-y-4 p-1" data-testid="page-loading"><Skeleton className="h-9 w-64" /><Skeleton className="h-72 w-full" /></div>;

// Pages that work without a login (a survey's public link, later the sign-in pages) get no sidebar and no bootstrap.
export function Gate() {
  const { pathname } = useLocation();
  if (publicRoutes.some((r) => matchPath(r.path as string, pathname))) {
    return (
      <>
        <Suspense fallback={pageLoading}>
        <Routes>
          {publicRoutes.map((r) => (
            <Route key={r.path} path={r.path} element={r.element} />
          ))}
        </Routes>
        </Suspense>
        <Toaster />
      </>
    );
  }
  return <PrivateApp />;
}

function PrivateApp() {
  const { pathname } = useLocation();
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
        <CrashBoundary key={pathname}>
        <Suspense fallback={pageLoading}>
        <Routes>
          {shellRoutes.map((r) => (
            <Route key={r.path} path={r.path} element={r.element} />
          ))}
          <Route path="*" element={<NotFound />} />
        </Routes>
        </Suspense>
        </CrashBoundary>
      </AppShell>
      <Toaster />
    </>
  );
}
