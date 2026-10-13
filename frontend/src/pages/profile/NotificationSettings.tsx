import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';

type Kind = { kind: string; label: string; enabled: boolean; locked: boolean };

// One switch per kind of notification. A change saves at once and the server's message is the toast.
export function NotificationSettings() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['notification-settings'], queryFn: () => api.get<{ kinds: Kind[] }>('profile/notifications/') });
  const set = async (kind: string, enabled: boolean) => {
    try {
      const r = await api.put<{ kinds: Kind[] }>('profile/notifications/', { kind, enabled });
      qc.setQueryData(['notification-settings'], r);
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Could not save.', 'error');
    }
  };
  if (!q.data) return <Skeleton className="h-64 w-full" />;
  return (
    <Card className="p-5">
      <h2 className="font-semibold">What should notify you</h2>
      <p className="mb-3 text-sm text-muted-foreground">Turn off the kinds you don’t need. This applies in every workspace you belong to.</p>
      <ul className="divide-y">
        {q.data.kinds.map((k) => (
          <li key={k.kind} className="flex items-center justify-between gap-3 py-2.5 text-sm">
            <span>{k.label}{k.locked && <span className="ml-2 text-xs text-muted-foreground">always on</span>}</span>
            <Switch checked={k.enabled} disabled={k.locked} aria-label={k.label} onCheckedChange={(v) => set(k.kind, v)} />
          </li>
        ))}
      </ul>
    </Card>
  );
}
