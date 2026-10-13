import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { TicketItem } from './types';

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

// Delete one or many tickets, then refresh the lists and the sidebar counts.
export function useTicketActions() {
  const qc = useQueryClient();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['tickets'] });
    qc.invalidateQueries({ queryKey: ['bootstrap'] });
    qc.invalidateQueries({ queryKey: ['product-nav'] });
  };
  const fail = (e: unknown) => toast(e instanceof Error ? e.message : 'Something went wrong.', 'error');

  const deleteOne = useMutation({
    mutationFn: (t: TicketItem) => api.delete<{ deleted: string }>(`tickets/${t.id}/`),
    onSuccess: (r) => {
      toast(`Ticket ${r.deleted} deleted.`, 'success');
      refresh();
    },
    onError: fail,
  });

  const deleteMany = useMutation({
    mutationFn: (ids: number[]) => api.post<{ deleted: number; skipped: number }>('tickets/bulk-delete/', { ids }),
    onSuccess: (r) => {
      toast(`Deleted ${plural(r.deleted, 'ticket')}${r.skipped ? `, skipped ${r.skipped}` : ''}.`, 'success');
      refresh();
    },
    onError: fail,
  });

  return { deleteOne, deleteMany, refresh };
}
