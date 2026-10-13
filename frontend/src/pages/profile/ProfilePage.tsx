import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ago } from '@/lib/time';
import { ErrorState } from '@/components/ui/error-state';
import { Avatar } from '@/components/ui/avatar';
import { Label } from '@/components/ui/label';
import { NotificationSettings } from './NotificationSettings';
import { ShortcutList } from '@/shell/ShortcutList';
import { Milestones, StreakBadge } from '@/components/fun/Kudos';
import { RefreshIcon, SaveIcon } from '@/components/ui/icons';

type Profile = {
  user: { username: string; name: string; initial: string; first_name: string; last_name: string; email: string; discord_id: string };
  role: string;
  role_label: string;
  company: string;
  joined: string | null;
  last_login: string | null;
  streak: number;
  milestones: string[];
  stats: { open_tickets: number; resolved_30d: number; dsr_week: string; days_present: number; products: number };
  recent: { id: number; title: string; created_at: string }[];
  message?: string;
};
type FieldErrors = Record<string, string[]>;

function Field({ label, htmlFor, error, hint, children }: { label: string; htmlFor: string; error?: string[]; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={htmlFor} className="text-sm font-medium">{label}</Label>
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
      <div className="flex justify-end"><Button type="submit" loading={saving}><SaveIcon />Save Changes</Button></div>
    </form>
  );
}

const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—');

export function ProfilePage() {
  const q = useQuery({ queryKey: ['profile'], queryFn: () => api.get<Profile>('profile/') });
  useEffect(() => {
    document.title = 'Profile — PQ Platform';
  }, []);
  const p = q.data;
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      {q.isError && !p ? (
        <Card><ErrorState title="Couldn’t load your profile."><Button size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
      ) : !p ? (
        <div className="space-y-3" data-testid="profile-loading"><Skeleton className="h-32 w-full" /><Skeleton className="h-48 w-full" /></div>
      ) : (
        <>
          <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-r from-primary/15 via-accent to-transparent p-6">
            <div className="flex flex-wrap items-center gap-5">
              <Avatar name={p.user.name} size="xl" />
              <div className="min-w-0 flex-1">
                <h1 className="truncate text-2xl font-semibold">{p.user.name}</h1>
                <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">@{p.user.username} <Badge variant="info">{p.role_label}</Badge> <span>{p.company}</span> <StreakBadge days={p.streak} /></p>
                <p className="mt-1 text-sm text-muted-foreground">{p.user.email}{p.user.discord_id ? ` · Discord ${p.user.discord_id}` : ''}</p>
              </div>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                <dt className="text-muted-foreground">Member since</dt><dd className="text-right font-medium">{date(p.joined)}</dd>
                <dt className="text-muted-foreground">Last sign-in</dt><dd className="text-right font-medium">{date(p.last_login)}</dd>
              </dl>
            </div>
          </section>

          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-5">
            {([['Open tickets', p.stats.open_tickets], ['Resolved (30 days)', p.stats.resolved_30d], ['Logged this week', p.stats.dsr_week], ['Days present', p.stats.days_present], ['Products', p.stats.products]] as [string, string | number][]).map(([l, v]) => (
              <div key={l} className="bg-card p-4"><div className="text-2xl font-semibold tabular-nums">{v}</div><div className="text-xs text-muted-foreground">{l}</div></div>
            ))}
          </div>

          <Tabs defaultValue="overview">
            <TabsList aria-label="Profile sections">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="settings">Settings</TabsTrigger>
              <TabsTrigger value="notifications">Notifications</TabsTrigger>
              <TabsTrigger value="shortcuts">Keyboard shortcuts</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="mt-4 space-y-4">
              {p.milestones.length > 0 && <Card className="p-5"><Milestones items={p.milestones} /></Card>}
              <Card className="p-5">
                <h2 className="mb-2 text-sm font-semibold">Recent activity</h2>
                {p.recent.length === 0 ? <p className="py-4 text-center text-sm text-muted-foreground">Nothing yet. What you do shows up here.</p> : (
                  <ul className="divide-y text-sm">{p.recent.map((a) => <li key={a.id} className="flex justify-between gap-3 py-2"><span className="truncate">{a.title}</span><span className="shrink-0 text-xs text-muted-foreground">{ago(a.created_at)}</span></li>)}</ul>
                )}
              </Card>
            </TabsContent>
            <TabsContent value="notifications" className="mt-4 max-w-3xl"><NotificationSettings /></TabsContent>
            <TabsContent value="shortcuts" className="mt-4"><Card className="p-5"><ShortcutList /><p className="mt-4 text-xs text-muted-foreground">Shortcuts pause while you type in a field. On a Mac, ⌘ is used where other systems use Ctrl.</p></Card></TabsContent>
            <TabsContent value="settings" className="mt-4 max-w-3xl"><ProfileForm p={p} /></TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
