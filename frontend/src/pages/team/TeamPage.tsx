import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
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

const SORTS: [string, string][] = [['-role', 'Role (high first)'], ['role', 'Role (low first)'], ['name', 'Name A-Z'], ['-joined', 'Newest first'], ['joined', 'Oldest first']];
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
        {d?.can_manage && <Button size="sm" onClick={() => setAdding(true)}><Plus /> Add member</Button>}
      </div>

      {d && (
        <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
          <span>{d.counts.total} people</span><span>·</span><span>{d.counts.owner_admin} owners and admins</span><span>·</span><span>{d.counts.developer} developers</span><span>·</span><span>{d.counts.support_viewer} support and viewers</span>
        </div>
      )}

      <div className="flex w-fit flex-wrap rounded-lg bg-secondary p-0.5">
        {[['', 'All'], ...(d?.roles ?? [])].map(([v, l]) => (
          <button key={l} type="button" aria-pressed={role === v} onClick={() => set('role', v || null)} className={cn('rounded-md px-3 py-1 text-sm', role === v ? 'bg-card font-medium shadow-sm' : 'text-muted-foreground hover:text-foreground')}>{l}</button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-full max-w-64 max-sm:max-w-none"><Input type="search" aria-label="Search members" placeholder="Search members…" leftIcon={<Search />} value={text} onChange={(e) => setText(e.target.value)} /></div>
        <Select value={params.get('sort') ?? '-role'} onValueChange={(v) => set('sort', v === '-role' ? null : v)}>
          <SelectTrigger aria-label="Sort" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>{SORTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      {q.isError && !d ? (
        <Card className="p-6 text-center"><p className="text-sm">Couldn’t load the team.</p><Button className="mt-3" size="sm" variant="outline" onClick={() => q.refetch()}>Try again</Button></Card>
      ) : !d ? (
        <Card className="space-y-3 p-4" data-testid="team-loading">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 w-full" />)}</Card>
      ) : d.items.length === 0 ? (
        <Card className="p-10 text-center"><h3 className="font-medium">No members found</h3><p className="mt-1 text-sm text-muted-foreground">Try a different search term or role.</p></Card>
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="p-3 font-medium">User</th><th className="p-3 font-medium">Role</th><th className="p-3 font-medium">Joined</th><th className="p-3 text-right font-medium">Actions</th></tr></thead>
            <tbody>
              {d.items.map((m) => (
                <tr key={m.id} className="border-b last:border-0">
                  <td className="p-3">
                    <div className="flex items-center gap-3">
                      <span className="grid size-8 place-items-center rounded-full bg-accent text-xs font-medium text-accent-foreground">{m.user.initial}</span>
                      <div className="min-w-0">
                        <div className="font-medium">{m.user.name}{m.is_you && <span className="ml-1 text-xs text-muted-foreground">(you)</span>}</div>
                        <div className="text-xs text-muted-foreground">{m.user.email}{m.user.discord_id && ` · @${m.user.discord_id}`}</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-3"><Badge variant={TONE[m.role] ?? 'default'}>{m.role_label}</Badge>{m.is_leave_approver && <Badge variant="outline" className="ml-1">Leave approver</Badge>}</td>
                  <td className="whitespace-nowrap p-3 text-muted-foreground">{shortDate(m.joined)}</td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1.5">
                      {m.can_edit && <Button size="sm" variant="outline" onClick={() => setEditing(m)}>Edit</Button>}
                      {m.can_remove && <Button size="sm" variant="destructive" onClick={() => setRemoving(m)}>Remove</Button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.page.num_pages > 1 && <div className="flex justify-end border-t p-3"><Pagination page={d.page.number} pageCount={d.page.num_pages} onPageChange={(p) => set('page', p === 1 ? null : String(p))} /></div>}
        </Card>
      )}

      {d && adding && <MemberDialog open onOpenChange={setAdding} roles={d.assignable_roles} />}
      {d && editing && <MemberDialog open onOpenChange={(o) => !o && setEditing(null)} member={editing} roles={d.assignable_roles} />}
      <AlertDialog open={removing !== null} onOpenChange={(o) => !o && setRemoving(null)} destructive title={`Remove ${removing?.user.username} from the team?`} description="They lose access to this workspace immediately." confirmLabel="Remove" onConfirm={() => removing && remove(removing.id)} />
    </div>
  );
}
