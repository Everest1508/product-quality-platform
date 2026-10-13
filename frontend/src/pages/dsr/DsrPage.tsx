import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CopyIcon, EditIcon, PlusIcon, RefreshIcon, SearchIcon, TrashIcon } from '@/components/ui/icons';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { Segmented } from '@/components/ui/segmented';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from '@/lib/toast';
import { EntryDialog } from './Entries';
import { useDsrActions, useDsrLog } from './useDsr';
import type { LogRow } from './types';

const RANGES: [string, string][] = [['today', 'Today'], ['yesterday', 'Yesterday'], ['7d', 'Last 7 days'], ['30d', 'Last 30 days']];
const STATUS: Record<string, 'success' | 'info' | 'danger'> = { completed: 'success', in_progress: 'info', blocked: 'danger' };

// Everything that was submitted, today and before, as one list: read it, search it, fix an entry in place.
export function DsrPage() {
  const [params, setParams] = useSearchParams();
  const range = params.get('range') ?? '7d';
  const user = params.get('user_id') ?? '';
  const [text, setText] = useState(params.get('q') ?? '');
  const q = params.get('q') ?? '';
  const query = useDsrLog({ range, user, q });
  const act = useDsrActions(user);
  const log = query.data;
  const [dialog, setDialog] = useState<{ entry?: LogRow } | null>(null);
  const [confirm, setConfirm] = useState<LogRow | null>(null);
  useEffect(() => {
    document.title = 'DSR — PQ Platform';
  }, []);
  // Search waits for a pause so the table does not reload on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => text !== q && set({ q: text || null }), 350);
    return () => clearTimeout(t);
  });

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k));
    setParams(next, { replace: true });
  };

  if (query.isError && !log) return <Card><ErrorState title="Couldn’t load the DSR."><Button size="sm" variant="outline" onClick={() => query.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>;
  if (!log) return <div className="space-y-3" data-testid="dsr-loading"><Skeleton className="h-10 w-72" /><Skeleton className="h-64 w-full" /></div>;
  const everyone = log.scope === 'all';
  const canLog = log.can_log && (log.target.is_me || log.is_privileged);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Daily Status Report"
        sub={everyone ? 'Everyone’s submitted work.' : `${log.target.is_me ? 'Your' : `${log.target.name}’s`} submitted work.`}
        actions={<>
          <Button variant="outline" onClick={() => navigator.clipboard.writeText(log.summary_text).then(() => toast('DSR copied to the clipboard.', 'success'))}><CopyIcon />Copy summary</Button>
          {canLog && <Button onClick={() => setDialog({})}><PlusIcon />Log work</Button>}
        </>}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Segmented value={RANGES.some(([v]) => v === log.range) ? log.range : ''} onValueChange={(v) => set({ range: v === '7d' ? null : v })} options={RANGES.map(([value, label]) => ({ value, label }))} />
        {log.is_privileged && (
          <Select value={user || 'me'} onValueChange={(v) => set({ user_id: v === 'me' ? null : v })}>
            <SelectTrigger aria-label="Whose work" className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="me">Me</SelectItem>
              <SelectItem value="all">Everyone</SelectItem>
              {log.members.filter((m) => m.id !== log.target.id || !log.target.is_me).map((m) => <SelectItem key={m.id} value={String(m.id)}>{m.name}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
        <div className="w-full max-w-64 max-sm:max-w-none"><Input type="search" aria-label="Search entries" placeholder="Search entries…" leftIcon={<SearchIcon />} value={text} onChange={(e) => setText(e.target.value)} /></div>
        <p className="ml-auto text-sm text-muted-foreground"><b className="text-foreground">{log.total}</b> · {log.count} {log.count === 1 ? 'entry' : 'entries'} · {log.completed} completed</p>
      </div>

      {!log.can_log && log.range === 'today' && <Alert variant="warning">{log.locked_reason}</Alert>}

      <Card className="overflow-hidden p-0 [&>div]:max-h-[70vh]">
        {log.rows.length === 0 ? (
          <EmptyState className="rounded-none border-0" title="Nothing submitted" description={q ? 'No entries match your search.' : 'Nothing was logged in this period.'} action={canLog ? <Button size="sm" onClick={() => setDialog({})}><PlusIcon />Log work</Button> : undefined} />
        ) : (
          <Table className="border-collapse [&_td]:border [&_th]:border">
            <TableHeader className="sticky top-0 z-10 bg-secondary">
              <TableRow className="bg-secondary hover:bg-secondary">
                <TableHead className="w-28 text-center">Date</TableHead>
                {everyone && <TableHead className="w-36">Employee</TableHead>}
                <TableHead className="min-w-64">Task</TableHead>
                <TableHead className="w-36">Project</TableHead>
                <TableHead className="w-40">Category</TableHead>
                <TableHead className="w-24 text-center">Time</TableHead>
                <TableHead className="w-32 text-center">Status</TableHead>
                <TableHead className="w-24 text-center">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {log.days.flatMap((d) => {
                const rows = log.rows.filter((r) => r.date === d.date);
                return rows.map((r, i) => (
                  <TableRow key={r.id} className="align-middle">
                    {i === 0 && (
                      <TableCell rowSpan={rows.length} className="bg-muted/40 text-center align-middle">
                        <div className="font-semibold">{d.date === log.today ? 'Today' : d.label}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{d.hours} · {d.count} {d.count === 1 ? 'entry' : 'entries'}</div>
                      </TableCell>
                    )}
                    {everyone && <TableCell className="whitespace-nowrap text-sm font-medium">{r.person.name}</TableCell>}
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                        {r.ticket ? <Link to={r.ticket.url} className="hover:underline">{r.task_name}</Link> : r.task_name}
                        {r.auto && <Badge variant="info" title="Added automatically when the ticket was resolved">Auto</Badge>}
                        {r.source && <Badge variant="outline" title={`Submitted through the DSR MCP from ${r.source}`}>via MCP</Badge>}
                      </div>
                      {r.notes && <p className="mt-0.5 text-xs text-muted-foreground">{r.notes}</p>}
                    </TableCell>
                    <TableCell className="text-sm">{r.product?.name ?? <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className="text-sm">{r.category_label}</TableCell>
                    <TableCell className="whitespace-nowrap text-center font-semibold tabular-nums">{r.hours}</TableCell>
                    <TableCell className="text-center"><Badge variant={STATUS[r.status] ?? 'default'}>{r.status_label}</Badge></TableCell>
                    <TableCell className="whitespace-nowrap text-center">
                      {r.editable ? (
                        <>
                          <Button variant="ghost" size="icon-sm" aria-label={`Edit ${r.task_name}`} onClick={() => setDialog({ entry: r })}><EditIcon /></Button>
                          <Button variant="ghost" size="icon-sm" aria-label={`Delete ${r.task_name}`} onClick={() => setConfirm(r)}><TrashIcon /></Button>
                        </>
                      ) : <span className="text-muted-foreground">—</span>}
                    </TableCell>
                  </TableRow>
                ));
              })}
            </TableBody>
          </Table>
        )}
      </Card>
      {log.truncated && <p className="text-xs text-muted-foreground">Showing the newest 500 entries. Narrow the range to see the rest.</p>}

      {dialog && <EntryDialog log={log} act={act} entry={dialog.entry} open onOpenChange={(o) => !o && setDialog(null)} />}
      <AlertDialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)} destructive title="Delete this entry?" description="This cannot be undone." confirmLabel="Delete" onConfirm={() => confirm && act.remove(confirm.id)} />
    </div>
  );
}
