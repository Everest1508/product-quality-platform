import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api } from '@/lib/api';
import { productList } from './fixtures';
import { ProductsPage } from './ProductsPage';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function setup(url = '/products/', data = productList()) {
  const get = vi.spyOn(api, 'get').mockResolvedValue(data as never);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/products/" element={<ProductsPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return get;
}

it('shows the tiles, the cards and the New product button for admins', async () => {
  setup();
  expect(await screen.findByText('Marketing site')).toBeInTheDocument();
  expect(screen.getByText('2 total')).toBeInTheDocument();
  expect(screen.getByText('Need attention')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /New product/ })).toHaveAttribute('href', '/products/create/');
  expect(screen.getByRole('link', { name: 'Edit Aum' })).toHaveAttribute('href', '/products/3/edit/');
});

it('hides create and edit from non-admins', async () => {
  setup('/products/', productList(undefined, { can_create: false }));
  await screen.findByText('Marketing site');
  expect(screen.queryByRole('link', { name: /New product/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Edit Aum' })).not.toBeInTheDocument();
});

it('table view is in the URL and rows open the product', async () => {
  setup('/products/?view=table');
  await userEvent.click(await screen.findByText('Bolt'));
  expect(await screen.findByText('elsewhere')).toBeInTheDocument();
  expect(screen.getByTestId('loc')).toHaveTextContent('/products/4/');
});

it('view toggle does not reach the server as a filter, search does after a pause', async () => {
  const get = setup('/products/?view=table&sort=-name');
  await screen.findByText('Bolt');
  expect(get).toHaveBeenCalledWith('products/?sort=-name');
  await userEvent.type(screen.getByRole('searchbox', { name: 'Search products' }), 'bol');
  await waitFor(() => expect(get).toHaveBeenCalledWith('products/?sort=-name&q=bol'), { timeout: 2000 });
});

it('says so when nothing matches', async () => {
  setup('/products/?q=zzz', productList([]));
  expect(await screen.findByText('No products found')).toBeInTheDocument();
  expect(screen.getByText('Try a different search term.')).toBeInTheDocument();
});
