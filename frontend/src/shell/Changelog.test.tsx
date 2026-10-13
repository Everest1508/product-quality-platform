import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import * as bootstrap from '@/lib/bootstrap';
import { sampleBootstrap } from '@/test-fixtures';
import { Changelog } from './Changelog';

afterEach(() => vi.restoreAllMocks());

const releases = [
  { tag: '1.12.0', date: '2026-10-12', title: 'newest', released: true, summary: 'In short: newest.', sections: [
    { name: 'New', label: 'New', slug: 'added', count: 1, items: ['<strong>Shiny.</strong> A thing'] },
    { name: 'Fixed', label: 'Fixed', slug: 'fixed', count: 1, items: ['<strong>Broken.</strong> Now works'] },
  ] },
  { tag: '1.11.0', date: '2026-10-11', title: 'older', released: true, summary: 'In short: older.', sections: [
    { name: 'New', label: 'New', slug: 'added', count: 1, items: ['<strong>Ancient.</strong> Once'] },
  ] },
];

function setup() {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  const get = vi.spyOn(api, 'get').mockResolvedValue({ releases });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Changelog open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
  return get;
}

it('fetches the changelog and shows the newest release alone', async () => {
  const get = setup();
  expect(await screen.findByText('Shiny.')).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('/api/v1/changelog/');
  expect(screen.queryByText('Ancient.')).not.toBeInTheDocument();
  expect(screen.getByText(/What.s new in/)).toHaveTextContent('v1.12.0');
});

it('older releases are one click away', async () => {
  setup();
  await screen.findByText('Shiny.');
  expect(screen.queryByText('Ancient.')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /older releases/i }));
  await userEvent.click(await screen.findByRole('button', { name: /v1\.11\.0/ })); // an older release opens when you click it
  expect(await screen.findByText('Ancient.')).toBeInTheDocument();
});

it('a type chip narrows every release', async () => {
  setup();
  await screen.findByText('Shiny.');
  await userEvent.click(screen.getByRole('button', { name: /^Fixed/ }));
  expect(screen.queryByText('Shiny.')).not.toBeInTheDocument();
  expect(screen.getByText('Broken.')).toBeInTheDocument();
});

it('says so when the changelog cannot load', async () => {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  vi.spyOn(api, 'get').mockRejectedValue(new Error('Request failed (500)'));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Changelog open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/couldn.t load/i)).toBeInTheDocument();
});

it('shows a release name beside its version', async () => {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  vi.spyOn(api, 'get').mockResolvedValue({ releases: [{ tag: '1.12.0', name: 'Heron', date: '2026-10-12', title: 'newest', released: true, summary: '', sections: [] }] } as never);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Changelog open onOpenChange={() => {}} /></QueryClientProvider>);
  expect(await screen.findByText('Heron')).toBeInTheDocument();
  expect(screen.getByText('Latest')).toBeInTheDocument();
});

it('search looks through older releases too and a miss says so', async () => {
  setup();
  await screen.findByText('Shiny.');
  await userEvent.type(screen.getByRole('searchbox', { name: /search the changelog/i }), 'ancient');
  expect(await screen.findByText('Ancient.')).toBeInTheDocument();
  expect(screen.queryByText('Shiny.')).not.toBeInTheDocument();
  await userEvent.clear(screen.getByRole('searchbox'));
  await userEvent.type(screen.getByRole('searchbox'), 'zzzz');
  expect(await screen.findByText(/nothing matches/i)).toBeInTheDocument();
});
