import { DownloadIcon, SparkleIcon } from '@/components/ui/icons';
import { useLocation } from 'react-router-dom';
import { useBootstrapData } from '@/lib/bootstrap';
import { useInstallPrompt } from '@/lib/pwa';
import { useProductNav } from '@/lib/useProductNav';
import { Sidebar as FrameSidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarHeader, SidebarItem, useSidebar } from '@/components/ui/sidebar';
import { CompanySwitcher } from './CompanySwitcher';
import { ProductSwitcher } from './ProductSwitcher';
import { activeKey, navSections, productSection } from './nav';

type Props = { onOpenChangelog(): void };

// Reads the rail state itself: the mobile slide-over always shows the full sidebar.
function Brand({ href }: { href: string }) {
  const { collapsed } = useSidebar();
  return (
    <a href={href} aria-label="PQ Platform home" className="flex items-center gap-2 font-semibold">
      <svg viewBox="5 5 23 23" className="size-6 shrink-0 text-primary" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <circle cx="16" cy="16" r="9" /><circle cx="16" cy="16" r="3.6" /><path d="M19.5 19.5L26 26" />
      </svg>
      {!collapsed && <span className="animate-in">PQ Platform</span>}
    </a>
  );
}

export function Sidebar({ onOpenChangelog }: Props) {
  const b = useBootstrapData();
  const pwa = useInstallPrompt();
  const { pathname } = useLocation();
  const productNav = useProductNav(pathname);
  const base = navSections(b);
  const sections = productNav ? [base[0], productSection(productNav), ...base.slice(1)] : base;
  const active = activeKey(pathname, sections);
  return (
    <FrameSidebar className="sticky top-0 h-screen">
      <SidebarHeader>
        <Brand href={b.urls.home} />
      </SidebarHeader>
      <SidebarContent>
        <CompanySwitcher />
        {sections.map((s, i) => (
          <div key={s.label ?? (s.product ? 'product' : i)} role="group" aria-label={s.label ?? (s.product ? 'Current product' : 'Main')}>
            <SidebarGroup label={s.label}>
              {s.product && <div className="pb-1"><ProductSwitcher nav={s.product} /></div>}
              {s.items.map((it) => (
                <SidebarItem
                  key={it.key}
                  label={it.label}
                  icon={<it.icon />}
                  badge={it.badge || undefined}
                  active={it.key === active}
                  {...(it.react ? { to: it.href } : { href: it.href })}
                />
              ))}
            </SidebarGroup>
          </div>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <div className="grid gap-0.5">
          <SidebarItem icon={<SparkleIcon />} label={`What's new`} badge={`v${b.version}`} onClick={onOpenChangelog} />
          {pwa.available && <SidebarItem icon={<DownloadIcon />} label="Install app" onClick={pwa.install} />}
        </div>
      </SidebarFooter>
    </FrameSidebar>
  );
}
