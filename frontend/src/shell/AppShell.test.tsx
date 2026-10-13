import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { socket } from '@/lib/presence';
import * as productNav from '@/lib/useProductNav';
import { AppShell } from './AppShell';
import * as bootstrap from '@/lib/bootstrap';
import { sampleBootstrap } from '@/test-fixtures';

afterEach(() => vi.restoreAllMocks());

function renderShell(path = '/tickets/', over = {}) {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap(over));
  localStorage.clear();
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <AppShell>
          <p>content</p>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it('renders the nav, marks the current page, and shows the content', () => {
  renderShell();
  expect(screen.getByRole('link', { name: /all tickets/i })).toHaveAttribute('aria-current', 'page');
  expect(screen.getAllByRole('link', { current: 'page' })).toHaveLength(1);
  expect(screen.getByText('content')).toBeInTheDocument();
  expect(screen.getByText('6')).toBeInTheDocument();
});

it('collapses and remembers it under the legacy storage key', async () => {
  renderShell();
  await userEvent.click(screen.getByRole('button', { name: /collapse/i }));
  expect(localStorage.getItem('pqSidebarCollapsed')).toBe('1');
});

it('starts collapsed when the legacy key says so', () => {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  localStorage.setItem('pqSidebarCollapsed', '1');
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter><AppShell><p>x</p></AppShell></MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByRole('button', { name: /expand/i })).toBeInTheDocument();
});

it('shows the admin items only to admins', () => {
  renderShell('/tickets/', { is_admin: true });
  expect(screen.getByRole('link', { name: /payroll setup/i })).toBeInTheDocument();
});

it('lists the workspaces in the switcher and the version in the footer', () => {
  renderShell();
  expect(screen.getByRole('button', { name: /what.s new/i })).toHaveTextContent('v1.12.0');
  expect(screen.getByRole('button', { name: /acme corp/i })).toBeInTheDocument();
});

it('reconnects the socket when the page comes back from the back/forward cache', () => {
  const start = vi.spyOn(socket, 'start').mockImplementation(() => {});
  renderShell();
  start.mockClear();
  window.dispatchEvent(Object.assign(new Event('pageshow'), { persisted: false }));
  expect(start).not.toHaveBeenCalled();
  window.dispatchEvent(Object.assign(new Event('pageshow'), { persisted: true }));
  expect(start).toHaveBeenCalledTimes(1);
});

it('shows the product section and switcher on a product page, with one active item', async () => {
  vi.spyOn(productNav, 'useProductNav').mockReturnValue({
    id: 3, name: 'Billing App', counts: { errors: 2, tickets: 5, surveys: 0, rules: 0 },
    urls: { overview: '/products/3/', errors: '/products/3/errors/', tickets: '/products/3/tickets/', surveys: '/products/3/surveys/', rules: '/products/3/rules/' },
    products: [{ id: 3, name: 'Billing App', url: '/products/3/tickets/' }, { id: 4, name: 'Mobile', url: '/products/4/tickets/' }],
    all_url: '/products/',
  });
  renderShell('/products/3/tickets/kanban/');
  expect(screen.getAllByRole('link', { current: 'page' })).toHaveLength(1);
  expect(screen.getByRole('link', { current: 'page' })).toHaveAccessibleName(/^Tickets/);
  expect(screen.getByRole('link', { name: /^Overview/ })).toHaveAttribute('href', '/products/3/');
  await userEvent.click(screen.getByRole('button', { name: /billing app/i }));
  expect(screen.getByRole('menuitem', { name: 'Mobile' })).toHaveAttribute('href', '/products/4/tickets/');
  expect(screen.getByRole('menuitem', { name: /view all products/i })).toHaveAttribute('href', '/products/');
});
