import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api } from '@/lib/api';
import { apiDocs } from './fixtures';
import { ProductApiDocsPage } from './ProductApiDocsPage';

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

function setup() {
  vi.spyOn(api, 'get').mockResolvedValue(apiDocs() as never);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/products/3/api/']}>
        <Routes><Route path="/products/:pk/api/" element={<ProductApiDocsPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it('shows the endpoint, its fields, errors and this product’s keys', async () => {
  setup();
  expect(await screen.findByRole('heading', { name: 'Send data to Aum' })).toBeInTheDocument();
  expect(screen.getByText('/api/v1/errors/capture/')).toBeInTheDocument();
  expect(screen.getByText('What went wrong.')).toBeInTheDocument();
  expect(screen.getByText('Bad request')).toBeInTheDocument();
  expect(screen.getByText('abcd1234...')).toBeInTheDocument();
});

it('the language tab switches the snippet and is remembered', async () => {
  setup();
  expect(await screen.findByText('curl -X POST /errors')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('radio', { name: 'Python' }));
  expect(screen.getByText('import requests')).toBeInTheDocument();
  expect(localStorage.getItem('pqApiLang')).toBe('python');
});

it('copy puts the snippet on the clipboard', async () => {
  setup();
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  await userEvent.click(await screen.findByRole('button', { name: /Copy/ }));
  expect(writeText).toHaveBeenCalledWith('curl -X POST /errors');
});
