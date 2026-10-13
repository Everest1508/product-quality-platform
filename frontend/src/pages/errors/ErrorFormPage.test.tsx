import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { errorMeta } from './fixtures';
import { ErrorFormPage } from './ErrorFormPage';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname}</div>;
}

function setup(path: string) {
  const get = vi.spyOn(api, 'get').mockResolvedValue(errorMeta as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ id: 8, url: '/products/3/errors/8/', message: 'Error #8 created.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/errors/create/" element={<ErrorFormPage />} />
          <Route path="/products/:pk/errors/create/" element={<ErrorFormPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, toast };
}

it('a product page fixes the product and needs only a title', async () => {
  const { post, get } = setup('/products/3/errors/create/');
  await userEvent.type(await screen.findByLabelText('Title'), 'Kaput');
  expect(screen.queryByRole('combobox', { name: 'Product' })).not.toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('errors/meta/?scope=product&product=3');
  await userEvent.click(screen.getByRole('button', { name: 'Report Error' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('errors/', expect.objectContaining({ product: 3, title: 'Kaput', severity: 'medium', environment: 'production' })));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/errors/8/'));
});

it('the global form asks for a product and a title before sending', async () => {
  const { post } = setup('/errors/create/');
  await userEvent.click(await screen.findByRole('button', { name: 'Report Error' }));
  expect(await screen.findByText('Choose a product.')).toBeInTheDocument();
  expect(screen.getByText('This field is required.')).toBeInTheDocument();
  expect(post).not.toHaveBeenCalled();
});

it('server field errors show under their fields and the form stays', async () => {
  const { post, toast } = setup('/products/3/errors/create/');
  post.mockRejectedValue(new ApiError('Could not save.', 400, { errors: { title: ['Too long.'] }, detail: 'Could not save.' }));
  await userEvent.type(await screen.findByLabelText('Title'), 'x');
  await userEvent.click(screen.getByRole('button', { name: 'Report Error' }));
  expect(await screen.findByText('Too long.')).toBeInTheDocument();
  expect(toast).toHaveBeenCalledWith('Could not save.', 'error');
  expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/errors/create/');
});
