import * as React from 'react';
import { cn } from '@/lib/utils';
import { SidebarProvider, SidebarTrigger } from './sidebar';

/**
 * Page frame: sidebar on the left, topbar and scrolling content on the right.
 * It fills its parent's height, so give the parent one (h-screen for a full app).
 */
export function AppShell({
  sidebar,
  children,
  className,
  defaultCollapsed,
}: {
  sidebar: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  defaultCollapsed?: boolean;
}) {
  return (
    <SidebarProvider defaultCollapsed={defaultCollapsed}>
      <div className={cn('flex h-dvh w-full overflow-hidden bg-background text-foreground', className)}>
        {sidebar}
        <div className="flex min-w-0 flex-1 flex-col">{children}</div>
      </div>
    </SidebarProvider>
  );
}

/** Sticky top bar. Starts with the sidebar toggle, then your children. */
export function Topbar({ children, className }: { children?: React.ReactNode; className?: string }) {
  return (
    <header className={cn('z-30 flex h-14 shrink-0 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-md', className)}>
      <SidebarTrigger />
      {children}
    </header>
  );
}

export const AppContent = ({ className, ...props }: React.HTMLAttributes<HTMLElement>) => (
  <main className={cn('min-h-0 flex-1 overflow-y-auto p-4 sm:p-6', className)} {...props} />
);

export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('mb-5 flex flex-wrap items-end justify-between gap-3', className)}>
      <div className="grid gap-1">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-[13px] text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
