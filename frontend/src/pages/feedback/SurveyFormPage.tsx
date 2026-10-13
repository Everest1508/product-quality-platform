import { FormSkeleton } from '@/components/skeletons';
import { stickyBar } from '@/components/StickyActions';
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input, Textarea } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useSurveyMeta, useSurveyRefresh, useSurveyScope } from './useFeedback';
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

export function SurveyFormPage() {
  const productId = useSurveyScope();
  const navigate = useNavigate();
  const meta = useSurveyMeta(productId);
  const refresh = useSurveyRefresh();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState('nps');
  const [status, setStatus] = useState('draft');
  const [product, setProduct] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const sending = useRef(false);
  const cancelUrl = productId ? `/products/${productId}/surveys/` : '/feedback/';
  useEffect(() => {
    document.title = 'New Survey — PQ Platform';
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    const missing: FieldErrors = {};
    if (!name.trim()) missing.name = ['This field is required.'];
    if (!productId && !product) missing.product = ['Choose a product.'];
    if (Object.keys(missing).length) return setErrors(missing);
    sending.current = true;
    setSaving(true);
    setErrors({});
    try {
      const path = productId ? `surveys/?scope=product&product=${productId}` : 'surveys/';
      const r = await api.post<{ url: string; message: string }>(path, { name: name.trim(), description, survey_type: type, status, product: productId ?? Number(product) });
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
  if (!meta.data) return <FormSkeleton className="mx-auto max-w-2xl space-y-4" />;
  const choose = (label: string, value: string, set: (v: string) => void, options: [string, string][], placeholder?: string) => (
    <Select value={value} onValueChange={set}>
      <SelectTrigger aria-label={label}><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>{options.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
    </Select>
  );

  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl space-y-4" noValidate>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">New Survey</h1>
        <Button asChild variant="outline" size="sm"><Link to={cancelUrl}><XIcon />Cancel</Link></Button>
      </div>
      <Card className="space-y-4 p-5">
        <Field label="Name" htmlFor="survey-name" error={errors.name}>
          <Input id="survey-name" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q1 NPS Survey" aria-invalid={!!errors.name} />
        </Field>
        <Field label="Description" htmlFor="survey-description" error={errors.description}>
          <Textarea id="survey-description" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description..." />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Type" error={errors.survey_type}>{choose('Type', type, setType, meta.data.types)}</Field>
          <Field label="Status" error={errors.status}>{choose('Status', status, setStatus, meta.data.statuses)}</Field>
        </div>
        {!productId && (
          <Field label="Product" error={errors.product}>
            {choose('Product', product, setProduct, meta.data.products.map((p): [string, string] => [String(p.id), p.name]), 'Choose a product')}
          </Field>
        )}
      </Card>
      <div className={stickyBar}>
        <Button asChild variant="outline"><Link to={cancelUrl}><XIcon />Cancel</Link></Button>
        <Button type="submit" loading={saving}><PlusIcon />Create Survey</Button>
      </div>
    </form>
  );
}
