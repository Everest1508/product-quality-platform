import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api } from '@/lib/api';
import * as toasts from '@/lib/toast';
import * as productNav from '@/lib/useProductNav';
import { errorItem, errorList, errorMeta } from './fixtures';
import { ErrorsPage } from './ErrorsPage';
import type { ErrorListResponse } from './types';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function setup(url: string, data: ErrorListResponse = errorList()) {
  vi.spyOn(productNav, 'useProductNav').mockReturnValue(undefined);
  const get = vi.spyOn(api, 'get').mockImplementation(async (path: string) => (path.startsWith('errors/meta') ? errorMeta : data) as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 1 } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/errors/" element={<ErrorsPage />} />
          <Route path="/products/:pk/errors/" element={<ErrorsPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, del, toast };
}

it('lists groups with counts, flags and a chart', async () => {
  setup('/errors/', errorList([errorItem({ is_regression: true, new_in_release: '2.0' })], { open_count: 1 }));
  expect(await screen.findByText('TypeError: foo')).toBeInTheDocument();
  expect(screen.getByText(/1 group · 1 open/)).toBeInTheDocument();
  expect(screen.getByText('Regression')).toBeInTheDocument();
  expect(screen.getByText('New in 2.0')).toBeInTheDocument();
  expect(screen.getByRole('img', { name: /5 occurrences/ })).toBeInTheDocument();
});

it('a product page scopes the request and hides the product column', async () => {
  const { get } = setup('/products/3/errors/');
  await screen.findByText('TypeError: foo');
  expect(get).toHaveBeenCalledWith('errors/?scope=product&product=3');
  expect(screen.queryByRole('columnheader', { name: 'Product' })).not.toBeInTheDocument();
});

it('tabs set the status or the regressed filter in the URL', async () => {
  setup('/errors/', errorList([errorItem()], { regressed_count: 2 }));
  await screen.findByText('TypeError: foo');
  await userEvent.click(screen.getByRole('radio', { name: 'Resolved' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/errors/?status=resolved');
  await userEvent.click(screen.getByRole('radio', { name: /Regressed/ }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/errors/?regressed=1');
});

it('search waits for a pause, then filters', async () => {
  const { get } = setup('/errors/');
  await screen.findByText('TypeError: foo');
  await userEvent.type(screen.getByRole('searchbox', { name: 'Search errors' }), 'null');
  await waitFor(() => expect(get).toHaveBeenCalledWith('errors/?q=null'), { timeout: 2000 });
});

it('delete asks first, and only owners and admins get the button', async () => {
  const { del } = setup('/errors/', errorList([errorItem({ can_delete: true }), errorItem({ id: 2, title: 'Other', can_delete: false })]));
  await screen.findByText('TypeError: foo');
  expect(screen.getAllByRole('button', { name: /Delete error/ })).toHaveLength(1);
  await userEvent.click(screen.getByRole('button', { name: 'Delete error #1' }));
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(await screen.findByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('errors/1/'));
});

it('clicking a row opens the group', async () => {
  setup('/errors/');
  await userEvent.click(await screen.findByText('NullError: bar'));
  expect(await screen.findByText('elsewhere')).toBeInTheDocument();
  expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/errors/2/');
});

it('says so when nothing matches, and when loading fails', async () => {
  setup('/errors/?q=zzz', errorList([]));
  expect(await screen.findByText('No errors found')).toBeInTheDocument();
  expect(screen.getByText('Try a different search term.')).toBeInTheDocument();
});
