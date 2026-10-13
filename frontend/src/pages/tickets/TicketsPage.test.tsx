import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api } from '@/lib/api';
import * as bootstrap from '@/lib/bootstrap';
import * as toasts from '@/lib/toast';
import * as productNav from '@/lib/useProductNav';
import { sampleBootstrap } from '@/test-fixtures';
import { meta, ticket } from './fixtures';
import { TicketsPage } from './TicketsPage';
import type { ListResponse } from './types';

afterEach(() => vi.restoreAllMocks());

const list = (items = [ticket(), ticket({ id: 2, key: 'AUM-002', title: 'Second' })], over: Partial<ListResponse['page']> = {}): ListResponse => ({
  view: 'list', items, page: { number: 1, num_pages: 1, count: items.length, per_page: 25, ...over }, open_count: 1,
});

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function setup(url: string, data: unknown = list()) {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  vi.spyOn(productNav, 'useProductNav').mockReturnValue(undefined);
  const get = vi.spyOn(api, 'get').mockImplementation(async (path: string) => (path.startsWith('tickets/meta') ? meta : data) as never);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/tickets/*" element={<TicketsPage />} />
          <Route path="/products/:pk/tickets/*" element={<TicketsPage />} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return get;
}

it('lists tickets with the count and open count in the header', async () => {
  setup('/tickets/list/');
  expect(await screen.findByText('Login bug')).toBeInTheDocument();
  expect(screen.getByText(/2 tickets · 1 open/)).toBeInTheDocument();
});

it('view links keep the filters, and New ticket points at the legacy form', async () => {
  setup('/tickets/list/?q=a');
  await screen.findByText('Login bug');
  expect(screen.getByRole('link', { name: 'Kanban' })).toHaveAttribute('href', '/tickets/kanban/?q=a');
  expect(screen.getByRole('link', { name: 'List' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('link', { name: /new ticket/i })).toHaveAttribute('href', '/tickets/create/');
});

it('product pages ask for the product scope and link New ticket to that product', async () => {
  const get = setup('/products/3/tickets/list/');
  await screen.findByText('Login bug');
  expect(get).toHaveBeenCalledWith('tickets/?view=list&scope=product&product=3');
  expect(screen.getByRole('link', { name: /new ticket/i })).toHaveAttribute('href', '/products/3/tickets/create/');
  expect(screen.queryByRole('combobox', { name: 'Filter by product' })).not.toBeInTheDocument();
});

it('changing a filter updates the URL', async () => {
  setup('/tickets/list/');
  await screen.findByText('Login bug');
  await userEvent.click(screen.getByRole('combobox', { name: 'Filter by priority' }));
  await userEvent.click(await screen.findByRole('option', { name: 'High' }));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/tickets/list/?priority=high'));
});

it('pagination sets the page in the URL', async () => {
  setup('/tickets/list/', list([ticket()], { num_pages: 3, count: 60 }));
  await screen.findByText('Login bug');
  await userEvent.click(screen.getByRole('button', { name: '2' }));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('page=2'));
});

it('empty states differ for a search and for no tickets', async () => {
  setup('/tickets/list/?q=zzz', list([]));
  expect(await screen.findByText('No tickets found')).toBeInTheDocument();
  expect(screen.getByText('Try a different search term.')).toBeInTheDocument();
});

it('empty without a search invites creating one', async () => {
  setup('/tickets/list/', list([]));
  expect(await screen.findByText('Create a ticket to start tracking work.')).toBeInTheDocument();
});

it('a failed load shows a retry', async () => {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  vi.spyOn(productNav, 'useProductNav').mockReturnValue(undefined);
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path.startsWith('tickets/meta')) return meta as never;
    throw new Error('Request failed (500)');
  });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/tickets/list/']}>
        <Routes><Route path="/tickets/*" element={<TicketsPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/couldn.t load tickets/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
});

it('deleting one ticket asks first, then calls the API and toasts', async () => {
  setup('/tickets/list/');
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 'AUM-001' });
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  await screen.findByText('Login bug');
  await userEvent.click(screen.getAllByRole('button', { name: /^delete/i })[0]);
  expect(await screen.findByText(/delete ticket AUM-001\?/i)).toBeInTheDocument();
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('tickets/1/'));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Ticket AUM-001 deleted.', 'success'));
});

it('cancelling the confirm does nothing', async () => {
  setup('/tickets/list/');
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 'x' });
  await screen.findByText('Login bug');
  await userEvent.click(screen.getAllByRole('button', { name: /^delete/i })[0]);
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }));
  expect(del).not.toHaveBeenCalled();
});

it('bulk delete: select mode, pick two, confirm, and report a partial result', async () => {
  setup('/tickets/list/');
  const post = vi.spyOn(api, 'post').mockResolvedValue({ deleted: 1, skipped: 1 });
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  await screen.findByText('Login bug');
  await userEvent.click(screen.getByRole('button', { name: 'Select' }));
  await userEvent.click(screen.getByRole('checkbox', { name: /select ticket AUM-001/i }));
  await userEvent.click(screen.getByRole('checkbox', { name: /select ticket AUM-002/i }));
  await userEvent.click(screen.getByRole('button', { name: /delete selected \(2\)/i }));
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/bulk-delete/', { ids: [1, 2] }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Deleted 1 ticket, skipped 1.', 'success'));
});

it('a delete that the server refuses toasts its reason', async () => {
  setup('/tickets/list/');
  vi.spyOn(api, 'delete').mockRejectedValue(new Error('You can only delete tickets you created.'));
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  await screen.findByText('Login bug');
  await userEvent.click(screen.getAllByRole('button', { name: /^delete/i })[0]);
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('You can only delete tickets you created.', 'error'));
});
