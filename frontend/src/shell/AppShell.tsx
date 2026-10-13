import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { socket } from '@/lib/presence';
import { useBootstrapData } from '@/lib/bootstrap';
import { Changelog } from './Changelog';
import { Palette } from './Palette';
import { ShortcutsHelp } from './ShortcutsHelp';
import { Sidebar } from './Sidebar';
import { useGlobalKeys } from './keys';
import { Topbar } from './Topbar';

const KEY = 'pqSidebarCollapsed';
const read = () => {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
};

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(read);
  const [open, setOpen] = useState(false);
  const [changelog, setChangelog] = useState(false);
  const [palette, setPalette] = useState(false);
  const [help, setHelp] = useState(false);
  const b = useBootstrapData();
  useGlobalKeys({
    onPalette: useCallback((m) => setPalette((o) => (m === 'toggle' ? !o : true)), []),
    onHelp: useCallback(() => setHelp(true), []),
    newTicketUrl: b.urls.ticket_create,
  });
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    socket.start();
    const stop = () => socket.stop();
    // Closing on pagehide lets the page enter the back/forward cache; reconnect when it returns.
    const back = (e: PageTransitionEvent) => e.persisted && socket.start();
    window.addEventListener('pagehide', stop);
    window.addEventListener('pageshow', back);
    return () => {
      window.removeEventListener('pagehide', stop);
      window.removeEventListener('pageshow', back);
    };
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  const toggle = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem(KEY, c ? '0' : '1');
      } catch {
        /* private mode: just don't remember it */
      }
      return !c;
    });
  return (
    <div className="flex min-h-screen bg-muted text-foreground">
      <Sidebar collapsed={collapsed} onToggle={toggle} open={open} onClose={() => setOpen(false)} onOpenChangelog={() => setChangelog(true)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenNav={() => setOpen(true)} onOpenPalette={() => setPalette(true)} />
        <main key={pathname} className="page-in mx-auto w-full max-w-7xl flex-1 p-6 max-md:p-4 lg:p-8">{children}</main>
      </div>
      <Palette open={palette} onOpenChange={setPalette} />
      <ShortcutsHelp open={help} onOpenChange={setHelp} />
      <Changelog open={changelog} onOpenChange={setChangelog} />
    </div>
  );
}
