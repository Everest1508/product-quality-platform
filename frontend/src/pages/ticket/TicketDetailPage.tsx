import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Eye, Pencil, Trash2 } from 'lucide-react';
import { ApiError } from '@/lib/api';
import { ago } from '@/lib/time';
import { usePresence } from '@/lib/usePresence';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { isTypingTarget } from '@/shell/keys';
import { AssigneePicker } from './AssigneePicker';
import { CommentList } from './CommentList';
import { DeadlineField } from './DeadlineField';
import { MentionTextarea } from './MentionTextarea';
import { useTicketActions, useTicketDetail } from './useTicket';
import type { TicketDetail } from './types';
import { Breadcrumb } from '@/components/ui/breadcrumb';

export const ASSIGN_DEBOUNCE_MS = 600;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 border-t pt-3 first:border-t-0 first:pt-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}

function Detail({ data, ticketId }: { data: TicketDetail; ticketId: number }) {
  const t = data.ticket;
  const act = useTicketActions(ticketId);
  const navigate = useNavigate();
  const { others } = usePresence();
  const boardUrl = t.product ? `/products/${t.product.id}/tickets/` : '/tickets/';
  const editUrl = `/tickets/${ticketId}/edit/`;

  useEffect(() => {
    document.title = `${t.key} ${t.title} — PQ Platform`;
  }, [t.key, t.title]);

  // `e` edits the ticket, like the classic page; never while typing or inside a menu or dialog.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'e' || e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return;
      e.preventDefault();
      navigate(editUrl);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [navigate, editUrl]);

  // Assignees save themselves a moment after the last change, so ticking three people sends one request.
  const serverIds = t.assignees.map((a) => a.id);
  const serverKey = serverIds.join(',');
  const [ids, setIds] = useState<number[]>(serverIds);
  const [saving, setSaving] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => setIds(serverIds), [serverKey]); // eslint-disable-line react-hooks/exhaustive-deps
  // The change waiting for its timer; leaving the page sends it instead of dropping it.
  const pending = useRef<number[] | null>(null);
  const assignNow = useRef(act.assign);
  assignNow.current = act.assign;
  useEffect(
    () => () => {
      clearTimeout(timer.current);
      if (pending.current) void assignNow.current(pending.current);
    },
    [],
  );
  const changeAssignees = (next: number[]) => {
    setIds(next);
    setSaving(true);
    pending.current = next;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      pending.current = null;
      await act.assign(next);
      setSaving(false);
    }, ASSIGN_DEBOUNCE_MS);
  };

  const [draft, setDraft] = useState('');
  const posting = useRef(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const body = draft.trim();
    if (!body || posting.current) return;
    posting.current = true;
    try {
      if (await act.addComment(body)) setDraft('');
    } finally {
      posting.current = false;
    }
  };

  const [confirmDelete, setConfirmDelete] = useState(false);
  const viewers = others.filter((u) => u.ticket_id === ticketId).map((u) => u.name);

  return (
    <div className="space-y-4">
      <Breadcrumb items={[{ label: 'Tickets', href: '/tickets/' }, ...(t.product ? [{ label: t.product.name, href: `/products/${t.product.id}/` }] : []), { label: t.key }]} />

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="break-words text-xl font-semibold">
            {t.key} <span className="ml-1 text-base font-normal text-muted-foreground">{t.title}</span>
          </h1>
          <p aria-live="polite" className="mt-1 min-h-5 text-xs text-muted-foreground">
            {viewers.length > 0 && (
              <span className="inline-flex items-center gap-1"><Eye className="size-3.5" /> {viewers.join(', ')} also viewing</span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild variant="outline" size="sm"><Link to={boardUrl}>← {t.product ? `${t.product.name} tickets` : 'Tickets'}</Link></Button>
          <Button asChild variant="outline" size="sm"><Link to={editUrl}><Pencil /> Edit Ticket</Link></Button>
          {t.can_delete && (
            <Button variant="destructive" size="sm" aria-label="Delete ticket" onClick={() => setConfirmDelete(true)}><Trash2 /> Delete</Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <Card className="p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-2">
                <Badge variant="outline">{t.type_label}</Badge>
                {t.product && <span className="text-muted-foreground">{t.product.name}</span>}
              </span>
              <span className="text-xs text-muted-foreground" title={new Date(t.created_at).toLocaleString()}>Created {ago(t.created_at)}</span>
            </div>
            {t.description && <div className="whitespace-pre-wrap break-words text-sm">{t.description}</div>}
          </Card>

          {t.linked_error && (
            <Card className="p-5">
              <div className="mb-2 text-sm font-medium">Linked Error</div>
              <a href={t.linked_error.url} className="break-words text-sm text-primary hover:underline">{t.linked_error.title}</a>
            </Card>
          )}

          <Card className="p-5">
            <div className="mb-3 text-sm font-medium">
              Comments <span className="text-muted-foreground">({data.comments.length})</span>
            </div>
            <CommentList comments={data.comments} people={data.mention_candidates} />
            <form onSubmit={submit} className="mt-4 space-y-2 border-t pt-4">
              <MentionTextarea
                aria-label="Comment"
                value={draft}
                onChange={setDraft}
                people={data.mention_candidates}
                rows={3}
                placeholder="Add a comment… type @ to mention someone"
              />
              <div className="text-right">
                <Button type="submit" size="sm" loading={act.busy === 'comment'}>Comment</Button>
              </div>
            </form>
          </Card>
        </div>

        <Card className="h-fit space-y-3 p-5">
          <div className="text-sm font-medium">Details</div>
          <Row label="Status">
            <Select value={t.status} onValueChange={(v) => void act.setStatus(v)} disabled={act.busy === 'status'}>
              <SelectTrigger aria-label="Status"><SelectValue /></SelectTrigger>
              <SelectContent>{data.statuses.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
            </Select>
          </Row>
          <Row label="Priority">
            <Select value={t.priority} onValueChange={(v) => void act.setPriority(v)} disabled={act.busy === 'priority'}>
              <SelectTrigger aria-label="Priority"><SelectValue /></SelectTrigger>
              <SelectContent>{data.priorities.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
            </Select>
          </Row>
          <Row label="Assignee">
            <AssigneePicker people={data.members} value={ids} onChange={changeAssignees} />
            {saving && <span className="text-xs text-muted-foreground">Saving…</span>}
          </Row>
          <Row label="Notifications">
            <Button
              variant="outline"
              size="sm"
              aria-pressed={data.following}
              loading={act.busy === 'follow'}
              onClick={() => void act.toggleFollow()}
              title={data.following ? 'Stop getting comment and status notices' : 'Get comment and status notices without being assigned'}
            >
              {data.following ? 'Following' : 'Follow'}
              {data.watcher_count > 0 && ` · ${data.watcher_count}`}
            </Button>
          </Row>
          <Row label="Deadline">
            <DeadlineField value={t.deadline_local} overdue={t.is_overdue} disabled={act.busy === 'deadline'} onChange={(v) => void act.setDeadline(v)} />
          </Row>
          <Row label="Source"><span className="text-sm">{t.source_label}</span></Row>
          <Row label="Updated"><span className="text-sm" title={new Date(t.updated_at).toLocaleString()}>{ago(t.updated_at)}</span></Row>
        </Card>
      </div>

      <AlertDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        destructive
        title={`Delete ticket ${t.key}?`}
        description="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={async () => {
          if (await act.remove()) navigate(boardUrl);
        }}
      />
    </div>
  );
}

export function TicketDetailPage() {
  const ticketId = Number(useParams().id);
  const q = useTicketDetail(ticketId);

  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <Card className="p-8 text-center">
        <p className="text-sm">{missing ? 'Ticket not found.' : 'Couldn’t load this ticket.'}</p>
        {missing ? (
          <Link to="/tickets/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to tickets</Link>
        ) : (
          <Button className="mt-3" size="sm" variant="outline" onClick={() => q.refetch()}>Try again</Button>
        )}
      </Card>
    );
  }
  if (!q.data) {
    return (
      <div className="space-y-3" data-testid="ticket-loading">
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  return <Detail data={q.data} ticketId={ticketId} />;
}
