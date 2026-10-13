import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeftIcon, PlusIcon, SaveIcon, XIcon } from '@/components/ui/icons';
import { useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input, Textarea } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useProductDetail, useProductRefresh } from './useProducts';
import type { ProductDetail, ProductInput } from './types';
import { DateField } from '@/components/ui/date-field';
import { Label } from '@/components/ui/label';

type FieldErrors = Record<string, string[]>;
const ENVS: [string, string][] = [['production', 'Production'], ['staging', 'Staging'], ['dev', 'Development']];

function Field({ label, htmlFor, error, hint, children }: { label: string; htmlFor?: string; error?: string[]; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={htmlFor} className="text-sm font-medium">{label}</Label>
      {children}
      {error?.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>)}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

type Initial = { name: string; key: string; description: string; env: string; webhook: string };

function ProductForm({ editing, productId, initial, cancelUrl }: { editing: boolean; productId?: number; initial: Initial; cancelUrl: string }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const refresh = useProductRefresh();
  const [name, setName] = useState(initial.name);
  const [key, setKey] = useState(initial.key);
  const [autoKey, setAutoKey] = useState(!initial.key); // the prefix follows the name until someone types their own
  const [description, setDescription] = useState(initial.description);
  const [env, setEnv] = useState(initial.env);
  const [webhook, setWebhook] = useState(initial.webhook);
  const [rows, setRows] = useState<{ title: string; date: string }[]>([{ title: '', date: '' }]);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const sending = useRef(false);

  useEffect(() => {
    document.title = `${editing ? 'Edit Product' : 'New Product'} — PQ Platform`;
  }, [editing]);

  // The suggestion is asked of the server, which knows which prefixes the company already uses.
  useEffect(() => {
    if (!autoKey) return;
    if (!name.trim()) {
      setKey('');
      return;
    }
    const t = setTimeout(async () => {
      try {
        const r = await api.get<{ key: string }>(`products/key-suggestion/?name=${encodeURIComponent(name)}${productId ? `&product=${productId}` : ''}`);
        setKey(r.key);
      } catch {
        /* the field stays as it is; a prefix is suggested on save anyway */
      }
    }, 250);
    return () => clearTimeout(t);
  }, [name, autoKey, productId]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    if (!name.trim()) {
      setErrors({ name: ['This field is required.'] });
      return;
    }
    const input: ProductInput = { name: name.trim(), key, description, default_environment: env, discord_webhook_url: webhook, milestones: rows };
    sending.current = true;
    setSaving(true);
    setErrors({});
    try {
      if (editing) {
        const saved = await api.patch<ProductDetail>(`products/${productId}/`, input);
        qc.setQueryData(['product', productId], { ...saved, message: undefined });
        refresh();
        toast(saved.message ?? 'Saved.', 'success');
        navigate(`/products/${productId}/`);
      } else {
        const r = await api.post<{ url: string; message: string }>('products/', input);
        refresh();
        toast(r.message, 'success');
        navigate(r.url);
      }
    } catch (err) {
      setErrors((err instanceof ApiError && (err.body as { errors?: FieldErrors } | undefined)?.errors) || {});
      toast(err instanceof Error ? err.message : 'Could not save.', 'error');
      sending.current = false;
      setSaving(false);
    }
  };

  const setRow = (i: number, patch: Partial<{ title: string; date: string }>) => setRows((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x)));

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-4" noValidate>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{editing ? 'Edit Product' : 'New Product'}</h1>
        <Button asChild variant="outline" size="sm"><Link to={cancelUrl}><XIcon />Cancel</Link></Button>
      </div>

      <Card className="space-y-4 p-5">
        <h2 className="text-sm font-medium text-muted-foreground">Product info</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" htmlFor="product-name" error={errors.name}>
            <Input id="product-name" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="My App" aria-invalid={!!errors.name} />
          </Field>
          <Field label="Default environment" error={errors.default_environment}>
            <Select value={env} onValueChange={setEnv}>
              <SelectTrigger aria-label="Default environment"><SelectValue /></SelectTrigger>
              <SelectContent>{ENVS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
            </Select>
          </Field>
        </div>
        <Field
          label="Ticket prefix"
          htmlFor="product-key"
          error={errors.key}
          hint={<>Tickets are named with it, for example <b>{(key || 'ABC') + '-001'}</b>.{autoKey && key ? ' Taken from the name. Type here to choose your own.' : ''}{editing ? ' Changing it renames every ticket of this product, so old links in chat will not match the new name.' : ''}</>}
        >
          <Input
            id="product-key"
            className="max-w-60 uppercase"
            maxLength={6}
            autoComplete="off"
            placeholder="Made from the name"
            value={key}
            onChange={(e) => {
              setAutoKey(false);
              setKey(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''));
            }}
          />
        </Field>
        <Field label="Description" htmlFor="product-description" error={errors.description} hint="Shown on the product dashboard so teammates know what this product is.">
          <Textarea id="product-description" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
        </Field>
      </Card>

      <Card className="space-y-4 p-5">
        <h2 className="text-sm font-medium text-muted-foreground">Notifications</h2>
        <Field label="Discord webhook URL" htmlFor="product-webhook" error={errors.discord_webhook_url} hint="Get notified about tickets, errors, and feedback in a Discord channel. Can be added later.">
          <Input id="product-webhook" type="password" autoComplete="off" value={webhook} onChange={(e) => setWebhook(e.target.value)} placeholder="https://discord.com/api/webhooks/..." />
        </Field>
      </Card>

      <Card className="space-y-3 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">Project milestones (completion dates)</h2>
          <Button type="button" variant="outline" size="sm" onClick={() => setRows((r) => [...r, { title: '', date: '' }])}><PlusIcon /> Add flow node</Button>
        </div>
        {rows.map((r, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-2">
            <Input aria-label={`Milestone ${i + 1} title`} placeholder={i === 0 ? 'Phase 1: MVP Release' : 'Next phase title'} value={r.title} onChange={(e) => setRow(i, { title: e.target.value })} />
            <DateField aria-label={`Milestone ${i + 1} target date`} value={r.date} onChange={(v) => setRow(i, { date: v })} />
          </div>
        ))}
        <p className="text-xs text-muted-foreground">They render as a visual flowchart roadmap on the product page.</p>
      </Card>

      <div className="flex justify-end gap-2">
        <Button asChild variant="outline"><Link to={cancelUrl}><XIcon />Cancel</Link></Button>
        <Button type="submit" loading={saving}><SaveIcon />{editing ? 'Save Changes' : 'Create Product'}</Button>
      </div>
    </form>
  );
}

export function ProductFormPage() {
  const { pk } = useParams();
  const id = pk ? Number(pk) : null;
  const q = useProductDetail(id ?? 0);
  if (id === null) return <ProductForm editing={false} initial={{ name: '', key: '', description: '', env: 'production', webhook: '' }} cancelUrl="/products/" />;
  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <Card className="p-8 text-center">
        <p className="text-sm">{missing ? 'Product not found.' : 'Couldn’t load this product.'}</p>
        <Button asChild variant="link" className="mt-3"><Link to="/products/"><ArrowLeftIcon /> Back to products</Link></Button>
      </Card>
    );
  }
  if (!q.data) return <div className="mx-auto max-w-3xl space-y-3" data-testid="form-loading"><Skeleton className="h-8 w-48" /><Skeleton className="h-60 w-full" /></div>;
  const p = q.data.product;
  return (
    <ProductForm
      key={p.id}
      editing
      productId={p.id}
      initial={{ name: p.name, key: p.key, description: p.description, env: p.default_environment, webhook: p.discord_webhook_url }}
      cancelUrl={`/products/${p.id}/`}
    />
  );
}
