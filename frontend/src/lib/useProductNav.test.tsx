import { afterEach, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { api } from './api';
import { useProductNav } from './useProductNav';

afterEach(() => vi.restoreAllMocks());

const nav = { id: 3, name: 'App', counts: { errors: 0, tickets: 1, surveys: 0, rules: 0 }, urls: {}, products: [], all_url: '/products/' };
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
);

it('fetches the nav for product pages', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue(nav);
  const { result } = renderHook(() => useProductNav('/products/3/tickets/'), { wrapper });
  expect(result.current).toBeUndefined();
  await waitFor(() => expect(result.current?.name).toBe('App'));
  expect(get).toHaveBeenCalledWith('products/3/nav/');
});

it('does nothing outside product pages', () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue(nav);
  const { result } = renderHook(() => useProductNav('/tickets/'), { wrapper });
  expect(result.current).toBeUndefined();
  expect(get).not.toHaveBeenCalled();
});
