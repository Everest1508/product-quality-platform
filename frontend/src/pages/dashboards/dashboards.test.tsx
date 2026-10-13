import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import { AuditLogPage } from './AuditLogPage';
import { ProductDashboardPage } from './ProductDashboardPage';
import { ReportsPage } from './ReportsPage';
import type { AuditResponse, ProductDashboard, Report } from './types';

afterEach(() => vi.restoreAllMocks());

const ev = (over = {}) => ({ id: 1, type: 'ticket_created', label: 'Ticket Created', pill: 'open', title: 'Ticket #1 created', description: 'details', created_at: '2026-10-13T10:00:00Z', url: '/tickets/1/', actor: { name: 'ann', initial: 'A' }, ...over });

const report = (): Report => ({
  scope: 'company', start_date: '2026-10-13', end_date: '2026-10-13', total_events: 3,
  presets: [{ label: 'Today', start: '2026-10-13', end: '2026-10-13' }, { label: 'Last 7 days', start: '2026-10-07', end: '2026-10-13' }],
  kpis: [{ key: 'tickets_created', label: 'Tickets created', tone: 'blue', value: 1, before: 2, pct: 50, dir: 'down' }, { key: 'total_events', label: 'All activity', tone: 'gray', value: 3, before: 0, pct: null, dir: 'up' }],
  daily_bars: [{ date: '2026-10-13', label: true, created: 100, resolved: 0, captured: 0, fixed: 0, row: { tickets_created: 1, tickets_resolved: 0, errors_captured: 0, errors_resolved: 0 } }],
  resolution_rate: 50, error_fix_rate: null, tickets: { created: 2, resolved: 1, in_progress: 0, assigned: 0 }, errors: { captured: 0, resolved: 0, ignored: 0 },
  feedback_received: 0, survey_responses: 0, product_bars: [{ name: 'Aum', total: 4, pct: 100 }], event_mix: [{ label: 'Ticket Created', count: 1, pct: 100 }],
  product_rows: [{ name: 'Aum', tickets_created: 1, tickets_resolved: 0, errors_captured: 0, errors_resolved: 0, feedback: 0 }],
  daily: [{ date: '2026-10-13', tickets_created: 1, tickets_resolved: 0, tickets_closed: 0, errors_captured: 0, errors_resolved: 0, feedback: 0, total: 1 }], recent: [ev()],
});

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function mount(path: string, element: React.ReactNode, route: string, data: unknown) {
  const get = vi.spyOn(api, 'get').mockImplementation(async () => data as never);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={element} /></Routes><Probe /></MemoryRouter>
    </QueryClientProvider>,
  );
  return get;
}

it('the report shows KPI changes, rings and the recent log, and presets set the range in the URL', async () => {
  const get = mount('/dashboards/reports/?start_date=2026-10-13&end_date=2026-10-13', <ReportsPage />, '/dashboards/reports/', report());
  expect((await screen.findAllByText('Tickets created')).length).toBeGreaterThan(0);
  expect(screen.getByText('vs 2 before')).toBeInTheDocument();
  expect(screen.getByText('new')).toBeInTheDocument();
  expect(screen.getByText('Recent activity log')).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('reports/?start_date=2026-10-13&end_date=2026-10-13');
  await userEvent.click(screen.getByRole('radio', { name: 'Last 7 days' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/dashboards/reports/?start_date=2026-10-07&end_date=2026-10-13');
});

it('an empty report says so', async () => {
  mount('/dashboards/reports/', <ReportsPage />, '/dashboards/reports/', { ...report(), recent: [], product_rows: [], daily: [], daily_bars: [], product_bars: [], event_mix: [] });
  expect(await screen.findByText('No activity')).toBeInTheDocument();
  expect(screen.getByText('No product activity in this range.')).toBeInTheDocument();
});

const audit = (): AuditResponse => ({ items: [ev(), ev({ id: 2, title: 'Err captured', url: '', actor: null })], page: { number: 1, num_pages: 1, count: 2, per_page: 25 }, event_types: [['ticket_created', 'Ticket Created']], members: [{ id: 1, name: 'ann' }] });

it('the audit log lists events with links and filters through the URL', async () => {
  mount('/dashboards/audit/', <AuditLogPage />, '/dashboards/audit/', audit());
  expect(await screen.findByRole('link', { name: 'Ticket #1 created' })).toHaveAttribute('href', '/tickets/1/');
  expect(screen.getByText('Err captured')).toBeInTheDocument();
  expect(screen.getByText('2 events')).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('From'), '2026-10-01');
  expect(screen.getByTestId('loc')).toHaveTextContent('from=2026-10-01');
  expect(await screen.findByRole('button', { name: 'Clear' })).toBeInTheDocument();
});

it('an empty audit log says so', async () => {
  mount('/dashboards/audit/?q=zzz', <AuditLogPage />, '/dashboards/audit/', { ...audit(), items: [], page: { number: 1, num_pages: 1, count: 0, per_page: 25 } });
  expect(await screen.findByText('No activity logged')).toBeInTheDocument();
});

const pd = (): ProductDashboard => ({
  product: { id: 3, name: 'Aum' }, errors: { total: 4, open: 2, resolved: 1 }, tickets: { total: 6, open: 3 }, survey: { avg_score: 4.5, responses: 2, count: 1 }, uptime: 99.5,
  errors_by_day: [{ date: '2026-10-12', count: 2 }, { date: '2026-10-13', count: 0 }], ticket_burndown: [{ date: '2026-10-12', open: 3 }, { date: '2026-10-13', open: 2 }],
  errors_by_severity: [{ severity: 'critical', count: 2 }], tickets_by_status: [{ status: 'in_progress', count: 3 }],
});

it('the product dashboard shows the numbers and the breakdowns', async () => {
  const get = mount('/dashboards/product/3/', <ProductDashboardPage />, '/dashboards/product/:product_pk/', pd());
  expect(await screen.findByRole('heading', { name: /Aum/ })).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('dashboards/product/3/');
  expect(screen.getByText('99.5%')).toBeInTheDocument();
  expect(screen.getByText('In progress')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Product page' })).toHaveAttribute('href', '/products/3/');
});

it('a missing product says not found', async () => {
  vi.spyOn(api, 'get').mockRejectedValue(new ApiError('Not found.', 404, {}));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/dashboards/product/9/']}><Routes><Route path="/dashboards/product/:product_pk/" element={<ProductDashboardPage />} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByText('Product not found.')).toBeInTheDocument());
});
