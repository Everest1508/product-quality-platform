import { useEffect, useState } from 'react';
import { ClockIcon, SaveIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import type { LogRow } from './types';
import type { useDsrActions } from './useDsr';

const KEY = 'pq:dsr-needs-time';
const seen = (): number[] => {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || '[]');
  } catch {
    return [];
  }
};

// A ticket that was open longer than a working day logs no time by itself: the person says how long they really worked on it.
// The window opens by itself once for each such row in a browser session, and the banner stays until the time is entered.
export function useNeedsTimePrompt(rows: LogRow[]): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(false);
  const ids = rows.map((r) => r.id).join(',');
  useEffect(() => {
    if (!rows.length) return;
    const known = seen();
    if (rows.every((r) => known.includes(r.id))) return;
    try {
      sessionStorage.setItem(KEY, JSON.stringify([...known, ...rows.map((r) => r.id)]));
    } catch {
      /* the banner still shows */
    }
    setOpen(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids]);
  return [open, setOpen];
}

export function NeedsTimeBanner({ rows, onOpen }: { rows: LogRow[]; onOpen(): void }) {
  if (!rows.length) return null;
  return (
    <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4">
      <p className="text-sm">
        <b>{rows.length === 1 ? 'A ticket that was open a long time was added to your DSR.' : `${rows.length} long-open tickets were added to your DSR.`}</b>{' '}
        {rows.slice(0, 2).map((r) => `${r.ticket?.key ?? r.task_name} (open for ${r.elapsed})`).join(', ')}. Add the time you worked on {rows.length === 1 ? 'it' : 'them'} today. Until then {rows.length === 1 ? 'it counts' : 'they count'} for nothing.
      </p>
      <Button size="sm" onClick={onOpen}><ClockIcon />Add time</Button>
    </div>
  );
}

export function NeedsTimeDialog({ rows, act, open, onOpenChange }: { rows: LogRow[]; act: ReturnType<typeof useDsrActions>; open: boolean; onOpenChange(o: boolean): void }) {
  const [hours, setHours] = useState<Record<number, string>>({});
  const save = async () => {
    for (const r of rows) {
      const v = (hours[r.id] ?? '').trim();
      if (!v) continue;
      if (!(await act.update(r.id, { hours_spent: v })).ok) return;
    }
    setHours({});
    onOpenChange(false);
  };
  return (
    <Dialog open={open && rows.length > 0} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>How long did you work on {rows.length === 1 ? 'this ticket' : 'these tickets'} today?</DialogTitle>
          <DialogDescription>{rows.length === 1 ? 'It was' : 'They were'} open for a long time, so the time open is not counted. Enter the time you actually spent. Only that goes into your DSR.</DialogDescription>
        </DialogHeader>
        <ul className="grid gap-3">
          {rows.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-3">
              <div className="min-w-40 flex-1">
                <div className="text-sm font-medium">{r.ticket?.key ?? ''} {r.task_name.replace(/^\[[^\]]*\]\s*/, '')}</div>
                <div className="text-xs text-muted-foreground">Open for {r.elapsed}</div>
              </div>
              <Input aria-label={`Time worked on ${r.task_name}`} className="h-9 w-28" placeholder="e.g. 2h 30m" value={hours[r.id] ?? ''} onChange={(e) => setHours((h) => ({ ...h, [r.id]: e.target.value }))} />
            </li>
          ))}
        </ul>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Later</Button>
          <Button loading={act.busy} onClick={save}><SaveIcon />Save time</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
