import { useEffect, useState } from 'react';
import { AlertDialog } from '@/components/ui/alert-dialog';

const hm = (ms: number) => {
  const m = Math.max(0, Math.floor(ms / 60000));
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`;
};

// Asks before punching out, with the time worked so far, since a punch-out ends the day.
export function PunchOutDialog({ open, onOpenChange, sinceMs, onConfirm }: { open: boolean; onOpenChange: (o: boolean) => void; sinceMs: number | null; onConfirm: () => void }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!open) return;
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(t);
  }, [open]);
  return (
    <AlertDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Punch out for today?"
      description={`You will be punched out for today. Time worked so far: ${sinceMs ? hm(now - sinceMs) : '—'}.`}
      confirmLabel="Punch out"
      onConfirm={onConfirm}
    />
  );
}
