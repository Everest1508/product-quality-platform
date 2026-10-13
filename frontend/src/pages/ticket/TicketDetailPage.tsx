import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeftIcon, BellIcon, EditIcon, EyeIcon, RefreshIcon, SendIcon, TrashIcon } from '@/components/ui/icons';
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
import { Timeline } from './Timeline';
import { DeadlineField } from './DeadlineField';
import { MentionTextarea } from './MentionTextarea';
import { useTicketActions, useTicketDetail } from './useTicket';
import type { TicketDetail } from './types';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { PageHeader } from '@/components/ui/page-header';

export const ASSIGN_DEBOUNCE_MS = 600;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid content-start gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
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
    <div className="mx-auto max-w-4xl space-y-5">
      <Breadcrumb items={[{ label: 'Tickets', href: '/tickets/' }, ...(t.product ? [{ label: t.product.name, href: `/products/${t.product.id}/` }] : []), { label: t.key }]} />

      <PageHeader
        title={<><span className="text-muted-foreground">{t.key}</span> {t.title}</>}
        sub={<>
          <Badge variant="outline">{t.type_label}</Badge> <span className="ml-1">Created {ago(t.created_at)} · updated {ago(t.updated_at)} · {t.source_label}</span>
          {viewers.length > 0 && <span aria-live="polite" className="ml-2 inline-flex items-center gap-1"><EyeIcon className="size-3.5" /> {viewers.join(', ')} also viewing</span>}
        </>}
        actions={<>
          <Button asChild variant="outline"><Link to={editUrl}><EditIcon /> Edit Ticket</Link></Button>
          {t.can_delete && <Button variant="outline" className="text-destructive" aria-label="Delete ticket" onClick={() => setConfirmDelete(true)}><TrashIcon /> Delete</Button>}
        </>}
      />

      <Card className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
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
        <Row label="Deadline">
          <DeadlineField value={t.deadline_local} overdue={t.is_overdue} disabled={act.busy === 'deadline'} onChange={(v) => void act.setDeadline(v)} />
        </Row>
      </Card>

      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">Description</h2>
        <Button
          variant="outline"
          size="sm"
          aria-pressed={data.following}
          loading={act.busy === 'follow'}
          onClick={() => void act.toggleFollow()}
          title={data.following ? 'Stop getting comment and status notices' : 'Get comment and status notices without being assigned'}
        ><BellIcon />
          {data.following ? 'Following' : 'Follow'}
          {data.watcher_count > 0 && ` · ${data.watcher_count}`}
        </Button>
      </div>
      <Card className="p-5">
        {t.description ? <div className="whitespace-pre-wrap break-words text-sm">{t.description}</div> : <p className="text-sm text-muted-foreground">No description.</p>}
        {t.linked_error && (
          <p className="mt-4 border-t pt-3 text-sm"><span className="text-muted-foreground">Linked error: </span><a href={t.linked_error.url} className="break-words text-primary hover:underline">{t.linked_error.title}</a></p>
        )}
      </Card>

      <h2 className="text-sm font-semibold">Activity <span className="font-normal text-muted-foreground">({data.comments.length} comment{data.comments.length === 1 ? '' : 's'})</span></h2>
      <Card className="p-5">
        <Timeline events={data.events ?? []} comments={data.comments} people={data.mention_candidates} />
        <form onSubmit={submit} className="mt-4 space-y-2 border-t pt-4 first:mt-0 first:border-0 first:pt-0">
          <MentionTextarea
            aria-label="Comment"
            value={draft}
            onChange={setDraft}
            people={data.mention_candidates}
            rows={3}
            placeholder="Add a comment… type @ to mention someone"
          />
          <div className="text-right">
            <Button type="submit" loading={act.busy === 'comment'}><SendIcon />Comment</Button>
          </div>
        </form>
      </Card>

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
          <Button asChild variant="link" className="mt-3"><Link to="/tickets/"><ArrowLeftIcon /> Back to tickets</Link></Button>
        ) : (
          <Button className="mt-3" size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button>
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
