import { afterEach, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ReactNode } from 'react';
import { api } from '@/lib/api';
import { filtersFromParams, paramsFromFilters, useTicketMeta, useTicketScope, useTickets } from './useTicketQuery';

afterEach(() => vi.restoreAllMocks());

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
const wrap = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client()}>{children}</QueryClientProvider>;

it('round-trips filters through the URL and drops empty values', () => {
  const p = paramsFromFilters({ q: 'login', type: '', priority: 'high', overdue: '1', page: '1' });
  expect(p.toString()).toBe('q=login&priority=high&overdue=1');
  expect(filtersFromParams(new URLSearchParams('q=a&status=open&page=3&junk=1'))).toEqual({ q: 'a', status: 'open', page: '3' });
});

it('product pages send scope=product, global pages do not, and the product filter is ignored when scoped', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({ view: 'list', items: [], page: { number: 1, num_pages: 1, count: 0, per_page: 25 }, open_count: 0 });
  const a = renderHook(() => useTickets('list', 3, { q: 'x', product: '9' }), { wrapper: wrap });
  await waitFor(() => expect(a.result.current.isSuccess).toBe(true));
  const b = renderHook(() => useTickets('board', null, {}), { wrapper: wrap });
  await waitFor(() => expect(b.result.current.isSuccess).toBe(true));
  expect(get).toHaveBeenCalledWith('tickets/?view=list&scope=product&product=3&q=x');
  expect(get).toHaveBeenCalledWith('tickets/?view=board');
});

it('global pages keep the product filter', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({ view: 'board', columns: [], total: 0, open_count: 0 });
  const r = renderHook(() => useTickets('board', null, { product: '9' }), { wrapper: wrap });
  await waitFor(() => expect(r.result.current.isSuccess).toBe(true));
  expect(get).toHaveBeenCalledWith('tickets/?view=board&product=9');
});

it('meta is scoped like the list', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({ statuses: [], types: [], priorities: [], products: [], members: [] });
  const a = renderHook(() => useTicketMeta(3), { wrapper: wrap });
  await waitFor(() => expect(a.result.current.isSuccess).toBe(true));
  const b = renderHook(() => useTicketMeta(null), { wrapper: wrap });
  await waitFor(() => expect(b.result.current.isSuccess).toBe(true));
  expect(get).toHaveBeenCalledWith('tickets/meta/?scope=product&product=3');
  expect(get).toHaveBeenCalledWith('tickets/meta/');
});

function scope(path: string) {
  const w = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/tickets/*" element={<>{children}</>} />
        <Route path="/products/:pk/tickets/*" element={<>{children}</>} />
      </Routes>
    </MemoryRouter>
  );
  return renderHook(() => useTicketScope(), { wrapper: w }).result.current;
}

it('reads the product and the view from the route', () => {
  expect(scope('/tickets/')).toEqual({ productId: null, view: 'board' });
  expect(scope('/tickets/kanban/')).toEqual({ productId: null, view: 'board' });
  expect(scope('/tickets/list/')).toEqual({ productId: null, view: 'list' });
  expect(scope('/products/7/tickets/')).toEqual({ productId: 7, view: 'board' });
  expect(scope('/products/7/tickets/list/')).toEqual({ productId: 7, view: 'list' });
});
