import { useEffect } from 'react';
import { X } from 'lucide-react';
import { dismiss, toast, useToasts, type Tags } from '@/lib/toast';
import { cn } from '@/lib/utils';

const bar: Record<Tags, string> = {
  success: 'bg-success',
  error: 'bg-destructive',
  info: 'bg-info',
  warning: 'bg-warning',
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
    <div role="status" aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto relative flex items-start gap-3 overflow-hidden rounded-lg border bg-card py-3 pl-4 pr-3 text-sm shadow-lg animate-toast">
          <span className={cn('absolute inset-y-0 left-0 w-1', bar[t.tags])} />
          <span className="flex-1">{t.text}</span>
          <button type="button" aria-label="Dismiss" onClick={() => dismiss(t.id)} className="text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
