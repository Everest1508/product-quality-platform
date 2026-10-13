import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input, Textarea } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useErrorMeta, useErrorRefresh } from './useErrors';
import type { ErrorInput } from './types';
import { Label } from '@/components/ui/label';
import { PlusIcon, XIcon } from '@/components/ui/icons';

type FieldErrors = Record<string, string[]>;

function Field({ label, htmlFor, error, children }: { label: string; htmlFor?: string; error?: string[]; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={htmlFor} className="text-sm font-medium">{label}</Label>
      {children}
      {error?.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>)}
    </div>
  );
}

export function ErrorFormPage() {
  const { pk } = useParams();
  const fixedProduct = pk ? Number(pk) : null;
  const navigate = useNavigate();
  const meta = useErrorMeta(fixedProduct);
  const refresh = useErrorRefresh();
  const [product, setProduct] = useState('');
  const [title, setTitle] = useState('');
  const [errorType, setErrorType] = useState('');
  const [severity, setSeverity] = useState('medium');
  const [stacktrace, setStacktrace] = useState('');
  const [environment, setEnvironment] = useState('production');
  const [page, setPage] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const sending = useRef(false);
  const cancelUrl = fixedProduct ? `/products/${fixedProduct}/errors/` : '/errors/';

  useEffect(() => {
    document.title = 'Report Error — PQ Platform';
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    const productId = fixedProduct ?? (product ? Number(product) : null);
    const missing: FieldErrors = {};
    if (!title.trim()) missing.title = ['This field is required.'];
    if (!productId) missing.product = ['Choose a product.'];
    if (Object.keys(missing).length) {
      setErrors(missing);
      return;
    }
    const input: ErrorInput = { product: productId, title: title.trim(), error_type: errorType, severity, stacktrace, environment, page };
    sending.current = true;
    setSaving(true);
    setErrors({});
    try {
      const r = await api.post<{ url: string; message: string }>('errors/', input);
      refresh();
      toast(r.message, 'success');
      navigate(r.url);
    } catch (err) {
      setErrors((err instanceof ApiError && (err.body as { errors?: FieldErrors } | undefined)?.errors) || {});
      toast(err instanceof Error ? err.message : 'Could not save.', 'error');
      sending.current = false;
      setSaving(false);
    }
  };

  if (meta.isError) return <Card className="p-8 text-center text-sm">Couldn’t load the form.</Card>;
  if (!meta.data) {
    return (
      <div className="mx-auto max-w-2xl space-y-3" data-testid="form-loading">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl space-y-4" noValidate>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Report Error</h1>
        <Button asChild variant="outline" size="sm"><Link to={cancelUrl}><XIcon />Cancel</Link></Button>
      </div>
      <Card className="space-y-4 p-5">
        {!fixedProduct && (
          <Field label="Product" error={errors.product}>
            <Select value={product} onValueChange={setProduct}>
              <SelectTrigger aria-label="Product"><SelectValue placeholder="Choose a product" /></SelectTrigger>
              <SelectContent>{meta.data.products.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}</SelectContent>
            </Select>
          </Field>
        )}
        <Field label="Title" htmlFor="error-title" error={errors.title}>
          <Input id="error-title" autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Error title" aria-invalid={!!errors.title} />
        </Field>
        <Field label="Error type" htmlFor="error-type" error={errors.error_type}>
          <Input id="error-type" value={errorType} onChange={(e) => setErrorType(e.target.value)} placeholder="e.g. TypeError, ValueError" />
        </Field>
        <Field label="Severity" error={errors.severity}>
          <Select value={severity} onValueChange={setSeverity}>
            <SelectTrigger aria-label="Severity"><SelectValue /></SelectTrigger>
            <SelectContent>{meta.data.severities.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
          </Select>
        </Field>
        <Field label="Stacktrace" htmlFor="error-stack" error={errors.stacktrace}>
          <Textarea id="error-stack" rows={4} value={stacktrace} onChange={(e) => setStacktrace(e.target.value)} placeholder="Paste stacktrace here (optional)" />
        </Field>
        <Field label="Environment" htmlFor="error-env" error={errors.environment}>
          <Input id="error-env" value={environment} onChange={(e) => setEnvironment(e.target.value)} />
        </Field>
        <Field label="Page" htmlFor="error-page" error={errors.page}>
          <Input id="error-page" value={page} onChange={(e) => setPage(e.target.value)} placeholder="Page URL where error occurred" />
        </Field>
      </Card>
      <div className="flex justify-end gap-2">
        <Button asChild variant="outline"><Link to={cancelUrl}><XIcon />Cancel</Link></Button>
        <Button type="submit" loading={saving}><PlusIcon />Report Error</Button>
      </div>
    </form>
  );
}
