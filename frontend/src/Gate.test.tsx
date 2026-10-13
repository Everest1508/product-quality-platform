import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as bootstrap from '@/lib/bootstrap';
import { sampleBootstrap } from '@/test-fixtures';
import { Gate } from './Gate';

afterEach(() => vi.restoreAllMocks());

const result = (over: object) => over as ReturnType<typeof bootstrap.useBootstrap>;

it('a failed background refresh keeps the app on screen', () => {
  vi.spyOn(bootstrap, 'useBootstrap').mockReturnValue(result({ isPending: false, isError: true, data: sampleBootstrap(), refetch: vi.fn() }));
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/nowhere/']}><Gate /></MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.queryByText(/couldn.t load the app/i)).not.toBeInTheDocument();
  expect(screen.getByText('Page not found.')).toBeInTheDocument();
});

it('a failed first load shows a retry', () => {
  vi.spyOn(bootstrap, 'useBootstrap').mockReturnValue(result({ isPending: false, isError: true, data: undefined, refetch: vi.fn() }));
  render(<MemoryRouter><Gate /></MemoryRouter>);
  expect(screen.getByText(/couldn.t load the app/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
});
