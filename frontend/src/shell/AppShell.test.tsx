import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { socket } from '@/lib/presence';
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
