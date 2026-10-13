import {
  Banknote, CalendarDays, ChartColumn, CircleCheck, ClipboardList, Clock, FileText, Headset, History, House,
  LayoutDashboard, Package, Percent, SlidersHorizontal, Sparkles, Ticket, TriangleAlert, User, Users, Wallet, type LucideIcon,
} from 'lucide-react';
import type { Bootstrap } from '@/lib/bootstrap';
import type { ProductNav } from '@/lib/useProductNav';

export type NavItem = { key: string; label: string; href: string; icon: LucideIcon; badge?: number; react: boolean };
export type NavSection = { label?: string; items: NavItem[]; product?: ProductNav };

// Paths the React router owns. Everything else is a normal link to a legacy page.
const REACT_PATH_RES = [
  /^\/notifications\/$/,
  /^\/tickets\/(kanban\/|list\/)?$/,
  /^\/products\/\d+\/tickets\/(kanban\/|list\/)?$/,
  /^\/tickets\/(create\/|\d+\/|\d+\/edit\/)$/,
  /^\/products\/\d+\/tickets\/(create\/|\d+\/)$/,
  /^\/products\/(create\/|\d+\/(edit\/|api\/)?)?$/,
  /^\/dsr\/$/,
  /^\/payroll\/(preview\/|holidays\/|profiles\/|me\/(\d+\/)?|runs\/\d+\/|payslips\/\d+\/)?$/,
  /^\/leave\/(apply\/|calendar\/|approvals\/|policies\/)?$/,
  /^\/attendance\/(team\/|timesheet\/(\d+\/)?|corrections\/(request\/)?|\d+\/edit\/)?$/,
  /^\/(team|profile)\/$/,
  /^\/dashboards\/(reports\/|audit\/|product\/\d+\/)?$/,
  /^\/feedback\/(create\/|cs-hub\/|\d+\/)?$/,
  /^\/products\/\d+\/(surveys|rules)\/(create\/)?$/,
  /^\/automation\/(create\/|\d+\/edit\/)?$/,
  /^\/errors\/(create\/|\d+\/)?$/,
  /^\/products\/\d+\/errors\/(create\/|\d+\/)?$/,
];
export const isReactPath = (path: string) => REACT_PATH_RES.some((re) => re.test(path));

export const productIdFromPath = (path: string): number | null => {
  const m = /^\/products\/(\d+)\//.exec(path);
  return m ? Number(m[1]) : null;
};

const item = (b: Bootstrap, key: string, label: string, icon: LucideIcon, badge?: number): NavItem => ({
  key,
  label,
  icon,
  href: b.urls[key],
  badge: badge || undefined,
  react: isReactPath(b.urls[key]),
});

export function navSections(b: Bootstrap): NavSection[] {
  const sections: NavSection[] = [
    {
      items: [
        item(b, 'home', 'Home', House),
        item(b, 'products', 'Products', Package),
        item(b, 'tickets', 'All tickets', Ticket, b.counts.open_tickets),
        item(b, 'errors', 'All errors', TriangleAlert, b.counts.open_errors),
        item(b, 'reports', 'Reports', ChartColumn),
        item(b, 'automation', 'All automation', Sparkles),
      ],
    },
    {
      label: 'Operations',
      items: [
        item(b, 'cs_hub', 'CS Hub', Headset),
        item(b, 'feedback', 'All feedback', FileText),
        item(b, 'attendance', 'My attendance', Clock),
        item(b, 'leave', 'My leave', CalendarDays),
        item(b, 'leave_calendar', 'Leave calendar', CalendarDays),
        item(b, 'dsr', 'DSR Sheet', ClipboardList),
        item(b, 'payslips', 'My payslips', Banknote),
      ],
    },
  ];
  if (b.is_admin) {
    sections.push({
      label: 'Admin',
      items: [
        item(b, 'team_attendance', 'Team attendance', Users),
        item(b, 'timesheet', 'Timesheet', CalendarDays),
        item(b, 'corrections', 'Corrections', Clock, b.counts.pending_corrections),
        item(b, 'leave_approvals', 'Leave approvals', CircleCheck),
        item(b, 'payroll', 'Payroll', Wallet),
        item(b, 'payroll_setup', 'Payroll setup', Percent),
        item(b, 'leave_policies', 'Leave Policy', SlidersHorizontal),
        item(b, 'team', 'Team', User),
        item(b, 'audit_log', 'Audit log', History),
      ],
    });
  }
  return sections;
}

// One item is active: the one whose URL is the longest prefix of the path. A
// substring test would light several up at once (the bug the legacy sidebar had).
export function activeKey(pathname: string, sections: NavSection[]): string | null {
  let best: NavItem | null = null;
  for (const it of sections.flatMap((s) => s.items)) {
    if (pathname.startsWith(it.href) && (!best || it.href.length > best.href.length)) best = it;
  }
  return best?.key ?? null;
}

// The sidebar's product section, shown while the URL is under /products/<id>/.
export function productSection(nav: ProductNav): NavSection {
  const it = (key: string, label: string, icon: LucideIcon, href: string, badge?: number): NavItem => ({
    key, label, icon, href, badge: badge || undefined, react: isReactPath(href),
  });
  return {
    product: nav,
    items: [
      it('p_overview', 'Overview', LayoutDashboard, nav.urls.overview),
      it('p_errors', 'Errors', TriangleAlert, nav.urls.errors, nav.counts.errors),
      it('p_tickets', 'Tickets', Ticket, nav.urls.tickets, nav.counts.tickets),
      it('p_surveys', 'Feedback', FileText, nav.urls.surveys, nav.counts.surveys),
      it('p_rules', 'Automation', Sparkles, nav.urls.rules, nav.counts.rules),
    ],
  };
}
