import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { errorDetail } from './fixtures';
import { ErrorDetailPage } from './ErrorDetailPage';
import type { ErrorDetail } from './types';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname}</div>;
}

function setup(path = '/products/3/errors/1/', data: ErrorDetail = errorDetail(), failWith?: Error) {
  const get = failWith ? vi.spyOn(api, 'get').mockRejectedValue(failWith) : vi.spyOn(api, 'get').mockResolvedValue(data as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue(data as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 1 } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/errors/:id/" element={<ErrorDetailPage />} />
          <Route path="/products/:pk/errors/:error_pk/" element={<ErrorDetailPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, del, toast };
}

it('shows the group: stats, trend, releases, occurrences', async () => {
  const { get } = setup('/errors/1/', errorDetail({ first_version: '1.0', regression_count: 2 }));
  expect(await screen.findByRole('heading', { name: /TypeError: foo/ })).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('errors/1/');
  expect(screen.getByText('Affected users')).toBeInTheDocument();
  expect(screen.getByText(/Came back after being resolved 2 times/)).toBeInTheDocument();
  expect(screen.getByText('Last 30 days')).toBeInTheDocument();
  expect(screen.getByText('at foo()')).toBeInTheDocument();
  expect(screen.getByText('User: u1')).toBeInTheDocument();
});

it('Resolve posts the status and toasts the server message', async () => {
  const { post, toast } = setup();
  post.mockResolvedValue({ ...errorDetail({ status: 'resolved', status_label: 'Resolved' }), message: 'Error group resolved.' } as never);
  await screen.findByRole('heading', { name: /TypeError/ });
  await userEvent.click(screen.getByRole('button', { name: 'Resolve' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('errors/1/status/', { status: 'resolved' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Error group resolved.', 'success'));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument());
});

it('Create Ticket posts convert-to-ticket and lists the linked ticket', async () => {
  const { post } = setup();
  post.mockResolvedValue({
    ...errorDetail({}, { linked_tickets: [{ id: 5, key: 'AUM-005', title: 'Fix it', status: 'open', status_label: 'Open', url: '/products/3/tickets/5/' }] }),
    message: 'Ticket AUM-005 created from error #1.',
  } as never);
  await screen.findByRole('heading', { name: /TypeError/ });
  await userEvent.click(screen.getByRole('button', { name: 'Create Ticket from Error' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('errors/1/convert-to-ticket/', {}));
  expect(await screen.findByText('AUM-005')).toBeInTheDocument();
});

it('delete is only offered to owners and admins, asks first, then leaves for the list', async () => {
  const { del } = setup('/products/3/errors/1/', errorDetail({ can_delete: true }));
  await screen.findByRole('heading', { name: /TypeError/ });
  await userEvent.click(screen.getByRole('button', { name: /Delete Error/ }));
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(await screen.findByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('errors/1/'));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/errors/'));
});

it('no delete button without the right', async () => {
  setup();
  await screen.findByRole('heading', { name: /TypeError/ });
  expect(screen.queryByRole('button', { name: /Delete Error/ })).not.toBeInTheDocument();
});

it('a 404 and a wrong product both say not found', async () => {
  setup('/errors/9/', errorDetail(), new ApiError('Not found.', 404, {}));
  expect(await screen.findByText('Error not found.')).toBeInTheDocument();
});

it('an error under another product’s URL is not found', async () => {
  setup('/products/4/errors/1/');
  expect(await screen.findByText('Error not found.')).toBeInTheDocument();
});
