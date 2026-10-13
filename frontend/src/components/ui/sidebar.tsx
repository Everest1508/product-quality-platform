import * as React from 'react';
import { Link } from 'react-router-dom';
import { ChevronDownIcon, PanelLeftIcon } from './icons';
import { cn } from '@/lib/utils';
import { Sheet, SheetContent, SheetTitle } from './dialog';
import { Tooltip, TooltipProvider } from './tooltip';

interface SidebarState {
  /** Icon-only rail on desktop. */
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  /** Slide-over menu below the lg breakpoint. */
  mobileOpen: boolean;
  setMobileOpen: (v: boolean) => void;
  isDesktop: boolean;
}
const Ctx = React.createContext<SidebarState | null>(null);

export function useSidebar() {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error('Sidebar parts must be used inside <SidebarProvider>');
  return ctx;
}

function useIsDesktop() {
  const q = '(min-width: 1024px)';
  return React.useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(q);
      m.addEventListener('change', cb);
      return () => m.removeEventListener('change', cb);
    },
    () => window.matchMedia(q).matches,
    () => true,
  );
}

export function SidebarProvider({ children, defaultCollapsed = false }: { children: React.ReactNode; defaultCollapsed?: boolean }) {
  const [collapsed, setCollapsed] = React.useState(defaultCollapsed);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const isDesktop = useIsDesktop();
  const value = React.useMemo(() => ({ collapsed, setCollapsed, mobileOpen, setMobileOpen, isDesktop }), [collapsed, mobileOpen, isDesktop]);
  return (
    <Ctx.Provider value={value}>
      <TooltipProvider delayDuration={100}>{children}</TooltipProvider>
    </Ctx.Provider>
  );
}

/** Collapses the rail on desktop and opens the slide-over on mobile. */
export function SidebarTrigger({ className }: { className?: string }) {
  const { collapsed, setCollapsed, setMobileOpen, isDesktop } = useSidebar();
  return (
    <button
      type="button"
      aria-label="Toggle sidebar"
      onClick={() => (isDesktop ? setCollapsed(!collapsed) : setMobileOpen(true))}
      className={cn('grid size-8 place-items-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/40', className)}
    >
      <PanelLeftIcon className="size-4" />
    </button>
  );
}

export function Sidebar({ children, className }: { children: React.ReactNode; className?: string }) {
  const state = useSidebar();
  const { collapsed, mobileOpen, setMobileOpen, isDesktop } = state;
  return (
    <>
      <aside
        data-collapsed={collapsed}
        className={cn(
          'hidden shrink-0 flex-col overflow-x-hidden border-r bg-card transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] lg:flex',
          collapsed ? 'w-[3.75rem]' : 'w-60',
          className,
        )}
      >
        {children}
      </aside>
      <Sheet open={mobileOpen && !isDesktop} onOpenChange={setMobileOpen}>
        <SheetContent side="left" aria-describedby={undefined} className="w-64 max-w-[16rem] gap-0 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          {/* The slide-over is always expanded, whatever the desktop rail is doing. */}
          <Ctx.Provider value={{ ...state, collapsed: false }}>
            <div className="flex h-full flex-col" onClick={(e) => (e.target as HTMLElement).closest('a,button[data-nav]') && setMobileOpen(false)}>
              {children}
            </div>
          </Ctx.Provider>
        </SheetContent>
      </Sheet>
    </>
  );
}

export const SidebarHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex h-14 shrink-0 items-center gap-2.5 border-b px-4', className)} {...props} />
);

export const SidebarContent = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <nav className={cn('grid flex-1 content-start gap-5 overflow-y-auto p-2.5', className)} {...props} />
);

export const SidebarFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('shrink-0 border-t p-2.5', className)} {...props} />
);

export function SidebarGroup({ label, children }: { label?: string; children: React.ReactNode }) {
  const { collapsed } = useSidebar();
  return (
    <div className="grid gap-0.5">
      {label &&
        (collapsed ? (
          <span className="mx-auto mb-1 h-px w-5 bg-border" />
        ) : (
          <p className="mb-1 animate-in px-2.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">{label}</p>
        ))}
      {children}
    </div>
  );
}

export interface SidebarSubItem {
  label: string;
  href?: string;
  active?: boolean;
  onClick?: () => void;
}

export interface SidebarItemProps {
  icon?: React.ReactNode;
  label: string;
  href?: string;
  /** In-app route: rendered as a router Link instead of a full-page anchor. */
  to?: string;
  active?: boolean;
  /** Small count shown on the right, or as a dot when collapsed. */
  badge?: React.ReactNode;
  onClick?: () => void;
  /** Nested links. Makes the item expandable. */
  items?: SidebarSubItem[];
}

const row =
  'flex h-8 w-full items-center gap-2.5 rounded-md px-2.5 text-[13px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/40 [&_svg]:size-4 [&_svg]:shrink-0';
const rowTone = (active?: boolean) =>
  active ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-secondary hover:text-foreground';

export function SidebarItem({ icon, label, href, to, active, badge, onClick, items }: SidebarItemProps) {
  const { collapsed, setCollapsed } = useSidebar();
  const childActive = items?.some((i) => i.active);
  const [open, setOpen] = React.useState(!!childActive);
  const Tag: React.ElementType = to ? Link : href ? 'a' : 'button';

  const inner = (
    <Tag
      {...(to ? { to } : href ? { href } : { type: 'button' as const })}
      data-nav={!items ? '' : undefined}
      aria-current={active ? 'page' : undefined}
      aria-expanded={items ? open && !collapsed : undefined}
      onClick={() => {
        if (items) {
          if (collapsed) setCollapsed(false);
          setOpen(collapsed ? true : !open);
        }
        onClick?.();
      }}
      className={cn(row, rowTone(active || (collapsed && childActive)), collapsed && 'relative mx-auto size-9 justify-center px-0')}
    >
      {icon}
      {collapsed ? (
        <>
          <span className="sr-only">{label}</span>
          {badge && <span className="absolute right-1.5 top-1.5 size-1.5 animate-pop rounded-full bg-primary" />}
        </>
      ) : (
        <>
          <span className="flex-1 animate-in truncate text-left">{label}</span>
          {badge && <span className="animate-in rounded-full bg-primary/10 px-1.5 text-[11px] font-semibold text-primary">{badge}</span>}
          {items && <ChevronDownIcon className={cn('!size-3.5 transition-transform', open && 'rotate-180')} />}
        </>
      )}
    </Tag>
  );

  return (
    <div>
      {collapsed ? <Tooltip content={label} side="right">{inner}</Tooltip> : inner}
      {items && open && !collapsed && (
        <div className="ml-[1.15rem] mt-0.5 grid gap-0.5 border-l pl-2.5">
          {items.map((s) => {
            const SubTag = s.href ? 'a' : 'button';
            return (
              <SubTag
                key={s.label}
                {...(s.href ? { href: s.href } : { type: 'button' as const })}
                data-nav=""
                aria-current={s.active ? 'page' : undefined}
                onClick={s.onClick}
                className={cn('flex h-7 w-full items-center rounded-md px-2.5 text-left text-[13px] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/40', s.active ? 'font-medium text-accent-foreground' : 'text-muted-foreground hover:text-foreground')}
              >
                {s.label}
              </SubTag>
            );
          })}
        </div>
      )}
    </div>
  );
}
