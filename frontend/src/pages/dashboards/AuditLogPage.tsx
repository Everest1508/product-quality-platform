import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Pagination } from '@/components/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Actor, EventBadge } from './EventBadge';
import { useAudit } from './useDashboards';

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
        <h1 className="text-xl font-semibold">Audit Log{d && <span className="ml-2 text-sm font-normal text-muted-foreground">{d.page.count} event{d.page.count === 1 ? '' : 's'}</span>}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Chronological system activity feed, security actions, and team audit logs.</p>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-full max-w-64 max-sm:max-w-none"><Input type="search" aria-label="Search event titles" placeholder="Search event titles…" leftIcon={<Search />} value={text} onChange={(e) => setText(e.target.value)} /></div>
        <Select value={params.get('type') ?? 'all'} onValueChange={(v) => set('type', v === 'all' ? null : v)}>
          <SelectTrigger aria-label="Filter by type" className="w-48"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All event types</SelectItem>{d?.event_types.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={params.get('actor') ?? 'all'} onValueChange={(v) => set('actor', v === 'all' ? null : v)}>
          <SelectTrigger aria-label="Filter by member" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">Any member</SelectItem>{d?.members.map((m) => <SelectItem key={m.id} value={String(m.id)}>{m.name}</SelectItem>)}</SelectContent>
        </Select>
        <label className="grid gap-1 text-xs">From<Input type="date" className="w-36" value={params.get('from') ?? ''} onChange={(e) => set('from', e.target.value || null)} /></label>
        <label className="grid gap-1 text-xs">To<Input type="date" className="w-36" value={params.get('to') ?? ''} onChange={(e) => set('to', e.target.value || null)} /></label>
        {filtered && <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setParams({})}>Clear</Button>}
      </div>

      {q.isError && !d ? (
        <Card className="p-6 text-center"><p className="text-sm">Couldn’t load the audit log.</p><Button className="mt-3" size="sm" variant="outline" onClick={() => q.refetch()}>Try again</Button></Card>
      ) : !d ? (
        <Card className="space-y-3 p-4" data-testid="audit-loading">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</Card>
      ) : d.items.length === 0 ? (
        <Card className="p-10 text-center"><h3 className="font-medium">No activity logged</h3><p className="mt-1 text-sm text-muted-foreground">No audit events match the current filter criteria.</p></Card>
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="p-3 font-medium">Timestamp</th><th className="p-3 font-medium">Event type</th><th className="p-3 font-medium">Details &amp; description</th><th className="p-3 font-medium">Actor</th></tr></thead>
            <tbody>
              {d.items.map((e) => (
                <tr key={e.id} className="border-b align-top last:border-0">
                  <td className="whitespace-nowrap p-3 text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</td>
                  <td className="p-3"><EventBadge e={e} /></td>
                  <td className="min-w-64 p-3"><div className="font-medium">{e.url ? <a href={e.url} className="hover:underline">{e.title}</a> : e.title}</div>{e.description && <div className="text-xs text-muted-foreground">{e.description}</div>}</td>
                  <td className="p-3"><Actor a={e.actor} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.page.num_pages > 1 && <div className="flex justify-end border-t p-3"><Pagination page={d.page.number} pageCount={d.page.num_pages} onPageChange={(p) => set('page', p === 1 ? null : String(p))} /></div>}
        </Card>
      )}
    </div>
  );
}
