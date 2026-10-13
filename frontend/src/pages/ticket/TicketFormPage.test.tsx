import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as bootstrap from '@/lib/bootstrap';
import * as toasts from '@/lib/toast';
import { meta } from '@/pages/tickets/fixtures';
import { sampleBootstrap } from '@/test-fixtures';
import { detail } from './fixtures';
import { TicketFormPage } from './TicketFormPage';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname}</div>;
}

function setup(path: string, opts: { detailError?: Error } = {}) {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  vi.spyOn(api, 'get').mockImplementation(async (p: string) => {
    if (p.startsWith('tickets/meta')) return meta as never;
    if (opts.detailError) throw opts.detailError;
    return detail({ id: 5, key: 'AUM-001', url: '/products/3/tickets/5/' }) as never;
  });
  const post = vi.spyOn(api, 'post').mockResolvedValue({ key: 'AUM-014', url: '/products/3/tickets/14/', warnings: [] } as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue(detail({ id: 5, key: 'AUM-001', url: '/products/3/tickets/5/' }) as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/tickets/create/" element={<TicketFormPage />} />
          <Route path="/products/:pk/tickets/create/" element={<TicketFormPage />} />
          <Route path="/tickets/:id/edit/" element={<TicketFormPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { post, patch, toast };
}

const submit = () => userEvent.click(screen.getByRole('button', { name: /create ticket|save changes/i }));

it('creates a company-wide ticket with the defaults and goes to it', async () => {
  const { post, toast } = setup('/tickets/create/');
  await userEvent.type(await screen.findByLabelText('Title'), 'Crash on login');
  await submit();
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/', {
    title: 'Crash on login', description: '', ticket_type: 'bug', priority: 'medium', product: null, assignees: [], deadline: '',
  }));
  expect(toast).toHaveBeenCalledWith('Ticket AUM-014 created.', 'success');
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/tickets/14/'));
});

it('picking a product, people and a deadline sends them', async () => {
  const { post } = setup('/tickets/create/');
  await userEvent.type(await screen.findByLabelText('Title'), 'T');
  await userEvent.type(screen.getByLabelText('Description'), 'details');
  await userEvent.click(screen.getByRole('combobox', { name: 'Product' }));
  await userEvent.click(await screen.findByRole('option', { name: 'App' }));
  await userEvent.click(screen.getByRole('button', { name: 'Assignees' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'Ann Lee' }));
  await userEvent.keyboard('{Escape}');
  fireEvent.change(screen.getByLabelText('Deadline'), { target: { value: '2026-10-20T10:00' } });
  await submit();
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/', expect.objectContaining({ description: 'details', product: 3, assignees: [5], deadline: '2026-10-20T10:00' })));
});

it('on a product page the product is fixed and sent, and not shown as a field', async () => {
  const { post } = setup('/products/3/tickets/create/');
  await userEvent.type(await screen.findByLabelText('Title'), 'T');
  expect(screen.queryByRole('combobox', { name: 'Product' })).not.toBeInTheDocument();
  await submit();
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/', expect.objectContaining({ product: 3 })));
});

it('warnings about skipped assignees are shown', async () => {
  const { post, toast } = setup('/tickets/create/');
  post.mockResolvedValue({ key: 'AUM-014', url: '/tickets/14/', warnings: ['Not assigned (no access to App): bob.'] } as never);
  await userEvent.type(await screen.findByLabelText('Title'), 'T');
  await submit();
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Not assigned (no access to App): bob.', 'warning'));
});

it('an empty title is refused before anything is sent', async () => {
  const { post } = setup('/tickets/create/');
  await screen.findByLabelText('Title');
  await submit();
  expect(await screen.findByText('This field is required.')).toBeInTheDocument();
  expect(post).not.toHaveBeenCalled();
});

it('server field errors show under their fields and the values stay', async () => {
  const { post, toast } = setup('/tickets/create/');
  post.mockRejectedValue(
    new ApiError('Could not save. Deadline: Enter a valid date/time.', 400, {
      errors: { deadline: ['Enter a valid date/time.'], title: ['Too long.'] },
    }),
  );
  await userEvent.type(await screen.findByLabelText('Title'), 'Keep me');
  await submit();
  expect(await screen.findByText('Enter a valid date/time.')).toBeInTheDocument();
  expect(screen.getByText('Too long.')).toBeInTheDocument();
  expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe('Keep me');
  expect(toast).toHaveBeenCalledWith('Could not save. Deadline: Enter a valid date/time.', 'error');
  expect(screen.getByTestId('loc')).toHaveTextContent('/tickets/create/');
});

it('a double click on Create sends one request', async () => {
  const { post } = setup('/tickets/create/');
  post.mockReturnValue(new Promise(() => {}) as never);
  await userEvent.type(await screen.findByLabelText('Title'), 'T');
  await userEvent.dblClick(screen.getByRole('button', { name: /create ticket/i }));
  expect(post).toHaveBeenCalledTimes(1);
});

it('Cancel goes back to the right board', async () => {
  setup('/products/3/tickets/create/');
  await screen.findByLabelText('Title');
  expect(screen.getAllByRole('link', { name: 'Cancel' })[0]).toHaveAttribute('href', '/products/3/tickets/');
});

it('edit is prefilled, saves with PATCH and returns to the ticket', async () => {
  const { patch, toast } = setup('/tickets/5/edit/');
  const title = (await screen.findByLabelText('Title')) as HTMLInputElement;
  expect(title.value).toBe('Login bug');
  expect((screen.getByLabelText('Description') as HTMLTextAreaElement).value).toBe('Cannot sign in');
  expect(screen.getByRole('button', { name: 'Assignees' })).toHaveTextContent('Ann Lee');
  expect(screen.queryByRole('combobox', { name: 'Product' })).not.toBeInTheDocument();
  await userEvent.clear(title);
  await userEvent.type(title, 'Renamed');
  await submit();
  await waitFor(() => expect(patch).toHaveBeenCalledWith('tickets/5/', {
    title: 'Renamed', description: 'Cannot sign in', ticket_type: 'bug', priority: 'high', status: 'open', assignees: [5], deadline: '',
  }));
  expect(toast).toHaveBeenCalledWith('Ticket AUM-001 updated.', 'success');
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/tickets/5/'));
});

it('editing a ticket the person cannot open says so', async () => {
  setup('/tickets/5/edit/', { detailError: new ApiError('Not found.', 404, {}) });
  expect(await screen.findByText('Ticket not found.')).toBeInTheDocument();
});
