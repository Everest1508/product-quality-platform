import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/components/ui/page-header';
import { ErrorState } from '@/components/ui/error-state';

type Profile = {
  user: { username: string; name: string; initial: string; first_name: string; last_name: string; email: string; discord_id: string };
  role: string;
  role_label: string;
  company: string;
  message?: string;
};
type FieldErrors = Record<string, string[]>;

function Field({ label, htmlFor, error, hint, children }: { label: string; htmlFor: string; error?: string[]; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium">{label}</label>
      {children}
      {error?.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>)}
      {hint && <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ProfileForm({ p }: { p: Profile }) {
  const qc = useQueryClient();
  const [first, setFirst] = useState(p.user.first_name);
  const [last, setLast] = useState(p.user.last_name);
  const [email, setEmail] = useState(p.user.email);
  const [discord, setDiscord] = useState(p.user.discord_id);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const sending = useRef(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    sending.current = true;
    setSaving(true);
    setErrors({});
    try {
      const r = await api.patch<Profile>('profile/', { first_name: first, last_name: last, email, discord_id: discord });
      qc.setQueryData(['profile'], { ...r, message: undefined });
      qc.invalidateQueries({ queryKey: ['bootstrap'] }); // the name in the top bar
      toast(r.message ?? 'Profile updated.', 'success');
    } catch (err) {
      setErrors((err instanceof ApiError && (err.body as { errors?: FieldErrors } | undefined)?.errors) || {});
      toast(err instanceof Error ? err.message : 'Could not save.', 'error');
    } finally {
      sending.current = false;
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <Card className="space-y-4 p-6">
        <div><h2 className="font-semibold">Personal information</h2><p className="text-sm text-muted-foreground">Update your display name and primary contact email.</p></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First name" htmlFor="p-first" error={errors.first_name}><Input id="p-first" value={first} onChange={(e) => setFirst(e.target.value)} /></Field>
          <Field label="Last name" htmlFor="p-last" error={errors.last_name}><Input id="p-last" value={last} onChange={(e) => setLast(e.target.value)} /></Field>
        </div>
        <Field label="Email address" htmlFor="p-email" error={errors.email}><Input id="p-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
      </Card>
      <Card className="space-y-4 p-6">
        <div><h2 className="font-semibold">Notification integrations</h2><p className="text-sm text-muted-foreground">Link external accounts for ticket assignment and alert mentions.</p></div>
        <Field label="Discord User ID" htmlFor="p-discord" error={errors.discord_id} hint={<>Used to mention you in Discord webhook alerts when a ticket is assigned to you. Enable <b>Developer Mode</b> in Discord settings, right-click your avatar, and choose <i>“Copy User ID”</i>.</>}>
          <Input id="p-discord" value={discord} onChange={(e) => setDiscord(e.target.value)} placeholder="e.g. 123456789012345678" />
        </Field>
      </Card>
      <div className="flex justify-end"><Button type="submit" loading={saving}>Save Changes</Button></div>
    </form>
  );
}

export function ProfilePage() {
  const q = useQuery({ queryKey: ['profile'], queryFn: () => api.get<Profile>('profile/') });
  useEffect(() => {
    document.title = 'Settings — PQ Platform';
  }, []);
  const p = q.data;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader title="Settings" sub="Manage your profile details, email address, and notification preferences." />
      {q.isError && !p ? (
        <ErrorState message="Couldn’t load your settings." onRetry={() => q.refetch()} />
      ) : !p ? (
        <div className="space-y-3" data-testid="profile-loading"><Skeleton className="h-20 w-full" /><Skeleton className="h-48 w-full" /></div>
      ) : (
        <>
          <Card className="flex flex-wrap items-center justify-between gap-4 p-5">
            <div className="flex min-w-0 items-center gap-4">
              <span className="grid size-12 shrink-0 place-items-center rounded-full bg-accent text-lg font-semibold text-accent-foreground">{p.user.initial}</span>
              <div className="min-w-0"><div className="truncate font-semibold">{p.user.name}</div><div className="text-sm text-muted-foreground">@{p.user.username} · <Badge variant="info">{p.role_label}</Badge></div></div>
            </div>
            <div className="text-sm text-muted-foreground">Company: <b className="text-foreground">{p.company}</b></div>
          </Card>
          <ProfileForm p={p} />
        </>
      )}
    </div>
  );
}
