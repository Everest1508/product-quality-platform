import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import type { Person } from './types';

const TABS: [string, string, boolean][] = [['/payroll/', 'Runs', true], ['/payroll/profiles/', 'Salaries', true], ['/payroll/holidays/', 'Holidays', true], ['/payroll/me/', 'My payslips', false]];

// The shared header of every payroll page: title, subtitle, actions and the section tabs.
export function PayHeader({ title, sub, actions, admin = true }: { title: string; sub?: ReactNode; actions?: ReactNode; admin?: boolean }) {
  const { pathname } = useLocation();
  const active = (to: string) => (to === '/payroll/' ? pathname === to || pathname.startsWith('/payroll/runs/') || pathname.startsWith('/payroll/preview') || pathname.startsWith('/payroll/payslips/') : pathname.startsWith(to));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><h1 className="text-xl font-semibold">{title}</h1>{sub && <p className="mt-1 text-sm text-muted-foreground">{sub}</p>}</div>
        {actions && <div className="flex gap-2">{actions}</div>}
      </div>
      <nav aria-label="Payroll sections" className="flex gap-1 border-b">
        {TABS.filter(([, , adminOnly]) => admin || !adminOnly).map(([to, label]) => (
          <Link key={to} to={to} aria-current={active(to) ? 'page' : undefined} className={`-mb-px border-b-2 px-3 py-2 text-sm ${active(to) ? 'border-primary font-medium' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>{label}</Link>
        ))}
      </nav>
    </div>
  );
}

export const Who = ({ p }: { p: Person }) => (
  <div className="flex items-center gap-2">
    <span className="grid size-7 place-items-center rounded-full bg-accent text-xs font-medium text-accent-foreground">{p.initial}</span>
    <div><div className="font-medium leading-tight">{p.name}</div><div className="text-xs text-muted-foreground">{p.username}</div></div>
  </div>
);

export const LockBadge = ({ locked }: { locked: boolean }) => <Badge variant={locked ? 'default' : 'success'}>{locked ? 'locked' : 'open'}</Badge>;
export const Num = ({ children, strong }: { children: ReactNode; strong?: boolean }) => <td className={`p-3 text-right tabular-nums ${strong ? 'font-semibold' : ''}`}>{children}</td>;
export const Th = ({ children, num }: { children?: ReactNode; num?: boolean }) => <th className={`p-3 font-medium ${num ? 'text-right' : ''}`}>{children}</th>;
export const Note = ({ children }: { children: ReactNode }) => <div className="space-y-1 rounded-md bg-secondary p-3 text-xs text-muted-foreground">{children}</div>;
