import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { FieldErrors, TicketDetail, TicketInput } from './types';

export const useTicketDetail = (id: number) =>
  useQuery({ queryKey: ['ticket', id], queryFn: () => api.get<TicketDetail>(`tickets/${id}/`) });

const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

// Every control on the detail page goes through here: call the endpoint, put the
// fresh ticket into the cache, refresh the lists and sidebar counts, say what happened.
export function useTicketActions(id: number) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const cached = () => qc.getQueryData<TicketDetail>(['ticket', id]);

  const refreshLists = () => {
    qc.invalidateQueries({ queryKey: ['tickets'] });
    qc.invalidateQueries({ queryKey: ['bootstrap'] });
    qc.invalidateQueries({ queryKey: ['product-nav'] });
  };

  async function apply(name: string, call: () => Promise<TicketDetail>, success: (d: TicketDetail, before?: TicketDetail) => string) {
    const before = cached();
    setBusy(name);
    try {
      const data = await call();
      qc.setQueryData(['ticket', id], { ...data, message: undefined });
      refreshLists();
      toast(success(data, before), 'success');
      return data;
    } catch (e) {
      toast(reason(e), 'error');
      return undefined;
    } finally {
      setBusy(null);
    }
  }

  return {
    busy,
    setPriority: (priority: string) =>
      apply('priority', () => api.post<TicketDetail>(`tickets/${id}/priority/`, { priority }), (d, b) =>
        `${d.ticket.key}: priority ${b?.ticket.priority_label ?? ''} → ${d.ticket.priority_label}.`),
    assign: (ids: number[]) => apply('assign', () => api.post<TicketDetail>(`tickets/${id}/assign/`, { assignees: ids }), (d) => d.message ?? 'Assignees updated.'),
    setDeadline: (local: string | null) =>
      apply('deadline', () => api.post<TicketDetail>(`tickets/${id}/deadline/`, { deadline: local }), (d) =>
        d.ticket.deadline_local ? `${d.ticket.key}: deadline set.` : `${d.ticket.key}: deadline cleared.`),
    toggleFollow: () => apply('follow', () => api.post<TicketDetail>(`tickets/${id}/follow/`, {}), (d) => d.message ?? 'Updated.'),
    addComment: (body: string) => apply('comment', () => api.post<TicketDetail>(`tickets/${id}/comments/`, { body }), () => 'Comment added.'),
    async setStatus(status: string) {
      const before = cached();
      setBusy('status');
      try {
        await api.post(`tickets/${id}/status/`, { status });
        await qc.invalidateQueries({ queryKey: ['ticket', id] });
        refreshLists();
        const label = (key: string) => before?.statuses.find(([k]) => k === key)?.[1] ?? key;
        toast(`${before?.ticket.key ?? ''}: status ${before?.ticket.status_label ?? ''} → ${label(status)}.`, 'success');
        return true;
      } catch (e) {
        toast(reason(e), 'error');
        return false;
      } finally {
        setBusy(null);
      }
    },
    async remove() {
      setBusy('delete');
      try {
        const r = await api.delete<{ deleted: string }>(`tickets/${id}/`);
        refreshLists();
        toast(`Ticket ${r.deleted} deleted.`, 'success');
        return true;
      } catch (e) {
        toast(reason(e), 'error');
        return false;
      } finally {
        setBusy(null);
      }
    },
  };
}

type Created = { key: string; url: string; warnings: string[] };

// Create (id null) or edit. A 400 rejects with `fieldErrors` so the form can show them under their fields.
export async function saveTicket(id: number | null, input: TicketInput): Promise<Created> {
  try {
    if (id === null) return await api.post<Created>('tickets/', input);
    const saved = await api.patch<TicketDetail>(`tickets/${id}/`, input);
    return { key: saved.ticket.key, url: saved.ticket.url, warnings: [] };
  } catch (e) {
    const errors = (e as { body?: { errors?: FieldErrors } }).body?.errors;
    throw Object.assign(e as Error, { fieldErrors: errors ?? {} });
  }
}
