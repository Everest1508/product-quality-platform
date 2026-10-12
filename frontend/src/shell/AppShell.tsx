import { useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
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
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
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
        <Topbar onOpenNav={() => setOpen(true)} changelogOpen={changelog} onChangelogOpenChange={setChangelog} />
        <main className="mx-auto w-full max-w-6xl flex-1 p-6 max-md:p-4">{children}</main>
      </div>
    </div>
  );
}
