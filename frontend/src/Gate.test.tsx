import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { api } from '@/lib/api';
import { Gate } from './Gate';

afterEach(() => vi.restoreAllMocks());

it('a public page is shown without loading the app shell or bootstrap', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({ id: 4, name: 'Q1 NPS', description: '', type: 'nps', product: 'Aum', scores: [0, 1] } as never);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/feedback/respond/4/']}><Gate /></MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByRole('heading', { name: 'Q1 NPS' })).toBeInTheDocument();
  expect(get).toHaveBeenCalledTimes(1);
  expect(get).toHaveBeenCalledWith('public/surveys/4/');
  expect(screen.queryByText('Loading…')).not.toBeInTheDocument();
});
