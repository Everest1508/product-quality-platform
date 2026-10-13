import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import { productIdFromPath } from '@/shell/nav';

export type ProductNav = {
  id: number;
  name: string;
  counts: { errors: number; tickets: number; surveys: number; rules: number };
  urls: { overview: string; errors: string; tickets: string; surveys: string; rules: string };
  products: { id: number; name: string; url: string }[];
  all_url: string;
};

// The product section of the sidebar, only while the URL is under /products/<id>/.
export function useProductNav(pathname: string): ProductNav | undefined {
  const id = productIdFromPath(pathname);
  const q = useQuery({
    queryKey: ['product-nav', id],
    enabled: id !== null,
    queryFn: () => api.get<ProductNav>(`products/${id}/nav/`),
    staleTime: 60_000,
  });
  return id === null ? undefined : q.data;
}
