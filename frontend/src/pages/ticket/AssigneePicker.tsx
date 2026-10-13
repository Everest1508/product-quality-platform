import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { Person } from './types';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

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
        <Button type="button" variant="outline" aria-label="Assignees" disabled={disabled} className="h-auto min-h-9 w-full justify-between gap-2 px-2.5 py-1.5 text-left font-normal">
          <span className="flex min-w-0 flex-wrap gap-1">
            {chosen.length === 0 && <span className="text-muted-foreground">Unassigned</span>}
            {chosen.map((p) => (
              <Badge key={p.id} variant="info">{p.name}</Badge>
            ))}
          </span>
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-2">
        {people.length > SEARCH_AFTER && (
          <Input type="search" aria-label="Search people" placeholder="Search people…" value={q} onChange={(e) => setQ(e.target.value)} className="mb-2" />
        )}
        <ul className="max-h-60 overflow-y-auto">
          {shown.map((p) => (
            <li key={p.id}>
              <Label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-secondary">
                <Checkbox aria-label={p.name} checked={value.includes(p.id)} onCheckedChange={(c) => toggle(p.id, c === true)} />
                {p.name}
                <span className="text-xs text-muted-foreground">@{p.username}</span>
              </Label>
            </li>
          ))}
          {shown.length === 0 && <li className="px-2 py-3 text-center text-sm text-muted-foreground">Nobody found.</li>}
        </ul>
        <div className="mt-1 flex justify-end border-t pt-2">
          <Button type="button" variant="link" size="xs" className="h-auto p-0" onClick={() => onChange([])}>Clear</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
