import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { productDetail } from './fixtures';
import { ProductFormPage } from './ProductFormPage';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname}</div>;
}

function setup(path: string) {
  const get = vi.spyOn(api, 'get').mockImplementation(async (p: string) => (p.startsWith('products/key-suggestion') ? { key: 'MYA' } : productDetail({}, { discord_webhook_url: 'https://discord.com/api/webhooks/1/x' })) as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ id: 9, url: '/products/9/', message: "Product 'My App' created." } as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue({ ...productDetail(), message: "Product 'Aum' updated." } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/products/create/" element={<ProductFormPage />} />
          <Route path="/products/:pk/edit/" element={<ProductFormPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, patch, toast };
}

it('the prefix is suggested from the name by the server until you type your own', async () => {
  const { get } = setup('/products/create/');
  await userEvent.type(await screen.findByLabelText('Name'), 'My App');
  await waitFor(() => expect(screen.getByLabelText('Ticket prefix')).toHaveValue('MYA'));
  expect(get).toHaveBeenCalledWith('products/key-suggestion/?name=My%20App');
  await userEvent.clear(screen.getByLabelText('Ticket prefix'));
  await userEvent.type(screen.getByLabelText('Ticket prefix'), 'zz!1');
  expect(screen.getByLabelText('Ticket prefix')).toHaveValue('ZZ1');
});

it('creating posts the form with milestones and goes to the new product', async () => {
  const { post } = setup('/products/create/');
  await userEvent.type(await screen.findByLabelText('Name'), 'My App');
  await userEvent.type(screen.getByLabelText('Milestone 1 title'), 'MVP');
  await userEvent.type(screen.getByLabelText('Milestone 1 target date'), '2026-12-01');
  await userEvent.click(screen.getByRole('button', { name: 'Create Product' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('products/', expect.objectContaining({ name: 'My App', default_environment: 'production', milestones: [{ title: 'MVP', date: '2026-12-01' }] })));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/products/9/'));
});

it('needs a name, and shows the server’s field errors', async () => {
  const { post } = setup('/products/create/');
  await userEvent.click(await screen.findByRole('button', { name: 'Create Product' }));
  expect(await screen.findByText('This field is required.')).toBeInTheDocument();
  expect(post).not.toHaveBeenCalled();
  post.mockRejectedValue(new ApiError('Could not save.', 400, { errors: { key: ['AUM already uses it.'] } }));
  await userEvent.type(screen.getByLabelText('Name'), 'x');
  await userEvent.click(screen.getByRole('button', { name: 'Create Product' }));
  expect(await screen.findByText('AUM already uses it.')).toBeInTheDocument();
});

it('editing starts from the saved values and patches', async () => {
  const { patch } = setup('/products/3/edit/');
  expect(await screen.findByLabelText('Name')).toHaveValue('Aum');
  expect(screen.getByLabelText('Ticket prefix')).toHaveValue('AUM');
  expect(screen.getByLabelText('Discord webhook URL')).toHaveValue('https://discord.com/api/webhooks/1/x');
  await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith('products/3/', expect.objectContaining({ name: 'Aum', key: 'AUM' })));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/'));
});
