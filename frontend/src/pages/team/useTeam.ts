import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { TeamResponse } from './types';

export const useTeam = (query: string) =>
  useQuery({ queryKey: ['team', query], queryFn: () => api.get<TeamResponse>(`team/${query ? `?${query}` : ''}`), placeholderData: keepPreviousData });

export function useTeamRefresh() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['team'] });
    qc.invalidateQueries({ queryKey: ['bootstrap'] });
  };
}

export function useRemoveMember() {
  const refresh = useTeamRefresh();
  return async (id: number) => {
    try {
      const r = await api.delete<{ message: string }>(`team/${id}/`);
      refresh();
      toast(r.message, 'success');
      return true;
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Something went wrong.', 'error');
      return false;
    }
  };
}
