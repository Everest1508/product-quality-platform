import { useRef, useState } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import { ArrowRightLeft, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { shortDate } from '@/lib/time';
import { toast } from '@/lib/toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Kanban } from '@/components/ui/kanban';
import { cn } from '@/lib/utils';
import { applyMove } from './moveTicket';
import { Assignees, priorityDot } from './TicketTable';
import type { BoardResponse, TicketItem } from './types';

type Props = {
  data: BoardResponse;
  queryKey: QueryKey;
  selecting: boolean;
  selected: Set<number>;
  onSelect(id: number, on: boolean): void;
  onDelete(item: TicketItem): void;
  // True while the data shown belongs to the previous filters: moving then would write the wrong board.
  disabled?: boolean;
};

export function Board({ data, queryKey, selecting, selected, onSelect, onDelete, disabled = false }: Props) {
  const qc = useQueryClient();
  const [pending, setPending] = useState<Set<number>>(new Set());
  const inflight = useRef<Set<number>>(new Set()); // checked synchronously, so two drops in one tick send one request
  const labelOf = (key: string) => data.columns.find((c) => c.key === key)?.label ?? key;

  const move = async (t: TicketItem, to: string) => {
    if (disabled || t.status === to || inflight.current.has(t.id)) return;
    inflight.current.add(t.id);
    setPending((s) => new Set(s).add(t.id));
    try {
      // A refetch already in flight would otherwise snap the card back for a moment.
      await qc.cancelQueries({ queryKey });
      qc.setQueryData<BoardResponse>(queryKey, (cur) => (cur ? applyMove(cur, t.id, to) : cur));
      await api.post(`tickets/${t.id}/status/`, { status: to });
      toast(`${t.key}: status ${t.status_label} → ${labelOf(to)}.`, 'success');
      qc.invalidateQueries({ queryKey: ['bootstrap'] });
      qc.invalidateQueries({ queryKey: ['product-nav'] });
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Cannot move ticket', 'error');
    } finally {
      inflight.current.delete(t.id);
      setPending((s) => {
        const next = new Set(s);
        next.delete(t.id);
        return next;
      });
      // Settle on the server's truth. Restoring an old snapshot would undo other cards' moves.
      qc.invalidateQueries({ queryKey: ['tickets'] });
    }
  };

  // befui's Kanban owns dragging (mouse and Alt+arrows). It reports the whole board after a drop; we turn that into one status change.
  const columns = data.columns.map((c) => ({ id: c.key, title: c.label }));
  const value = Object.fromEntries(data.columns.map((c) => [c.key, c.tickets.map((t) => ({ id: String(t.id), t }))]));
  const onChange = (next: Record<string, { id: string; t: TicketItem }[]>) => {
    for (const [status, cards] of Object.entries(next)) {
      const moved = cards.find((c) => c.t.status !== status);
      if (moved) void move(moved.t, status);
    }
  };

  const card = (t: TicketItem) => (
    <div data-ticket-card data-ticket-id={t.id} data-url={t.url} className={cn('space-y-2', pending.has(t.id) && 'opacity-60')}>
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="flex min-w-0 items-center gap-1.5">
          {selecting && <Checkbox aria-label={`Select ticket ${t.key}`} checked={selected.has(t.id)} onCheckedChange={(c) => onSelect(t.id, c === true)} />}
          <span className="truncate">
            {t.key}
            {t.product && <> · <b className="font-medium text-foreground">{t.product.name}</b></>}
          </span>
        </span>
        <span className="flex shrink-0 items-center">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={`Move ${t.key}`}><ArrowRightLeft /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {!disabled && data.columns.filter((c) => c.key !== t.status).map((c) => (
                <DropdownMenuItem key={c.key} onSelect={() => void move(t, c.key)}>{c.label}</DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          {t.can_delete && <Button variant="ghost" size="icon-sm" aria-label={`Delete ${t.key}`} onClick={() => onDelete(t)}><Trash2 /></Button>}
        </span>
      </div>
      <a href={t.url} className="block break-words font-medium hover:underline">{t.title}</a>
      <div className="flex items-center gap-2 text-xs">
        <Badge variant="outline">{t.type_label}</Badge>
        <span className="inline-flex items-center gap-1.5">
          <span className={cn('size-2 rounded-full', priorityDot[t.priority])} />
          {t.priority_label}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <Assignees people={t.assignees} />
        {t.deadline && (
          <span className={cn('text-xs', t.is_overdue ? 'text-destructive' : 'text-muted-foreground')} title={new Date(t.deadline).toLocaleString()}>
            {t.is_overdue ? 'Overdue · ' : 'Due '}
            {shortDate(t.deadline)}
          </span>
        )}
      </div>
    </div>
  );

  return (
    <Kanban
      columns={columns}
      value={value}
      onChange={(next) => !disabled && onChange(next)}
      renderCard={(it) => card(it.t)}
      className="[&_section]:w-72"
    />
  );
}
