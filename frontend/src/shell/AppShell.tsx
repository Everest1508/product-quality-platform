import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { SidebarProvider, useSidebar } from '@/components/ui/sidebar';
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

// Remembers the desktop rail state under the same key the old sidebar used.
function RememberCollapsed() {
  const { collapsed } = useSidebar();
  useEffect(() => {
    try {
      localStorage.setItem(KEY, collapsed ? '1' : '0');
    } catch {
      /* private mode: just don't remember it */
    }
  }, [collapsed]);
  return null;
}

function Frame({ children }: { children: ReactNode }) {
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
  return (
    <div className="flex min-h-screen bg-muted text-foreground">
      <RememberCollapsed />
      <Sidebar onOpenChangelog={() => setChangelog(true)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenPalette={() => setPalette(true)} />
        <main key={pathname} className="page-in mx-auto w-full max-w-7xl flex-1 p-6 max-md:p-4 lg:p-8">{children}</main>
      </div>
      <Palette open={palette} onOpenChange={setPalette} />
      <ShortcutsHelp open={help} onOpenChange={setHelp} />
      <Changelog open={changelog} onOpenChange={setChangelog} />
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider defaultCollapsed={read()}>
      <Frame>{children}</Frame>
    </SidebarProvider>
  );
}
