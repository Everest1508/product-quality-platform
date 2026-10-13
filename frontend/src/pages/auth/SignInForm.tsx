import { useRef, useState, type FormEvent } from 'react';
import { EyeIcon, EyeOffIcon, LogInIcon } from '@/components/ui/icons';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert } from '@/components/ui/alert';
import { Label } from '@/components/ui/label';

// The username/password form shared by the sign-in page and the desktop app's sign-in. The server decides where to go next.
export function SignInForm({ path, extra, submitLabel = 'Sign in' }: { path: string; extra: Record<string, string>; submitLabel?: string }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    if (!username.trim() || !password) {
      setError('Enter your username and password.');
      return;
    }
    sending.current = true;
    setBusy(true);
    setError('');
    try {
      const r = await api.post<{ redirect: string }>(path, { username: username.trim(), password, ...extra });
      window.location.assign(r.redirect);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Could not sign in.');
      setPassword('');
      sending.current = false;
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      {error && <Alert variant="danger">{error}</Alert>}
      <div className="grid gap-1.5">
        <Label htmlFor="username" className="text-sm font-medium">Username or email <span aria-hidden className="text-destructive">*</span></Label>
        <Input id="username" autoFocus autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} placeholder="Username or email" value={username} onChange={(e) => setUsername(e.target.value)} aria-invalid={!!error} />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="password" className="text-sm font-medium">Password <span aria-hidden className="text-destructive">*</span></Label>
        <div className="relative">
          <Input id="password" type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Password" className="pr-10" value={password} onChange={(e) => setPassword(e.target.value)} aria-invalid={!!error} />
          <Button type="button" variant="ghost" size="icon-sm" aria-label={show ? 'Hide password' : 'Show password'} className="absolute right-0.5 top-0.5 text-muted-foreground" onClick={() => setShow((s) => !s)}>
            {show ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
          </Button>
        </div>
      </div>
      <Button type="submit" className="w-full" loading={busy}><LogInIcon />{submitLabel}</Button>
    </form>
  );
}
