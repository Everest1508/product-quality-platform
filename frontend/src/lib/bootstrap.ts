import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export type FlashMessage = { text: string; tags: 'success' | 'error' | 'info' | 'warning' };
export type Bootstrap = {
  user: { id: number; name: string; initial: string; role: string | null; role_label: string };
  company: { id: number; name: string };
  workspaces: { company_id: number; name: string; role_label: string; current: boolean }[];
  counts: { open_tickets: number; open_errors: number; pending_corrections: number };
  is_admin: boolean;
  version: string;
  csrf: string;
  vapid_key: string;
  messages: FlashMessage[];
  urls: Record<string, string>;
};

export const useBootstrap = () =>
  useQuery({
    queryKey: ['bootstrap'],
    queryFn: () => api.get<Bootstrap>('bootstrap/'),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

export function useBootstrapData(): Bootstrap {
  const { data } = useBootstrap();
  if (!data) throw new Error('Bootstrap not loaded');
  return data;
}
