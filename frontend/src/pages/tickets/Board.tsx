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
};

export function Board({ data, queryKey, selecting, selected, onSelect, onDelete }: Props) {
  const qc = useQueryClient();
  const dragging = useRef<number | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const [pending, setPending] = useState<Set<number>>(new Set());
  const labelOf = (key: string) => data.columns.find((c) => c.key === key)?.label ?? key;

  const move = async (t: TicketItem, to: string) => {
    if (t.status === to || pending.has(t.id)) return;
    const before = qc.getQueryData<BoardResponse>(queryKey);
    qc.setQueryData(queryKey, applyMove(data, t.id, to));
    setPending((s) => new Set(s).add(t.id));
    try {
      await api.post(`tickets/${t.id}/status/`, { status: to });
      toast(`${t.key}: status ${t.status_label} → ${labelOf(to)}.`, 'success');
      qc.invalidateQueries({ queryKey: ['tickets'] });
      qc.invalidateQueries({ queryKey: ['bootstrap'] });
      qc.invalidateQueries({ queryKey: ['product-nav'] });
    } catch (e) {
      qc.setQueryData(queryKey, before);
      toast(e instanceof Error ? e.message : 'Cannot move ticket', 'error');
    } finally {
      setPending((s) => {
        const next = new Set(s);
        next.delete(t.id);
        return next;
      });
    }
  };

  const drop = (to: string) => {
    setOver(null);
    const id = dragging.current;
    dragging.current = null;
    const t = data.columns.flatMap((c) => c.tickets).find((x) => x.id === id);
    if (t) void move(t, to);
  };

  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {data.columns.map((col) => (
        <section
          key={col.key}
          role="region"
          aria-label={col.label}
          data-status={col.key}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(col.key);
          }}
          onDragLeave={() => setOver((o) => (o === col.key ? null : o))}
          onDrop={(e) => {
            e.preventDefault();
            drop(col.key);
          }}
          className={cn('flex w-72 shrink-0 flex-col gap-2 rounded-xl border bg-secondary/50 p-2', over === col.key && 'ring-2 ring-primary/40')}
        >
          <header className="flex items-center justify-between px-1 py-1 text-sm font-medium">
            <span>{col.label}</span>
            <span className="rounded-full bg-card px-2 text-xs text-muted-foreground">{col.tickets.length}</span>
          </header>
          {col.tickets.map((t) => (
            <article
              key={t.id}
              data-ticket-card
              data-ticket-id={t.id}
              data-url={t.url}
              draggable
              onDragStart={(e) => {
                dragging.current = t.id;
                e.dataTransfer?.setData('text/plain', String(t.id));
                if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
              }}
              className={cn('cursor-grab space-y-2 rounded-lg border bg-card p-3 text-sm shadow-sm', t.is_overdue && 'border-destructive/40', pending.has(t.id) && 'opacity-60')}
            >
              <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span className="flex min-w-0 items-center gap-1.5">
                  {selecting && (
                    <Checkbox aria-label={`Select ticket ${t.key}`} checked={selected.has(t.id)} onCheckedChange={(c) => onSelect(t.id, c === true)} />
                  )}
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
                      {data.columns.filter((c) => c.key !== t.status).map((c) => (
                        <DropdownMenuItem key={c.key} onSelect={() => void move(t, c.key)}>{c.label}</DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  {t.can_delete && (
                    <Button variant="ghost" size="icon-sm" aria-label={`Delete ${t.key}`} onClick={() => onDelete(t)}><Trash2 /></Button>
                  )}
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
            </article>
          ))}
          {col.tickets.length === 0 && <p className="rounded-lg border border-dashed py-6 text-center text-xs text-muted-foreground">No tickets</p>}
        </section>
      ))}
    </div>
  );
}
