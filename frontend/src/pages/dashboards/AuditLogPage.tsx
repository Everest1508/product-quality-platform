import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { RefreshIcon, SearchIcon, XIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Pagination } from '@/components/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Actor, EventBadge } from './EventBadge';
import { useAudit } from './useDashboards';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { DateField } from '@/components/ui/date-field';

const KEYS = ['q', 'type', 'actor', 'from', 'to', 'page'] as const;

export function AuditLogPage() {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams([...params.entries()].filter(([k]) => (KEYS as readonly string[]).includes(k))).toString();
  const q = useAudit(query);
  const d = q.data;
  const set = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next);
  };
  const [text, setText] = useState(params.get('q') ?? '');
  const latest = useRef(params);
  latest.current = params;
  useEffect(() => setText(params.get('q') ?? ''), [params]);
  useEffect(() => {
    if (text === (latest.current.get('q') ?? '')) return;
    const t = setTimeout(() => {
      const next = new URLSearchParams(latest.current);
      if (text) next.set('q', text);
      else next.delete('q');
      next.delete('page');
      setParams(next);
    }, 400);
    return () => clearTimeout(t);
  }, [text, setParams]);
  useEffect(() => {
    document.title = 'Audit Log — PQ Platform';
  }, []);
  const filtered = KEYS.some((k) => k !== 'page' && params.get(k));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Audit Log{d && <span className="ml-2 text-sm font-normal text-muted-foreground">{d.page.count} event{d.page.count === 1 ? '' : 's'}</span>}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Chronological system activity feed, security actions, and team audit logs.</p>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-full max-w-64 max-sm:max-w-none"><Input type="search" aria-label="Search event titles" placeholder="Search event titles…" leftIcon={<SearchIcon />} value={text} onChange={(e) => setText(e.target.value)} /></div>
        <Select value={params.get('type') ?? 'all'} onValueChange={(v) => set('type', v === 'all' ? null : v)}>
          <SelectTrigger aria-label="Filter by type" className="w-48"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All event types</SelectItem>{d?.event_types.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={params.get('actor') ?? 'all'} onValueChange={(v) => set('actor', v === 'all' ? null : v)}>
          <SelectTrigger aria-label="Filter by member" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">Any member</SelectItem>{d?.members.map((m) => <SelectItem key={m.id} value={String(m.id)}>{m.name}</SelectItem>)}</SelectContent>
        </Select>
        <div className="grid gap-1 text-xs"><span>From</span><DateField aria-label="From" className="w-36" value={params.get('from') ?? ''} onChange={(v) => set('from', v || null)} /></div>
        <div className="grid gap-1 text-xs"><span>To</span><DateField aria-label="To" className="w-36" value={params.get('to') ?? ''} onChange={(v) => set('to', v || null)} /></div>
        {filtered && <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setParams({})}><XIcon />Clear</Button>}
      </div>

      {q.isError && !d ? (
        <Card><ErrorState title="Couldn’t load the audit log."><Button size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
      ) : !d ? (
        <Card className="space-y-3 p-4" data-testid="audit-loading">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</Card>
      ) : d.items.length === 0 ? (
        <EmptyState title="No activity logged" description={<>No audit events match the current filter criteria.</>} />
      ) : (
        <Card className="overflow-x-auto p-0">
          <Table>
            <TableHeader><TableRow><TableHead>Timestamp</TableHead><TableHead>Event type</TableHead><TableHead>Details &amp; description</TableHead><TableHead>Actor</TableHead></TableRow></TableHeader>
            <TableBody>
              {d.items.map((e) => (
                <TableRow key={e.id} className="align-top">
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</TableCell>
                  <TableCell><EventBadge e={e} /></TableCell>
                  <TableCell className="min-w-64"><div className="font-medium">{e.url ? <a href={e.url} className="hover:underline">{e.title}</a> : e.title}</div>{e.description && <div className="text-xs text-muted-foreground">{e.description}</div>}</TableCell>
                  <TableCell><Actor a={e.actor} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {d.page.num_pages > 1 && <div className="flex justify-end border-t p-3"><Pagination page={d.page.number} pageCount={d.page.num_pages} onPageChange={(p) => set('page', p === 1 ? null : String(p))} /></div>}
        </Card>
      )}
    </div>
  );
}
