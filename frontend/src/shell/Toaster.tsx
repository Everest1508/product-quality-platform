import type * as React from 'react';
import { useEffect } from 'react';
import { AlertCircleIcon, AlertIcon, CheckCircleIcon, InfoIcon, XIcon } from '@/components/ui/icons';
import { dismiss, toast, useToasts, type Tags } from '@/lib/toast';
import { Button } from '@/components/ui/button';

// Same look as befui's Toaster (icon, title, dismiss); the store stays ours because every API write toasts through `toast(text, tag)`.
const icons: Record<Tags, React.ReactElement> = {
  success: <CheckCircleIcon className="size-4 text-success" />,
  error: <AlertCircleIcon className="size-4 text-destructive" />,
  info: <InfoIcon className="size-4 text-info" />,
  warning: <AlertIcon className="size-4 text-warning" />,
};

export function Toaster() {
  const toasts = useToasts();
  useEffect(() => {
    const off = () => toast('You are offline. Changes will not save until you reconnect.', 'error');
    const on = () => toast('Back online.', 'success');
    window.addEventListener('offline', off);
    window.addEventListener('online', on);
    return () => {
      window.removeEventListener('offline', off);
      window.removeEventListener('online', on);
    };
  }, []);
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto flex items-start gap-3 rounded-lg border bg-popover p-3.5 shadow-lg animate-toast">
          <span className="mt-0.5">{icons[t.tags]}</span>
          <p className="flex-1 text-[13px] font-medium">{t.text}</p>
          <Button variant="ghost" size="icon-sm" aria-label="Dismiss" className="size-6 text-muted-foreground" onClick={() => dismiss(t.id)}>
            <XIcon className="size-3.5" />
          </Button>
        </div>
      ))}
    </div>
  );
}
