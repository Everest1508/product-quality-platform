import { useRef, useState, type FormEvent, type ReactNode } from 'react';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useTeamRefresh } from './useTeam';
import type { Member } from './types';
import { Label } from '@/components/ui/label';

type FieldErrors = Record<string, string[]>;

function Field({ label, htmlFor, error, hint, children }: { label: string; htmlFor?: string; error?: string[]; hint?: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={htmlFor} className="text-sm font-medium">{label}</Label>
      {children}
      {error?.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>)}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

// Adding a person (no `member`) or changing one. The server owns every rule; field errors come back under their fields.
export function MemberDialog({ open, onOpenChange, member, roles }: { open: boolean; onOpenChange(o: boolean): void; member?: Member; roles: [string, string][] }) {
  const refresh = useTeamRefresh();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState(member?.user.email ?? '');
  const [first, setFirst] = useState(member?.user.first_name ?? '');
  const [last, setLast] = useState(member?.user.last_name ?? '');
  const [discord, setDiscord] = useState(member?.user.discord_id ?? '');
  const [role, setRole] = useState(member?.role ?? 'developer');
  const [approver, setApprover] = useState(member?.is_leave_approver ?? false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    sending.current = true;
    setBusy(true);
    setErrors({});
    try {
      const r = member
        ? await api.patch<{ message: string }>(`team/${member.id}/`, { first_name: first, last_name: last, email, discord_id: discord, role, is_leave_approver: approver })
        : await api.post<{ message: string }>('team/', { username, email, first_name: first, last_name: last, password, role });
      refresh();
      toast(r.message, 'success');
      onOpenChange(false);
    } catch (err) {
      setErrors((err instanceof ApiError && (err.body as { errors?: FieldErrors } | undefined)?.errors) || {});
      toast(err instanceof Error ? err.message : 'Could not save.', 'error');
    } finally {
      sending.current = false;
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <form onSubmit={submit} className="space-y-3" noValidate>
          <DialogHeader><DialogTitle>{member ? `Edit ${member.user.username}` : 'Add Team Member'}</DialogTitle></DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            {!member && <Field label="Username" htmlFor="m-username" error={errors.username}><Input id="m-username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username" /></Field>}
            <Field label="Email" htmlFor="m-email" error={errors.email}><Input id="m-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" /></Field>
            <Field label="First name" htmlFor="m-first" error={errors.first_name}><Input id="m-first" value={first} onChange={(e) => setFirst(e.target.value)} /></Field>
            <Field label="Last name" htmlFor="m-last" error={errors.last_name}><Input id="m-last" value={last} onChange={(e) => setLast(e.target.value)} /></Field>
            {!member && <Field label="Password" htmlFor="m-password" error={errors.password}><Input id="m-password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>}
            {member && <Field label="Discord ID" htmlFor="m-discord" error={errors.discord_id} hint="Enables @mention in Discord webhooks."><Input id="m-discord" value={discord} onChange={(e) => setDiscord(e.target.value)} placeholder="e.g. 123456789012345678" /></Field>}
            <Field label="Role" error={errors.role}>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger aria-label="Role"><SelectValue /></SelectTrigger>
                <SelectContent>{roles.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            {member && <Label className="flex items-center gap-2 self-end pb-2 text-sm"><Checkbox checked={approver} onCheckedChange={(c) => setApprover(c === true)} /> Can approve leave</Label>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" loading={busy}>{member ? 'Save' : 'Add Member'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
