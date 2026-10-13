import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { keyRow, productDetail } from './fixtures';
import { ProductDetailPage } from './ProductDetailPage';
import type { ProductDetail } from './types';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname}</div>;
}

function setup(data: ProductDetail = productDetail(), failWith?: Error) {
  const get = failWith ? vi.spyOn(api, 'get').mockRejectedValue(failWith) : vi.spyOn(api, 'get').mockResolvedValue(data as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue(data as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue(data as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/products/3/']}>
        <Routes>
          <Route path="/products/:pk/" element={<ProductDetailPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, del, toast };
}

it('shows the product, its counts, versions, keys and team access', async () => {
  setup();
  expect(await screen.findByRole('heading', { name: 'Aum' })).toBeInTheDocument();
  expect(screen.getByText('1.0.0')).toBeInTheDocument();
  expect(screen.getByText('server')).toBeInTheDocument();
  expect(screen.getByText('Not configured')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Review errors →' })).toHaveAttribute('href', '/products/3/errors/');
  expect(screen.getByText('Allocated members')).toBeInTheDocument();
});

it('a non-admin sees no edit, delete or team access, and a viewer no key form', async () => {
  setup(productDetail({ is_admin: false, can_manage_keys: false, members: [] }));
  await screen.findByRole('heading', { name: 'Aum' });
  expect(screen.queryByRole('link', { name: 'Edit' })).not.toBeInTheDocument();
  expect(screen.queryByText('Allocated members')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Generate' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Rotate' })).not.toBeInTheDocument();
  expect(screen.getByText(/can create and rotate keys/)).toBeInTheDocument();
});

it('Generate posts the name and shows the raw key once', async () => {
  const { post, toast } = setup();
  post.mockResolvedValue({ ...productDetail({ api_keys: [keyRow(), keyRow({ id: 8, name: 'billing' })] }), raw_key: 'f'.repeat(64), message: "API key 'billing' created." } as never);
  await screen.findByRole('heading', { name: 'Aum' });
  await userEvent.type(screen.getByRole('textbox', { name: 'Key name' }), 'billing');
  await userEvent.click(screen.getByRole('button', { name: 'Generate' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('products/3/api-keys/', { name: 'billing' }));
  expect(await screen.findByText(/Copy it now/)).toBeInTheDocument();
  expect(screen.getByText('f'.repeat(64))).toBeInTheDocument();
  expect(toast).toHaveBeenCalledWith("API key 'billing' created.", 'success');
  await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
  expect(screen.queryByText('f'.repeat(64))).not.toBeInTheDocument();
});

it('Rotate asks first, sends the chosen grace, and shows the new key', async () => {
  const { post } = setup();
  post.mockResolvedValue({ ...productDetail(), raw_key: 'a'.repeat(64), message: 'Key rotated — the old key works until Oct 14.' } as never);
  await screen.findByRole('heading', { name: 'Aum' });
  await userEvent.click(screen.getByRole('button', { name: 'Rotate' }));
  expect(post).not.toHaveBeenCalled();
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Rotate' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('api-keys/7/rotate/', { grace: '1d' }));
  expect(await screen.findByText(/New key ready/)).toBeInTheDocument();
});

it('Revoke asks first', async () => {
  const { post } = setup();
  await screen.findByRole('heading', { name: 'Aum' });
  await userEvent.click(screen.getByRole('button', { name: 'Revoke' }));
  expect(post).not.toHaveBeenCalled();
  const dialog = await screen.findByRole('dialog');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Revoke' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('api-keys/7/revoke/'));
});

it('adds and deletes versions', async () => {
  const { post, del } = setup();
  await screen.findByRole('heading', { name: 'Aum' });
  await userEvent.click(screen.getByRole('button', { name: /Add$/ }));
  await userEvent.type(screen.getByRole('textbox', { name: 'Version' }), '2.0.0');
  await userEvent.click(screen.getByRole('checkbox'));
  await userEvent.click(within(screen.getByRole('textbox', { name: 'Version' }).closest('form')!).getByRole('button', { name: 'Add' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('products/3/versions/', { version_string: '2.0.0', is_current: true }));
  await userEvent.click(screen.getByRole('button', { name: 'Delete version 1.0.0' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('products/3/versions/21/'));
});

it('allocates and removes members', async () => {
  const { post } = setup();
  await screen.findByText('Allocated members');
  await userEvent.click(screen.getByRole('button', { name: 'Allocate' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('products/3/access/', { user_id: 2 }));
});

it('milestones advance and add', async () => {
  const { post } = setup();
  await screen.findByRole('heading', { name: 'Aum' });
  await userEvent.click(screen.getByRole('button', { name: 'Upcoming' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('milestones/11/toggle/'));
  await userEvent.click(screen.getByRole('button', { name: /Add flow node/ }));
  await userEvent.type(await screen.findByLabelText('Milestone title'), 'Beta');
  await userEvent.click(screen.getByRole('button', { name: 'Add node' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('products/3/milestones/', expect.objectContaining({ title: 'Beta', order: 2 })));
});

it('delete asks, then goes to the list', async () => {
  const { del } = setup();
  del.mockResolvedValue({ deleted: 'Aum' } as never);
  await screen.findByRole('heading', { name: 'Aum' });
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('products/3/'));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/products/'));
  expect(screen.getByText('elsewhere')).toBeInTheDocument();
});

it('a 404 says not found', async () => {
  setup(productDetail(), new ApiError('Not found.', 404, {}));
  expect(await screen.findByText('Product not found.')).toBeInTheDocument();
});
