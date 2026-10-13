import { TrashIcon } from '@/components/ui/icons';
import { go } from '@/lib/go';
import { ago } from '@/lib/time';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import type { TicketItem } from './types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const statusVariant: Record<string, 'default' | 'info' | 'warning' | 'primary' | 'success' | 'outline'> = {
  open: 'default', assigned: 'info', in_progress: 'warning', testing: 'primary', resolved: 'success', closed: 'outline',
};
export const priorityDot: Record<string, string> = {
  critical: 'bg-destructive', high: 'bg-warning', medium: 'bg-info', low: 'bg-muted-foreground/50',
};

export function Assignees({ people }: { people: TicketItem['assignees'] }) {
  if (!people.length) return <span className="text-xs text-muted-foreground">Unassigned</span>;
  return (
    <span className="flex items-center">
      {people.slice(0, 3).map((a) => (
        <span key={a.id} title={a.name} className="-mr-1 grid size-6 place-items-center rounded-full border-2 border-card bg-accent text-[11px] font-semibold text-accent-foreground">
          {a.initial}
        </span>
      ))}
      {people.length > 3 && <span className="ml-2 text-xs text-muted-foreground">+{people.length - 3}</span>}
    </span>
  );
}

type Props = {
  items: TicketItem[];
  selecting: boolean;
  selected: Set<number>;
  onSelect(id: number, checked: boolean): void;
  onDelete(item: TicketItem): void;
};

export function TicketTable({ items, selecting, selected, onSelect, onDelete }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="uppercase tracking-wider">
          {selecting && <TableHead className="w-10 px-3 py-2"><span className="sr-only">Select</span></TableHead>}
          <TableHead className="px-3 py-2">ID</TableHead>
          <TableHead className="px-3 py-2">Title</TableHead>
          <TableHead className="px-3 py-2">Status</TableHead>
          <TableHead className="px-3 py-2 max-md:hidden">Priority</TableHead>
          <TableHead className="px-3 py-2 max-sm:hidden">Assignees</TableHead>
          <TableHead className="px-3 py-2 max-md:hidden">Updated</TableHead>
          <TableHead className="px-3 py-2"><span className="sr-only">Actions</span></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((t) => (
          <TableRow key={t.id} data-ticket-row data-ticket-id={t.id} data-url={t.url} onClick={() => go(t.url)} className="cursor-pointer border-b last:border-b-0 hover:bg-muted">
            {selecting && (
              <TableCell className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                <Checkbox aria-label={`Select ticket ${t.key}`} checked={selected.has(t.id)} onCheckedChange={(c) => onSelect(t.id, c === true)} />
              </TableCell>
            )}
            <TableCell className="whitespace-nowrap px-3 py-3 font-semibold text-muted-foreground">{t.key}</TableCell>
            <TableCell className="max-w-md px-3 py-3">
              <a href={t.url} onClick={(e) => e.stopPropagation()} className="break-words font-semibold hover:underline">{t.title}</a>
              <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                {t.product && <b className="font-medium text-foreground">{t.product.name}</b>}
                <Badge variant="outline">{t.type_label}</Badge>
                {t.linked_error && <span>Linked to error</span>}
              </div>
            </TableCell>
            <TableCell className="px-3 py-3"><Badge variant={statusVariant[t.status] ?? 'default'}>{t.status_label}</Badge></TableCell>
            <TableCell className="px-3 py-3 max-md:hidden">
              <span className="inline-flex items-center gap-1.5 text-xs">
                <span className={cn('size-2 rounded-full', priorityDot[t.priority])} />
                {t.priority_label}
              </span>
            </TableCell>
            <TableCell className="px-3 py-3 max-sm:hidden">
              <span className="flex items-center gap-2">
                <Assignees people={t.assignees} />
                {t.is_overdue && <Badge variant="danger">Overdue</Badge>}
              </span>
            </TableCell>
            <TableCell className="whitespace-nowrap px-3 py-3 text-xs text-muted-foreground max-md:hidden" title={new Date(t.updated_at).toLocaleString()}>{ago(t.updated_at)}</TableCell>
            <TableCell className="px-3 py-3 text-right" onClick={(e) => e.stopPropagation()}>
              {t.can_delete && (
                <Button variant="ghost" size="icon-sm" aria-label={`Delete ${t.key}`} onClick={() => onDelete(t)}>
                  <TrashIcon />
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
