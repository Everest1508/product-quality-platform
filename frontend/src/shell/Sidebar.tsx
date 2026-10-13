import { ChevronLeft, ChevronRight, Download, Sparkles } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useBootstrapData } from '@/lib/bootstrap';
import { useInstallPrompt } from '@/lib/pwa';
import { useProductNav } from '@/lib/useProductNav';
import { cn } from '@/lib/utils';
import { CompanySwitcher } from './CompanySwitcher';
import { ProductSwitcher } from './ProductSwitcher';
import { activeKey, navSections, productSection, type NavItem } from './nav';

type Props = { collapsed: boolean; onToggle(): void; open: boolean; onClose(): void; onOpenChangelog(): void };

function Row({ it, active, collapsed }: { it: NavItem; active: boolean; collapsed: boolean }) {
  const cls = cn(
    'flex items-center gap-3 rounded-md px-2.5 py-2 text-sm text-muted-foreground outline-none hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/40',
    active && 'bg-accent font-medium text-accent-foreground',
  );
  const inner = (
    <>
      <it.icon className="size-4 shrink-0" />
      {!collapsed && <span className="min-w-0 flex-1 truncate">{it.label}</span>}
      {!collapsed && it.badge ? (
        <span className="rounded-full bg-secondary px-1.5 text-[11px] font-medium text-secondary-foreground">{it.badge}</span>
      ) : null}
    </>
  );
  const common = { className: cls, title: collapsed ? it.label : undefined, 'aria-current': active ? ('page' as const) : undefined };
  return it.react ? (
    <Link to={it.href} {...common}>{inner}</Link>
  ) : (
    <a href={it.href} {...common}>{inner}</a>
  );
}

export function Sidebar({ collapsed, onToggle, open, onClose, onOpenChangelog }: Props) {
  const b = useBootstrapData();
  const pwa = useInstallPrompt();
  const { pathname } = useLocation();
  const productNav = useProductNav(pathname);
  const base = navSections(b);
  const sections = productNav ? [base[0], productSection(productNav), ...base.slice(1)] : base;
  const active = activeKey(pathname, sections);
  return (
    <>
      <aside
        className={cn(
          'flex shrink-0 flex-col gap-3 overflow-y-auto border-r bg-card p-3 transition-[width] md:sticky md:top-0 md:h-screen max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-40 max-md:w-64 max-md:transition-transform',
          collapsed ? 'w-16' : 'w-60',
          open ? 'max-md:translate-x-0' : 'max-md:-translate-x-full',
        )}
      >
        <a href={b.urls.home} aria-label="PQ Platform home" className="flex items-center gap-2 px-1.5 py-1 font-semibold">
          <svg viewBox="5 5 23 23" className="size-6 shrink-0 text-primary" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <circle cx="16" cy="16" r="9" /><circle cx="16" cy="16" r="3.6" /><path d="M19.5 19.5L26 26" />
          </svg>
          {!collapsed && <span>PQ Platform</span>}
        </a>
        <CompanySwitcher collapsed={collapsed} />
        {sections.map((s, i) => (
          <nav key={s.label ?? (s.product ? 'product' : i)} aria-label={s.label ?? (s.product ? 'Current product' : 'Main')} className="flex flex-col gap-0.5">
            {s.product && <div className="pb-1"><ProductSwitcher nav={s.product} collapsed={collapsed} /></div>}
            {s.label && !collapsed && (
              <div className="px-2.5 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{s.label}</div>
            )}
            {s.items.map((it) => (
              <Row key={it.key} it={it} active={it.key === active} collapsed={collapsed} />
            ))}
          </nav>
        ))}
        <div className="mt-auto flex flex-col gap-0.5 border-t pt-3">
          <button
            type="button"
            onClick={onOpenChangelog}
            aria-label={`What's new in v${b.version}`}
            title={collapsed ? `What's new in v${b.version}` : undefined}
            className="flex items-center gap-3 rounded-md px-2.5 py-2 text-sm text-muted-foreground outline-none hover:bg-secondary hover:text-foreground"
          >
            <Sparkles className="size-4 shrink-0" />
            {!collapsed && (
              <>
                <span className="flex-1 text-left">What's new</span>
                <span className="rounded-full bg-secondary px-1.5 text-[11px] font-medium">v{b.version}</span>
              </>
            )}
          </button>
          {pwa.available && (
            <button type="button" onClick={pwa.install} className="flex items-center gap-3 rounded-md px-2.5 py-2 text-sm text-muted-foreground outline-none hover:bg-secondary hover:text-foreground">
              <Download className="size-4 shrink-0" />
              {!collapsed && <span>Install app</span>}
            </button>
          )}
          <button
            type="button"
            onClick={onToggle}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="flex items-center gap-3 rounded-md px-2.5 py-2 text-sm text-muted-foreground outline-none hover:bg-secondary hover:text-foreground max-md:hidden"
          >
            {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={onClose} aria-hidden />}
    </>
  );
}
