import { LedgerSkeleton } from '@/components/skeletons';
import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { EditIcon, PlusIcon, RefreshIcon, SearchIcon, TrashIcon } from '@/components/ui/icons';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Pagination } from '@/components/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { shortDate } from '@/lib/time';
import { cn } from '@/lib/utils';
import { MemberDialog } from './MemberDialog';
import { useRemoveMember, useTeam } from './useTeam';
import type { Member } from './types';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Segmented } from '@/components/ui/segmented';
import { Avatar } from '@/components/ui/avatar';
import { Ledger, LedgerRow } from '@/components/ui/ledger';

const SORTS: [string, string][] = [['-role', 'Role (high first)'], ['role', 'Role (low first)'], ['name', 'Name A-Z'], ['-joined', 'Newest first'], ['joined', 'Oldest first']];
const ROLE_TONE: Record<string, 'info' | 'warn' | 'good' | 'off'> = { owner: 'info', admin: 'warn', developer: 'good', support: 'good', viewer: 'off' };
const TONE: Record<string, 'info' | 'warning' | 'success' | 'default'> = { owner: 'info', admin: 'warning', developer: 'success', support: 'default', viewer: 'default' };
const KEYS = ['q', 'role', 'sort', 'page'];

export function TeamPage() {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams([...params.entries()].filter(([k]) => KEYS.includes(k))).toString();
  const q = useTeam(query);
  const d = q.data;
  const remove = useRemoveMember();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Member | null>(null);
  const [removing, setRemoving] = useState<Member | null>(null);
  const role = params.get('role') ?? '';

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
    document.title = 'Team — PQ Platform';
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Team {d && <span className="ml-2 text-sm font-normal text-muted-foreground">{d.page.count} member{d.page.count === 1 ? '' : 's'}</span>}</h1>
        {d?.can_manage && <Button size="sm" onClick={() => setAdding(true)}><PlusIcon /> Add member</Button>}
      </div>

      {d && (
        <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
          <span>{d.counts.total} people</span><span>·</span><span>{d.counts.owner_admin} owners and admins</span><span>·</span><span>{d.counts.developer} developers</span><span>·</span><span>{d.counts.support_viewer} support and viewers</span>
        </div>
      )}

      <Segmented className="flex-wrap" value={role ?? ''} onValueChange={(v) => set('role', v || null)} options={[['', 'All'], ...(d?.roles ?? [])].map(([v, l]) => ({ value: v, label: l }))} />

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-full max-w-64 max-sm:max-w-none"><Input type="search" aria-label="Search members" placeholder="Search members…" leftIcon={<SearchIcon />} value={text} onChange={(e) => setText(e.target.value)} /></div>
        <Select value={params.get('sort') ?? '-role'} onValueChange={(v) => set('sort', v === '-role' ? null : v)}>
          <SelectTrigger aria-label="Sort" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>{SORTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      {q.isError && !d ? (
        <Card><ErrorState title="Couldn’t load the team."><Button size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
      ) : !d ? (
        <LedgerSkeleton testId="team-loading" />
      ) : d.items.length === 0 ? (
        <EmptyState title="No members found" description={<>Try a different search term or role.</>} />
      ) : (
        <>
          <Ledger>
            {d.items.map((m) => (
              <LedgerRow
                key={m.id}
                tone={ROLE_TONE[m.role] ?? 'off'}
                title={<>
                  <Avatar name={m.user.name} />
                  <Link to={`/team/${m.id}/`} className="truncate text-base font-semibold hover:underline">{m.user.name}{m.is_you && <span className="ml-1 text-xs font-normal text-muted-foreground">(you)</span>}</Link>
                  <Badge variant={TONE[m.role] ?? 'default'}>{m.role_label}</Badge>
                  {m.is_leave_approver && <Badge variant="outline">Leave approver</Badge>}
                </>}
                sub={`${m.user.email}${m.user.discord_id ? ` · @${m.user.discord_id}` : ''}`}
                metrics={[{ label: 'Joined', value: <span className="text-sm">{shortDate(m.joined)}</span> }]}
                actions={<>
                  {m.can_edit && <Button size="sm" variant="outline" onClick={() => setEditing(m)}><EditIcon />Edit</Button>}
                  {m.can_remove && <Button size="sm" variant="outline" className="text-destructive" onClick={() => setRemoving(m)}><TrashIcon />Remove</Button>}
                </>}
              />
            ))}
          </Ledger>
          {d.page.num_pages > 1 && <div className="flex justify-end"><Pagination page={d.page.number} pageCount={d.page.num_pages} onPageChange={(p) => set('page', p === 1 ? null : String(p))} /></div>}
        </>
      )}

      {d && adding && <MemberDialog open onOpenChange={setAdding} roles={d.assignable_roles} />}
      {d && editing && <MemberDialog open onOpenChange={(o) => !o && setEditing(null)} member={editing} roles={d.assignable_roles} />}
      <AlertDialog open={removing !== null} onOpenChange={(o) => !o && setRemoving(null)} destructive title={`Remove ${removing?.user.username} from the team?`} description="They lose access to this workspace immediately." confirmLabel="Remove" onConfirm={() => removing && remove(removing.id)} />
    </div>
  );
}
