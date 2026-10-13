import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { ago } from '@/lib/time';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { CorrectionStatus } from './parts';
import { reason, useAttQuery, useAttRefresh, useAttWrite } from './useAttendance';
import type { Correction, CorrectionForm, RecordEdit } from './types';

const when = (c: Correction['original'] | Correction['requested']) => (c.check_in || c.check_out ? `${c.check_in || 'none'} → ${c.check_out || 'none'}` : 'none');

export function CorrectionQueuePage() {
  const q = useAttQuery<{ pending: Correction[]; decided: Correction[] }>('corrections', 'attendance/corrections/');
  const write = useAttWrite();
  const [notes, setNotes] = useState<Record<number, string>>({});
  useEffect(() => {
    document.title = 'Attendance corrections — PQ Platform';
  }, []);
  const d = q.data;
  const decide = (c: Correction, action: 'approve' | 'reject') => write(() => api.post<{ message: string }>(`attendance/corrections/${c.id}/${action}/`, { note: notes[c.id] ?? '' }));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Attendance corrections {d && <span className="ml-2 text-sm font-normal text-muted-foreground">{d.pending.length} waiting</span>}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Approving changes the person’s record and is logged. Rejecting leaves it as it is.</p>
      </div>
      {!d ? <Skeleton className="h-40 w-full" data-testid="corr-loading" /> : (
        <>
          {d.pending.length === 0 && <Card className="p-10 text-center"><h3 className="font-medium">Nothing waiting</h3><p className="text-sm text-muted-foreground">Requests from your team show up here.</p></Card>}
          {d.pending.map((c) => (
            <Card key={c.id} className="space-y-3 p-5">
              <div className="flex items-center gap-3">
                <span className="grid size-8 place-items-center rounded-full bg-accent text-xs font-medium text-accent-foreground">{c.person.initial}</span>
                <div><div className="font-medium">{c.person.name}{c.is_mine && <em className="ml-1 text-xs not-italic text-muted-foreground">You</em>}</div><div className="text-xs text-muted-foreground">{c.date_label} · asked {ago(c.created_at)}</div></div>
              </div>
              <div className="grid gap-1 text-sm sm:grid-cols-2">
                <div><span className="text-xs text-muted-foreground">Check-in </span>{c.original.check_in || 'none'}{c.requested.check_in ? <> → <b>{c.requested.check_in}</b></> : <span className="text-muted-foreground"> unchanged</span>}</div>
                <div><span className="text-xs text-muted-foreground">Check-out </span>{c.original.check_out || 'none'}{c.requested.check_out ? <> → <b>{c.requested.check_out}{c.requested.check_out_next_day && <small> next day</small>}</b></> : <span className="text-muted-foreground"> unchanged</span>}</div>
              </div>
              <p className="text-sm">“{c.reason}”</p>
              {c.can_decide ? (
                <div className="flex flex-wrap gap-2">
                  <Input aria-label={`Note to ${c.person.name}`} className="min-w-48 flex-1" maxLength={255} placeholder={`Note to ${c.person.name} (optional)`} value={notes[c.id] ?? ''} onChange={(e) => setNotes((n) => ({ ...n, [c.id]: e.target.value }))} />
                  <Button variant="outline" onClick={() => decide(c, 'reject')}>Reject</Button>
                  <Button onClick={() => decide(c, 'approve')}>Approve</Button>
                </div>
              ) : <p className="text-sm text-muted-foreground">This is your own request, so another owner or admin has to decide it.</p>}
            </Card>
          ))}
          {d.decided.length > 0 && (
            <Card className="overflow-x-auto p-0">
              <div className="border-b p-4 font-semibold">Recently decided</div>
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="p-3 font-medium">Person</th><th className="p-3 font-medium">Day</th><th className="p-3 font-medium">Result</th><th className="p-3 font-medium">By</th><th className="p-3 font-medium">Note</th></tr></thead>
                <tbody>{d.decided.map((c) => <tr key={c.id} className="border-b last:border-0"><td className="p-3">{c.person.name}</td><td className="p-3">{c.date_label}</td><td className="p-3"><CorrectionStatus c={c} /></td><td className="p-3">{c.decided_by || '—'}</td><td className="p-3 text-muted-foreground">{c.decision_note}</td></tr>)}</tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export function CorrectionRequestPage() {
  const [params] = useSearchParams();
  const date = params.get('date') ?? '';
  const q = useAttQuery<CorrectionForm>('correction-form', `attendance/corrections/request/${date ? `?date=${date}` : ''}`);
  const navigate = useNavigate();
  const refresh = useAttRefresh();
  const [day, setDay] = useState('');
  const [inn, setInn] = useState('');
  const [out, setOut] = useState('');
  const [nextDay, setNextDay] = useState(false);
  const [why, setWhy] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const d = q.data;
  useEffect(() => {
    if (d) setDay((x) => x || d.date);
  }, [d]);
  useEffect(() => {
    document.title = 'Ask for a correction — PQ Platform';
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    sending.current = true;
    setBusy(true);
    setError('');
    try {
      const r = await api.post<{ message: string }>('attendance/corrections/request/', { date: day, check_in: inn, check_out: out, out_next_day: nextDay, reason: why });
      refresh();
      toast(r.message, 'success');
      navigate('/attendance/');
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Could not send.');
      toast(reason(err), 'error');
      sending.current = false;
      setBusy(false);
    }
  };

  if (!d) return <Skeleton className="h-64 w-full" data-testid="corr-form-loading" />;
  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl space-y-4" noValidate>
      <div className="flex items-center justify-between"><h1 className="text-xl font-semibold">Ask for a correction</h1><Button asChild variant="outline" size="sm"><Link to="/attendance/">Cancel</Link></Button></div>
      <Card className="space-y-4 p-5">
        <p className="text-sm text-muted-foreground">Tell us what the day should say. Nothing changes until an owner or admin approves it. You can ask for a day in the last {d.max_age_days} days.</p>
        {d.record && <p className="rounded-md bg-secondary p-3 text-sm">Recorded for {d.date_label}: in {d.record.check_in || 'none'}, out {d.record.check_out || 'none'}.</p>}
        {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="grid gap-1.5 text-sm font-medium">Day<Input type="date" min={d.min_date} max={d.max_date} value={day} onChange={(e) => setDay(e.target.value)} /></label>
          <label className="grid gap-1.5 text-sm font-medium">Check in<Input type="time" value={inn} onChange={(e) => setInn(e.target.value)} /></label>
          <label className="grid gap-1.5 text-sm font-medium">Check out<Input type="time" value={out} onChange={(e) => setOut(e.target.value)} /></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={nextDay} onCheckedChange={(c) => setNextDay(c === true)} /> The check-out was after midnight (the next day)</label>
        <label className="grid gap-1.5 text-sm font-medium">Reason<Input maxLength={500} placeholder="Why does the day need changing?" value={why} onChange={(e) => setWhy(e.target.value)} /></label>
        <p className="text-xs text-muted-foreground">Only the times you fill in are changed.</p>
      </Card>
      <div className="flex justify-end gap-2"><Button asChild variant="outline"><Link to="/attendance/">Cancel</Link></Button><Button type="submit" loading={busy}>Send request</Button></div>
      {d.recent.length > 0 && (
        <Card className="space-y-2 p-5">
          <h2 className="text-sm font-semibold">Your recent requests</h2>
          <ul className="divide-y text-sm">{d.recent.map((c) => <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2"><span>{c.date_label} · {when(c.requested)} · <span className="text-muted-foreground">“{c.reason}”</span></span><CorrectionStatus c={c} /></li>)}</ul>
        </Card>
      )}
    </form>
  );
}

export function RecordEditPage() {
  const id = useParams().id;
  const q = useAttQuery<RecordEdit>('record', `attendance/records/${id}/`);
  const write = useAttWrite();
  const navigate = useNavigate();
  const [inn, setInn] = useState('');
  const [out, setOut] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const d = q.data;
  useEffect(() => {
    if (d) {
      setInn(d.check_in);
      setOut(d.check_out || (d.status === 'stale' ? d.suggested_check_out : ''));
      setNotes(d.notes);
    }
  }, [d?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    document.title = 'Edit attendance — PQ Platform';
  }, []);
  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return <Card className="p-8 text-center"><p className="text-sm">{missing ? 'Record not found.' : q.error instanceof ApiError && q.error.status === 403 ? 'Only owners and admins can edit attendance.' : 'Couldn’t load this record.'}</p><Link to="/attendance/team/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to the team</Link></Card>;
  }
  if (!d) return <Skeleton className="h-64 w-full" data-testid="rec-loading" />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    const r = await write(() => api.patch<RecordEdit>(`attendance/records/${d.id}/`, { check_in: inn, check_out: out, notes }), 'success');
    setBusy(false);
    if (r) navigate(-1);
  };

  return (
    <form onSubmit={submit} className="mx-auto max-w-xl space-y-4" noValidate>
      <div className="flex items-center justify-between"><h1 className="text-xl font-semibold">Edit attendance</h1><Button asChild variant="outline" size="sm"><Link to="/attendance/team/">Cancel</Link></Button></div>
      <Card className="space-y-4 p-5">
        <p className="text-sm"><b>{d.user.name}</b> · {d.date_label}</p>
        {d.status === 'stale' && <p className="rounded-md border border-warning/30 bg-warning/10 p-3 text-sm">This day was never checked out. Until it is closed it counts for at most one working day ({d.worked_hours_per_day}), currently {d.effective}.</p>}
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-1.5 text-sm font-medium">Check in<Input type="datetime-local" value={inn} onChange={(e) => setInn(e.target.value)} /></label>
          <label className="grid gap-1.5 text-sm font-medium">Check out<Input type="datetime-local" value={out} onChange={(e) => setOut(e.target.value)} /></label>
        </div>
        <label className="grid gap-1.5 text-sm font-medium">Notes<Input maxLength={255} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
        <p className="text-xs text-muted-foreground">Leave check-out empty to keep the day open. Changes are logged.</p>
      </Card>
      <div className="flex justify-end gap-2"><Button asChild variant="outline"><Link to="/attendance/team/">Cancel</Link></Button><Button type="submit" loading={busy}>Save</Button></div>
    </form>
  );
}
