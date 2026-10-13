import { useRef, useState, type FormEvent } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

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
      {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div className="grid gap-1.5">
        <label htmlFor="username" className="text-sm font-medium">Username or email <span aria-hidden className="text-destructive">*</span></label>
        <Input id="username" autoFocus autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} placeholder="Username or email" value={username} onChange={(e) => setUsername(e.target.value)} aria-invalid={!!error} />
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="password" className="text-sm font-medium">Password <span aria-hidden className="text-destructive">*</span></label>
        <div className="relative">
          <Input id="password" type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Password" className="pr-10" value={password} onChange={(e) => setPassword(e.target.value)} aria-invalid={!!error} />
          <button type="button" aria-label={show ? 'Hide password' : 'Show password'} className="absolute inset-y-0 right-0 grid w-10 place-items-center text-muted-foreground hover:text-foreground" onClick={() => setShow((s) => !s)}>
            {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
      </div>
      <Button type="submit" className="w-full" loading={busy}>{submitLabel}</Button>
    </form>
  );
}
