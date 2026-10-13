import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { TicketFilters, TicketMeta } from './types';

const SORTS: [string, string][] = [
  ['-created', 'Newest first'],
  ['created', 'Oldest first'],
  ['-updated', 'Recently updated'],
  ['-priority', 'Priority (high first)'],
  ['priority', 'Priority (low first)'],
  ['title', 'Title (A-Z)'],
];

type Props = {
  filters: TicketFilters;
  onChange(next: TicketFilters): void;
  meta?: TicketMeta;
  showStatus: boolean;
  showProduct: boolean;
};

function Choice({ label, value, allLabel, options, onChange }: {
  label: string;
  value: string | undefined;
  allLabel?: string;
  options: [string, string][];
  onChange(v: string | undefined): void;
}) {
  return (
    <Select value={value ?? (allLabel ? 'all' : '')} onValueChange={(v) => onChange(v === 'all' ? undefined : v)}>
      <SelectTrigger aria-label={label} className="w-44 max-sm:w-full">
        <SelectValue placeholder={allLabel} />
      </SelectTrigger>
      <SelectContent>
        {allLabel && <SelectItem value="all">{allLabel}</SelectItem>}
        {options.map(([v, l]) => (
          <SelectItem key={v} value={v}>{l}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function FilterBar({ filters, onChange, meta, showStatus, showProduct }: Props) {
  const [q, setQ] = useState(filters.q ?? '');
  // Keep the box in step when the URL changes (Clear, Back).
  useEffect(() => setQ(filters.q ?? ''), [filters.q]);
  // Search as you type, but only once typing pauses.
  useEffect(() => {
    if (q === (filters.q ?? '')) return;
    const t = setTimeout(() => onChange({ ...filters, q: q || undefined, page: undefined }), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const set = (key: keyof TicketFilters) => (v: string | undefined) => onChange({ ...filters, [key]: v, page: undefined });
  const pairs = <T,>(rows: T[], id: (r: T) => string, name: (r: T) => string): [string, string][] => rows.map((r) => [id(r), name(r)]);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="w-full max-w-60 max-sm:max-w-none">
        <Input
          type="search"
          aria-label="Search tickets"
          placeholder="Search tickets…"
          leftIcon={<Search />}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      {showStatus && <Choice label="Filter by status" value={filters.status} allLabel="All statuses" options={meta?.statuses ?? []} onChange={set('status')} />}
      <Choice label="Filter by type" value={filters.type} allLabel="All types" options={meta?.types ?? []} onChange={set('type')} />
      <Choice label="Filter by priority" value={filters.priority} allLabel="All priorities" options={[...(meta?.priorities ?? [])].reverse()} onChange={set('priority')} />
      {showProduct && (
        <Choice label="Filter by product" value={filters.product} allLabel="All products" options={pairs(meta?.products ?? [], (p) => String(p.id), (p) => p.name)} onChange={set('product')} />
      )}
      <Choice
        label="Filter by assignee"
        value={filters.assigned}
        allLabel="All assignees"
        options={[['me', 'Assigned to me'], ['unassigned', 'Unassigned'], ...pairs(meta?.members ?? [], (m) => String(m.id), (m) => m.name)]}
        onChange={set('assigned')}
      />
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={filters.overdue === '1'} onCheckedChange={(c) => set('overdue')(c === true ? '1' : undefined)} />
        Overdue only
      </label>
      <span className="ml-auto flex items-center gap-2 max-sm:ml-0 max-sm:w-full">
        <Choice label="Sort tickets" value={filters.sort ?? '-created'} options={SORTS} onChange={set('sort')} />
        <Button variant="ghost" size="sm" onClick={() => onChange({})}>Clear</Button>
      </span>
    </div>
  );
}
