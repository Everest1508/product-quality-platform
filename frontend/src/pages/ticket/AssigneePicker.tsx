import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { Person } from './types';

type Props = { people: Person[]; value: number[]; onChange(ids: number[]): void; disabled?: boolean };

const SEARCH_AFTER = 8;

// Pick several people. Every toggle reports the whole new list, so the caller can save as it goes.
export function AssigneePicker({ people, value, onChange, disabled }: Props) {
  const [q, setQ] = useState('');
  const chosen = people.filter((p) => value.includes(p.id));
  const shown = people.filter((p) => !q || p.name.toLowerCase().includes(q.toLowerCase()) || p.username.toLowerCase().includes(q.toLowerCase()));
  const toggle = (id: number, on: boolean) => onChange(on ? [...value, id] : value.filter((v) => v !== id));

  return (
    <Popover onOpenChange={(o) => !o && setQ('')}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Assignees"
          disabled={disabled}
          className="flex min-h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-2.5 py-1.5 text-left text-sm outline-none hover:border-muted-foreground/40 focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
        >
          <span className="flex min-w-0 flex-wrap gap-1">
            {chosen.length === 0 && <span className="text-muted-foreground">Unassigned</span>}
            {chosen.map((p) => (
              <span key={p.id} className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground">
                {p.name}
              </span>
            ))}
          </span>
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-2">
        {people.length > SEARCH_AFTER && (
          <Input type="search" aria-label="Search people" placeholder="Search people…" value={q} onChange={(e) => setQ(e.target.value)} className="mb-2" />
        )}
        <ul className="max-h-60 overflow-y-auto">
          {shown.map((p) => (
            <li key={p.id}>
              <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-secondary">
                <Checkbox aria-label={p.name} checked={value.includes(p.id)} onCheckedChange={(c) => toggle(p.id, c === true)} />
                {p.name}
                <span className="text-xs text-muted-foreground">@{p.username}</span>
              </label>
            </li>
          ))}
          {shown.length === 0 && <li className="px-2 py-3 text-center text-sm text-muted-foreground">Nobody found.</li>}
        </ul>
        <div className="mt-1 flex justify-end border-t pt-2">
          <button type="button" onClick={() => onChange([])} className="text-xs text-primary hover:underline">Clear</button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
