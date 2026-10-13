import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/lib/toast';
import { AddForm, EntryTable, Suggestions } from './Entries';
import { useDsr, useDsrActions } from './useDsr';
import { ErrorState } from '@/components/ui/error-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Alert } from '@/components/ui/alert';

const long = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });

export function DsrPage() {
  const [params, setParams] = useSearchParams();
  const date = params.get('date') ?? '';
  const userId = params.get('user_id') ?? '';
  const q = useDsr(date, userId);
  const act = useDsrActions(date, userId);
  const sheet = q.data;
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    document.title = 'DSR — PQ Platform';
  }, []);

  const go = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next);
  };

  if (q.isError && !sheet) return <Card><ErrorState title="Couldn’t load the DSR sheet."><Button size="sm" variant="outline" onClick={() => q.refetch()}>Try again</Button></ErrorState></Card>;
  if (!sheet) return <div className="space-y-3" data-testid="dsr-loading"><Skeleton className="h-10 w-72" /><Skeleton className="h-48 w-full" /></div>;
  const isToday = sheet.date === sheet.today;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Daily Status Report</h1>
          <p className="mt-1 text-sm text-muted-foreground">{sheet.target.is_me ? 'Your' : `${sheet.target.name}’s`} work for {long(sheet.date)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="icon" aria-label="Previous day" onClick={() => go({ date: sheet.prev })}><ChevronLeft /></Button>
          <Input type="date" aria-label="Day" className="w-40" max={sheet.today} value={sheet.date} onChange={(e) => e.target.value && go({ date: e.target.value })} />
          <Button variant="outline" size="icon" aria-label="Next day" disabled={isToday} onClick={() => go({ date: sheet.next })}><ChevronRight /></Button>
          <Button variant={isToday ? 'primary' : 'outline'} size="sm" onClick={() => go({ date: null })}>Today</Button>
          <Button variant="outline" size="sm" onClick={() => go({ date: sheet.yesterday })}>Yesterday</Button>
          {sheet.is_privileged && (
            <Select value={userId || String(sheet.target.id)} onValueChange={(v) => go({ user_id: v })}>
              <SelectTrigger aria-label="Whose sheet" className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent>{sheet.members.map((m) => <SelectItem key={m.id} value={String(m.id)}>{m.name}</SelectItem>)}</SelectContent>
            </Select>
          )}
        </div>
      </div>

      {!sheet.can_submit && <Alert variant="warning">{sheet.locked_reason}</Alert>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-4"><div className="text-2xl font-semibold">{sheet.total}</div><div className="text-xs text-muted-foreground">Total time</div></Card>
        <Card className="p-4"><div className="text-2xl font-semibold">{sheet.entries.length}</div><div className="text-xs text-muted-foreground">Entries</div></Card>
        <Card className="p-4"><div className="text-2xl font-semibold">{sheet.completed}</div><div className="text-xs text-muted-foreground">Completed</div></Card>
        <Card className="p-4">
          <div className="text-2xl font-semibold">{sheet.progress}%</div>
          <Progress className="mt-1" value={sheet.progress} />
          <div className="mt-1 text-xs text-muted-foreground">of an 8h day</div>
        </Card>
      </div>

      {sheet.can_submit && <Card className="p-5"><h2 className="mb-3 text-sm font-semibold">Log your work</h2><AddForm sheet={sheet} act={act} /></Card>}
      <Suggestions sheet={sheet} act={act} />

      <Card className="space-y-3 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Entries</h2>
          <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(sheet.summary_text).then(() => { setCopied(true); toast('DSR copied to the clipboard.', 'success'); setTimeout(() => setCopied(false), 2000); })}><Copy /> {copied ? 'Copied!' : 'Copy summary'}</Button>
        </div>
        <EntryTable sheet={sheet} act={act} />
      </Card>

      {sheet.is_privileged && sheet.team_overview.length > 0 && (
        <Card className="space-y-3 p-5">
          <h2 className="text-sm font-semibold">Team overview</h2>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader><TableRow><TableHead className="py-2">Member</TableHead><TableHead>Time</TableHead><TableHead className="w-40">Of 8h</TableHead><TableHead>Completed</TableHead><TableHead>Entries</TableHead></TableRow></TableHeader>
              <TableBody>
                {sheet.team_overview.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="py-2"><button type="button" className="font-medium hover:underline" onClick={() => go({ user_id: String(m.id) })}>{m.name}</button></TableCell>
                    <TableCell>{m.hours}</TableCell>
                    <TableCell><Progress value={m.progress} /></TableCell>
                    <TableCell>{m.completed}</TableCell><TableCell>{m.entries}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
}
