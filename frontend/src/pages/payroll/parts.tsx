import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { PageHeader } from '@/components/ui/page-header';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { Person } from './types';
import { TableCell, TableHead } from '@/components/ui/table';
import { Avatar } from '@/components/ui/avatar';

const TABS: [string, string, boolean][] = [['/payroll/', 'Runs', true], ['/payroll/profiles/', 'Salaries', true], ['/payroll/holidays/', 'Holidays', true], ['/payroll/me/', 'My payslips', false]];

// The shared header of every payroll page: title, subtitle, actions and the section tabs.
export function PayHeader({ title, sub, actions, admin = true }: { title: string; sub?: ReactNode; actions?: ReactNode; admin?: boolean }) {
  const { pathname } = useLocation();
  const active = (to: string) => (to === '/payroll/' ? pathname === to || pathname.startsWith('/payroll/runs/') || pathname.startsWith('/payroll/preview') || pathname.startsWith('/payroll/payslips/') : pathname.startsWith(to));
  return (
    <div className="space-y-3">
      <PageHeader title={title} sub={sub} actions={actions} />
      <Tabs value={TABS.find(([to]) => active(to))?.[0] ?? ''}>
        <TabsList aria-label="Payroll sections">
          {TABS.filter(([, , adminOnly]) => admin || !adminOnly).map(([to, label]) => (
            <TabsTrigger key={to} value={to} asChild><Link to={to}>{label}</Link></TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}

export const Who = ({ p }: { p: Person }) => (
  <div className="flex items-center gap-2">
    <Avatar name={p.name} />
    <div><div className="font-medium leading-tight">{p.name}</div><div className="text-xs text-muted-foreground">{p.username}</div></div>
  </div>
);

export const LockBadge = ({ locked }: { locked: boolean }) => <Badge variant={locked ? 'default' : 'success'}>{locked ? 'locked' : 'open'}</Badge>;
export const Num = ({ children, strong }: { children: ReactNode; strong?: boolean }) => <TableCell className={`p-3 text-right tabular-nums ${strong ? 'font-semibold' : ''}`}>{children}</TableCell>;
export const Th = ({ children, num }: { children?: ReactNode; num?: boolean }) => <TableHead className={`p-3 font-medium ${num ? 'text-right' : ''}`}>{children}</TableHead>;
export const Note = ({ children }: { children: ReactNode }) => <div className="space-y-1 rounded-md bg-secondary p-3 text-xs text-muted-foreground">{children}</div>;
