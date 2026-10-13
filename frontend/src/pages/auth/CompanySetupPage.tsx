import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AuthLayout } from './AuthLayout';

export function CompanySetupPage() {
  const [name, setName] = useState('');
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  useEffect(() => {
    document.title = 'Set up your company — PQ Platform';
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    if (!name.trim()) return setErrors(['This field is required.']);
    sending.current = true;
    setBusy(true);
    setErrors([]);
    try {
      const r = await api.post<{ redirect: string }>('auth/company/', { name: name.trim() });
      window.location.assign(r.redirect);
    } catch (err) {
      const fields = err instanceof ApiError ? (err.body as { errors?: { name?: string[] } } | undefined)?.errors?.name : undefined;
      setErrors(fields ?? [err instanceof Error ? err.message : 'Could not create the company.']);
      sending.current = false;
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Set up your company" subtitle="You are not part of a workspace yet. Create one and you will be its owner.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <div className="grid gap-1.5">
          <label htmlFor="company-name" className="text-sm font-medium">Company name</label>
          <Input id="company-name" autoFocus placeholder="Acme Corp" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={errors.length > 0} />
          {errors.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>)}
        </div>
        <Button type="submit" className="w-full" loading={busy}>Create company</Button>
      </form>
      <form method="post" action="/logout/" className="mt-3 text-center"><button type="submit" className="text-xs text-muted-foreground underline">Sign out</button></form>
    </AuthLayout>
  );
}
