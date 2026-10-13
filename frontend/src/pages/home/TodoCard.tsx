import { useState, type FormEvent } from 'react';
import { PlusIcon, XIcon } from '@/components/ui/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useTodoActions, useTodos } from './useHome';
import { Progress } from '@/components/ui/progress';
import { DateField } from '@/components/ui/date-field';
import { Checkbox } from '@/components/ui/checkbox';

const day = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
const PRIORITY: Record<number, 'danger' | 'warning' | 'default'> = { 3: 'danger', 2: 'warning', 1: 'default' };

export function TodoCard({ bare = false }: { bare?: boolean }) {
  const q = useTodos();
  const act = useTodoActions();
  const [text, setText] = useState('');
  const [priority, setPriority] = useState('2');
  const [due, setDue] = useState('');

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    if (await act.add(text.trim(), priority, due)) {
      setText('');
      setDue('');
    }
  };
  const d = q.data;
  // Inside the home tabs the list needs no card of its own.
  const Wrap = bare ? 'div' : Card;

  return (
    <Wrap className="space-y-3 p-5" id="todo-card">
      {!bare && <div className="flex items-baseline justify-between"><h2 className="font-semibold">My to-do</h2><span className="text-xs text-muted-foreground">only you can see this</span></div>}
      <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
        <Input aria-label="New task" className="min-w-40 flex-1" maxLength={300} autoComplete="off" placeholder="Add a task…" value={text} onChange={(e) => setText(e.target.value)} />
        <Select value={priority} onValueChange={setPriority}>
          <SelectTrigger aria-label="Priority" className="w-28"><SelectValue /></SelectTrigger>
          <SelectContent>{(d?.priorities ?? [['1', 'Low'], ['2', 'Medium'], ['3', 'High']]).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
        <DateField aria-label="Due date (optional)" className="w-40" value={due} onChange={setDue} />
        <Button type="submit" disabled={act.busy}><PlusIcon />Add</Button>
      </form>
      {!d ? (
        <Skeleton className="h-20 w-full" />
      ) : (
        <>
          {d.total > 0 && (
            <div className="space-y-1">
              <Progress value={(d.done / d.total) * 100} tone="success" />
              <p className="text-xs text-muted-foreground">
                {d.done} of {d.total} done
                {d.done > 0 && <> · <Button variant="link" size="xs" className="h-auto p-0" onClick={() => act.clearDone()}><XIcon />Clear done</Button></>}
              </p>
            </div>
          )}
          <ul className="space-y-1">
            {d.todos.map((t) => (
              <li key={t.id} className={cn('flex items-center gap-2 rounded-md px-1 py-1 text-sm', t.done && 'text-muted-foreground line-through')}>
                <Checkbox aria-label={t.text} checked={t.done} onCheckedChange={() => act.toggle(t.id)} />
                <span className="min-w-0 flex-1 break-words">{t.text}</span>
                <Badge variant={PRIORITY[t.priority] ?? 'default'}>{t.priority_label}</Badge>
                {t.due && <Badge variant={t.late ? 'danger' : t.today ? 'warning' : 'outline'}>{t.late ? `Overdue · ${day(t.due)}` : t.today ? 'Today' : day(t.due)}</Badge>}
                <Button variant="ghost" size="icon-sm" aria-label="Delete task" className="size-6 text-muted-foreground hover:text-destructive" onClick={() => act.remove(t.id)}><XIcon className="size-3.5" /></Button>
              </li>
            ))}
            {d.todos.length === 0 && <li className="py-2 text-sm text-muted-foreground">Nothing here yet. Add the first thing you want to get done today.</li>}
          </ul>
          {d.done > 0 && <p className="text-xs text-muted-foreground">Finished tasks are added to today’s DSR. Add the time you spent there.</p>}
        </>
      )}
    </Wrap>
  );
}
