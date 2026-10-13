import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input, Textarea } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useTicketMeta } from '@/pages/tickets/useTicketQuery';
import { AssigneePicker } from './AssigneePicker';
import { saveTicket, useTicketDetail } from './useTicket';
import type { FieldErrors, Person, TicketInput } from './types';
import { DateTimeField } from '@/components/ui/date-field';
import { Label } from '@/components/ui/label';

const TYPES: [string, string][] = [['bug', 'Bug'], ['feature', 'Feature'], ['question', 'Question']];
const NO_PRODUCT = 'none'; // Radix Select does not allow an empty value

type FormProps = {
  mode: 'create' | 'edit';
  ticketId?: number;
  productId: number | null; // fixed product on a product page
  initial: { title: string; description: string; ticket_type: string; priority: string; status: string; assignees: number[]; deadline: string };
  heading: string;
  members: Person[];
  products: { id: number; name: string }[];
  priorities: [string, string][];
  statuses: [string, string][];
  cancelUrl: string;
};

function Field({ label, htmlFor, error, children }: { label: string; htmlFor?: string; error?: string[]; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={htmlFor} className="text-sm font-medium">{label}</Label>
      {children}
      {error?.map((e) => <p key={e} className="text-xs text-destructive">{e}</p>)}
    </div>
  );
}

function TicketForm({ mode, ticketId, productId, initial, heading, members, products, priorities, statuses, cancelUrl }: FormProps) {
  const navigate = useNavigate();
  const [title, setTitle] = useState(initial.title);
  const [description, setDescription] = useState(initial.description);
  const [type, setType] = useState(initial.ticket_type);
  const [priority, setPriority] = useState(initial.priority);
  const [status, setStatus] = useState(initial.status);
  const [product, setProduct] = useState(NO_PRODUCT);
  const [assignees, setAssignees] = useState<number[]>(initial.assignees);
  const [deadline, setDeadline] = useState(initial.deadline);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const sending = useRef(false);

  useEffect(() => {
    document.title = `${heading} — PQ Platform`;
  }, [heading]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    if (!title.trim()) {
      setErrors({ title: ['This field is required.'] });
      return;
    }
    const input: TicketInput = { title: title.trim(), description, ticket_type: type, priority, assignees, deadline };
    if (mode === 'edit') input.status = status;
    else input.product = productId ?? (product === NO_PRODUCT ? null : Number(product));
    sending.current = true;
    setSaving(true);
    setErrors({});
    try {
      const saved = await saveTicket(mode === 'edit' ? ticketId! : null, input);
      toast(mode === 'edit' ? `Ticket ${saved.key} updated.` : `Ticket ${saved.key} created.`, 'success');
      saved.warnings.forEach((w) => toast(w, 'warning'));
      navigate(saved.url);
    } catch (err) {
      setErrors((err as { fieldErrors?: FieldErrors }).fieldErrors ?? {});
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

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-4" noValidate>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{heading}</h1>
        <Button asChild variant="outline" size="sm"><Link to={cancelUrl}>Cancel</Link></Button>
      </div>

      <Card className="space-y-4 p-5">
        <Field label="Title" htmlFor="ticket-title" error={errors.title}>
          <Input id="ticket-title" autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What needs to be done?" aria-invalid={!!errors.title} />
        </Field>
        <Field label="Description" htmlFor="ticket-description" error={errors.description}>
          <Textarea id="ticket-description" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Detailed description of the issue or feature request…" />
        </Field>
      </Card>

      <Card className="space-y-4 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Type" error={errors.ticket_type}>{choose('Type', type, setType, TYPES)}</Field>
          <Field label="Priority" error={errors.priority}>{choose('Priority', priority, setPriority, priorities)}</Field>
        </div>
        {mode === 'edit' && <Field label="Status" error={errors.status}>{choose('Status', status, setStatus, statuses)}</Field>}
        {mode === 'create' && !productId && (
          <Field label="Product" error={errors.product}>
            {choose('Product', product, setProduct, [[NO_PRODUCT, 'No product (company-wide)'], ...products.map((p): [string, string] => [String(p.id), p.name])])}
          </Field>
        )}
      </Card>

      <Card className="space-y-4 p-5">
        <Field label="Assignees" error={errors.assignees}>
          <AssigneePicker people={members} value={assignees} onChange={setAssignees} />
          {mode === 'create' && !productId && product !== NO_PRODUCT && (
            <p className="text-xs text-muted-foreground">People without access to this product are skipped.</p>
          )}
        </Field>
        <Field label="Deadline" htmlFor="ticket-deadline" error={errors.deadline}>
          <DateTimeField id="ticket-deadline" value={deadline} onChange={setDeadline} />
        </Field>
      </Card>

      <div className="flex justify-end gap-2">
        <Button asChild variant="outline"><Link to={cancelUrl}>Cancel</Link></Button>
        <Button type="submit" loading={saving}>{mode === 'edit' ? 'Save Changes' : '+ Create Ticket'}</Button>
      </div>
    </form>
  );
}

export function TicketFormPage() {
  const params = useParams();
  const editId = params.id ? Number(params.id) : null;
  const productId = params.pk ? Number(params.pk) : null;

  if (editId !== null) return <EditTicket id={editId} />;
  return <CreateTicket productId={productId} />;
}

function Loading() {
  return (
    <div className="mx-auto max-w-3xl space-y-3" data-testid="form-loading">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

function CreateTicket({ productId }: { productId: number | null }) {
  const meta = useTicketMeta(productId);
  if (meta.isError) return <Card className="p-8 text-center text-sm">Couldn’t load the form.</Card>;
  if (!meta.data) return <Loading />;
  return (
    <TicketForm
      mode="create"
      productId={productId}
      heading="New Ticket"
      initial={{ title: '', description: '', ticket_type: 'bug', priority: 'medium', status: 'open', assignees: [], deadline: '' }}
      members={meta.data.members.map((m) => ({ ...m, username: '' }))}
      products={meta.data.products}
      priorities={meta.data.priorities}
      statuses={meta.data.statuses}
      cancelUrl={productId ? `/products/${productId}/tickets/` : '/tickets/'}
    />
  );
}

function EditTicket({ id }: { id: number }) {
  const q = useTicketDetail(id);
  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <Card className="p-8 text-center">
        <p className="text-sm">{missing ? 'Ticket not found.' : 'Couldn’t load this ticket.'}</p>
        <Link to="/tickets/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to tickets</Link>
      </Card>
    );
  }
  if (!q.data) return <Loading />;
  const t = q.data.ticket;
  return (
    <TicketForm
      key={t.id}
      mode="edit"
      ticketId={t.id}
      productId={null}
      heading={`Edit Ticket ${t.key}`}
      initial={{
        title: t.title, description: t.description, ticket_type: t.type, priority: t.priority, status: t.status,
        assignees: t.assignees.map((a) => a.id), deadline: t.deadline_local,
      }}
      members={q.data.members}
      products={[]}
      priorities={q.data.priorities}
      statuses={q.data.statuses}
      cancelUrl={t.url}
    />
  );
}
