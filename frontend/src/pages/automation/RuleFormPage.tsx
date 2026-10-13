import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useRule, useRuleMeta, useRuleRefresh, useRuleScope } from './useRules';
import type { Rule, RuleInput, RuleMeta } from './types';

type FieldErrors = Record<string, string[]>;
const NONE = 'none'; // Radix Select does not allow an empty value
const ANY = 'any';

function Field({ label, htmlFor, error, hint, children }: { label: string; htmlFor?: string; error?: string[]; hint?: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium">{label}</label>
      {children}
      {error?.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>)}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function RuleForm({ rule, meta, productId }: { rule?: Rule; meta: RuleMeta; productId: number | null }) {
  const navigate = useNavigate();
  const refresh = useRuleRefresh();
  const [name, setName] = useState(rule?.name ?? '');
  const [product, setProduct] = useState(rule?.product ? String(rule.product.id) : NONE);
  const [trigger, setTrigger] = useState(rule?.trigger_type ?? meta.triggers[0]?.[0] ?? 'error_threshold');
  const [severity, setSeverity] = useState(rule?.severity || ANY);
  const [threshold, setThreshold] = useState(String(rule?.threshold_count ?? 5));
  const [windowMin, setWindowMin] = useState(String(rule?.window_minutes ?? 60));
  const [action, setAction] = useState(rule?.action ?? 'create_ticket');
  const [assignTo, setAssignTo] = useState(rule?.assign_to ? String(rule.assign_to) : NONE);
  const [active, setActive] = useState(rule?.is_active ?? true);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const sending = useRef(false);
  const base = productId ? `/products/${productId}/rules/` : '/automation/';
  useEffect(() => {
    document.title = `${rule ? 'Edit Rule' : 'New Rule'} — PQ Platform`;
  }, [rule]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    if (!name.trim()) return setErrors({ name: ['This field is required.'] });
    const input: RuleInput = {
      name: name.trim(), product: productId ?? (product === NONE ? null : Number(product)), trigger_type: trigger,
      severity: severity === ANY ? '' : severity, threshold_count: Number(threshold), window_minutes: Number(windowMin),
      action, assign_to: assignTo === NONE ? null : Number(assignTo), is_active: active,
    };
    sending.current = true;
    setSaving(true);
    setErrors({});
    try {
      const r = rule
        ? await api.patch<{ message: string }>(`rules/${rule.id}/`, input)
        : await api.post<{ message: string }>(productId ? `rules/?scope=product&product=${productId}` : 'rules/', input);
      refresh();
      toast(r.message, 'success');
      navigate(base);
    } catch (err) {
      setErrors((err instanceof ApiError && (err.body as { errors?: FieldErrors } | undefined)?.errors) || {});
      toast(err instanceof Error ? err.message : 'Could not save.', 'error');
      sending.current = false;
      setSaving(false);
    }
  };

  const choose = (label: string, value: string, set: (v: string) => void, options: [string, string][]) => (
    <Select value={value} onValueChange={set}>
      <SelectTrigger aria-label={label}><SelectValue /></SelectTrigger>
      <SelectContent>{options.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
    </Select>
  );
  const productOptions: [string, string][] = [
    ...(meta.can_company_wide ? ([[NONE, 'All products (company-wide)']] as [string, string][]) : []),
    ...meta.products.map((p): [string, string] => [String(p.id), p.name]),
  ];

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-4" noValidate>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-xl font-semibold">{rule ? 'Edit Rule' : 'New Automation Rule'}</h1><p className="text-sm text-muted-foreground">Configure trigger conditions and automated actions.</p></div>
        <Button asChild variant="outline" size="sm"><Link to={base}>Cancel</Link></Button>
      </div>
      <Card className="space-y-4 p-5">
        <h2 className="text-sm font-medium text-muted-foreground">Rule basics</h2>
        <Field label="Rule name" htmlFor="rule-name" error={errors.name}>
          <Input id="rule-name" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Critical Errors Spike Alert" aria-invalid={!!errors.name} />
        </Field>
        {!productId && (
          <Field label="Product scope" error={errors.product} hint={meta.can_company_wide ? 'Choose “All products” to evaluate this rule across your whole company.' : undefined}>
            {choose('Product scope', product, setProduct, productOptions)}
          </Field>
        )}
      </Card>
      <Card className="space-y-4 p-5">
        <h2 className="text-sm font-medium text-muted-foreground">Trigger thresholds</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Trigger type" error={errors.trigger_type}>{choose('Trigger type', trigger, setTrigger, meta.triggers)}</Field>
          <Field label="Severity filter" error={errors.severity}>{choose('Severity filter', severity, setSeverity, meta.severities.map(([v, l]): [string, string] => [v || ANY, l]))}</Field>
          <Field label="Threshold count" htmlFor="rule-threshold" error={errors.threshold_count}><Input id="rule-threshold" type="number" min={1} value={threshold} onChange={(e) => setThreshold(e.target.value)} /></Field>
          <Field label="Window (minutes)" htmlFor="rule-window" error={errors.window_minutes}><Input id="rule-window" type="number" min={1} value={windowMin} onChange={(e) => setWindowMin(e.target.value)} /></Field>
        </div>
      </Card>
      <Card className="space-y-4 p-5">
        <h2 className="text-sm font-medium text-muted-foreground">Action &amp; target</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Automated action" error={errors.action}>{choose('Automated action', action, setAction, meta.actions)}</Field>
          <Field label="Assign to" error={errors.assign_to}>{choose('Assign to', assignTo, setAssignTo, [[NONE, 'Nobody (Unassigned)'], ...meta.members.map((m): [string, string] => [String(m.id), m.name])])}</Field>
        </div>
        <label className="flex items-center gap-2 text-sm font-medium"><Checkbox checked={active} onCheckedChange={(c) => setActive(c === true)} /> Rule is active</label>
      </Card>
      <div className="flex justify-end gap-2">
        <Button asChild variant="outline"><Link to={base}>Cancel</Link></Button>
        <Button type="submit" loading={saving}>{rule ? 'Save Changes' : 'Create Rule'}</Button>
      </div>
    </form>
  );
}

export function RuleFormPage() {
  const params = useParams();
  const productId = useRuleScope();
  const id = params.id ? Number(params.id) : null;
  const meta = useRuleMeta(productId);
  const rule = useRule(id ?? 0);
  const loading = <div className="mx-auto max-w-3xl space-y-3" data-testid="form-loading"><Skeleton className="h-8 w-48" /><Skeleton className="h-60 w-full" /></div>;
  if (meta.isError || (id !== null && rule.isError)) {
    const missing = rule.error instanceof ApiError && rule.error.status === 404;
    return <Card className="p-8 text-center"><p className="text-sm">{missing ? 'Rule not found.' : 'Couldn’t load the form.'}</p><Link to="/automation/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to rules</Link></Card>;
  }
  if (!meta.data || (id !== null && !rule.data)) return loading;
  return <RuleForm key={id ?? 'new'} rule={id === null ? undefined : rule.data?.rule} meta={meta.data} productId={productId ?? (id === null ? null : rule.data?.rule.product?.id ?? null)} />;
}
