import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Copy, Pencil, Plus, Trash2, X } from 'lucide-react';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api';
import { ago, shortDate } from '@/lib/time';
import { MilestoneFlow } from './MilestoneFlow';
import { useProductActions, useProductDetail } from './useProducts';
import type { ApiKeyRow, ProductDetail } from './types';
import { Avatar } from '@/components/ui/avatar';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { Label } from '@/components/ui/label';
import { StatCard } from '@/components/ui/stat-card';

const GRACE: [string, string][] = [['1d', 'Old key works 24 more hours'], ['7d', 'Old key works 7 more days'], ['now', 'Stop the old key now']];

export function KeyState({ k }: { k: ApiKeyRow }) {
  if (k.state === 'active') return <Badge variant="success">Active</Badge>;
  if (k.state === 'expiring') return <Badge variant="warning" title={`Stops working ${k.expires_at ? new Date(k.expires_at).toLocaleString() : ''}`}>Ends {k.expires_at ? ago(k.expires_at).replace(/^in /, 'in ') : ''}</Badge>;
  if (k.state === 'expired') return <Badge variant="danger">Expired</Badge>;
  return <Badge>Revoked</Badge>;
}

function Stat({ label, value, tone, foot }: { label: string; value: number; tone: string; foot: React.ReactNode }) {
  return <StatCard label={label} value={<span className={tone}>{value}</span>} chart={<div className="text-xs">{foot}</div>} />;
}

function NewKeyBanner({ raw, rotated, onDismiss }: { raw: string; rotated: boolean; onDismiss(): void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="mt-3 rounded-lg border border-success/40 bg-success/5 p-3" role="status">
      <p className="text-sm font-medium text-success">{rotated ? 'New key ready.' : 'API key generated.'} Copy it now. It will not be shown again.</p>
      <div className="mt-2 flex gap-2">
        <code className="flex-1 break-all rounded border bg-card p-2 text-xs">{raw}</code>
        <Button
          size="sm"
          variant="outline"
          onClick={() => navigator.clipboard.writeText(raw).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); })}
        >
          <Copy /> {copied ? 'Copied!' : 'Copy'}
        </Button>
        <Button size="icon-sm" variant="ghost" aria-label="Dismiss" onClick={onDismiss}><X /></Button>
      </div>
    </div>
  );
}

function KeysCard({ data, act }: { data: ProductDetail; act: ReturnType<typeof useProductActions> }) {
  const [name, setName] = useState('');
  const [raw, setRaw] = useState<{ key: string; rotated: boolean } | null>(null);
  const [grace, setGrace] = useState<Record<number, string>>({});
  const [revoke, setRevoke] = useState<ApiKeyRow | null>(null);
  const [rotate, setRotate] = useState<ApiKeyRow | null>(null);
  const p = data.product;

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    const r = await act.createKey(name.trim());
    if (r?.raw_key) {
      setRaw({ key: r.raw_key, rotated: false });
      setName('');
    }
  };

  return (
    <Card className="space-y-3 p-5" id="api-key-list">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">API keys</h2>
        <Badge>{data.api_keys.length}</Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        Use an API key to report errors and feedback from your application. <Link to={`/products/${p.id}/api/`} className="font-medium text-primary hover:underline">See how to use it</Link>.
      </p>
      {data.api_keys.length === 0 && <p className="py-3 text-center text-sm text-muted-foreground">No API keys yet.</p>}
      <ul className="divide-y">
        {data.api_keys.map((k) => (
          <li key={k.id} className="space-y-2 py-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{k.name}</span>
              <KeyState k={k} />
            </div>
            <div className="text-xs text-muted-foreground">
              <code>{k.prefix}...</code> · created {shortDate(k.created_at)} · {k.last_used_at ? `last used ${ago(k.last_used_at)}` : 'never used'}
            </div>
            {k.usable && data.can_manage_keys && (
              <div className="flex flex-wrap items-center gap-2">
                <Select value={grace[k.id] ?? '1d'} onValueChange={(v) => setGrace((g) => ({ ...g, [k.id]: v }))}>
                  <SelectTrigger aria-label={`What happens to the old key ${k.name}`} className="h-8 w-60 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>{GRACE.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
                </Select>
                <Button size="sm" variant="outline" disabled={act.busy === 'key'} onClick={() => setRotate(k)}>Rotate</Button>
                <Button size="sm" variant="destructive" disabled={act.busy === 'key'} onClick={() => setRevoke(k)}>Revoke</Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {raw && <NewKeyBanner raw={raw.key} rotated={raw.rotated} onDismiss={() => setRaw(null)} />}
      {data.can_manage_keys ? (
        <form onSubmit={create} className="flex gap-2 border-t pt-3">
          <Input aria-label="Key name" placeholder="Key name" value={name} onChange={(e) => setName(e.target.value)} />
          <Button type="submit" loading={act.busy === 'key'}>Generate</Button>
        </form>
      ) : (
        <p className="border-t pt-3 text-sm text-muted-foreground">Owners, admins and developers can create and rotate keys.</p>
      )}

      <AlertDialog
        open={rotate !== null}
        onOpenChange={(o) => !o && setRotate(null)}
        title="Make a new key for this product?"
        description="Update your app to use it."
        confirmLabel="Rotate"
        onConfirm={async () => {
          if (!rotate) return;
          const r = await act.rotateKey(rotate.id, grace[rotate.id] ?? '1d');
          if (r?.raw_key) setRaw({ key: r.raw_key, rotated: true });
        }}
      />
      <AlertDialog
        open={revoke !== null}
        onOpenChange={(o) => !o && setRevoke(null)}
        destructive
        title="Revoke this API key?"
        description="Apps using it stop working immediately."
        confirmLabel="Revoke"
        onConfirm={() => revoke && act.revokeKey(revoke.id)}
      />
    </Card>
  );
}

function VersionsCard({ data, act }: { data: ProductDetail; act: ReturnType<typeof useProductActions> }) {
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState('');
  const [current, setCurrent] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    if (await act.addVersion(text.trim(), current)) {
      setText('');
      setCurrent(false);
      setAdding(false);
    }
  };
  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Versions</h2>
        <Button size="sm" variant="outline" onClick={() => setAdding(true)}><Plus /> Add</Button>
      </div>
      {data.versions.length === 0 && <p className="py-3 text-center text-sm text-muted-foreground">No versions yet.</p>}
      <ul className="divide-y">
        {data.versions.map((v) => (
          <li key={v.id} className="flex items-center justify-between py-2">
            <span className="flex items-center gap-2 text-sm font-medium">{v.version_string}{v.is_current && <Badge variant="success">Current</Badge>}</span>
            <span className="flex items-center gap-2">
              {v.released_at && <span className="text-xs text-muted-foreground">{shortDate(v.released_at)}</span>}
              <Button size="icon-sm" variant="ghost" aria-label={`Delete version ${v.version_string}`} onClick={() => act.deleteVersion(v.id)}><X /></Button>
            </span>
          </li>
        ))}
      </ul>
      {adding && (
        <form onSubmit={submit} className="flex flex-wrap items-center gap-2 border-t pt-3">
          <Input aria-label="Version" className="min-w-32 flex-1" autoFocus placeholder="e.g. 1.2.0" value={text} onChange={(e) => setText(e.target.value)} />
          <Label className="flex items-center gap-1.5 text-xs"><Checkbox checked={current} onCheckedChange={(c) => setCurrent(c === true)} /> Current</Label>
          <Button type="submit" loading={act.busy === 'version'}>Add</Button>
          <Button type="button" variant="outline" onClick={() => setAdding(false)}>Cancel</Button>
        </form>
      )}
    </Card>
  );
}

function AccessCard({ data, act }: { data: ProductDetail; act: ReturnType<typeof useProductActions> }) {
  const allocated = data.members.filter((m) => m.allocated).length;
  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Allocated members</h2>
        <Badge>{allocated}</Badge>
      </div>
      <p className="text-sm text-muted-foreground">Owners and admins have access to all products. Other members need explicit allocation.</p>
      <ul className="divide-y">
        {data.members.map((m) => (
          <li key={m.id} className="flex items-center justify-between gap-3 py-2">
            <div className="flex min-w-0 items-center gap-3">
              <Avatar name={m.name || m.username} />
              <div className="min-w-0"><div className="truncate text-sm font-medium">{m.name}</div><div className="truncate text-xs text-muted-foreground">{m.email}</div></div>
            </div>
            {m.allocated ? (
              m.is_you ? <Badge variant="success">You</Badge> : <Button size="sm" variant="ghost" className="text-destructive" disabled={act.busy === 'access'} onClick={() => act.unallocate(m.id)}>Remove</Button>
            ) : (
              <Button size="sm" variant="outline" disabled={act.busy === 'access'} onClick={() => act.allocate(m.id)}>Allocate</Button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function ProductDetailPage() {
  const { pk } = useParams();
  const id = Number(pk);
  const q = useProductDetail(id);
  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <Card className="p-8 text-center">
        <p className="text-sm">{missing ? 'Product not found.' : 'Couldn’t load this product.'}</p>
        <Link to="/products/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to products</Link>
      </Card>
    );
  }
  if (!q.data) return <div className="space-y-3" data-testid="product-loading"><Skeleton className="h-8 w-64" /><Skeleton className="h-40 w-full" /></div>;
  return <Detail data={q.data} />;
}

function Detail({ data }: { data: ProductDetail }) {
  const p = data.product;
  const navigate = useNavigate();
  const act = useProductActions(p.id);
  const [confirmDelete, setConfirmDelete] = useState(false);
  useEffect(() => {
    document.title = `${p.name} — PQ Platform`;
  }, [p.name]);

  // "Manage keys" on the docs page links here with #api-key-list.
  useEffect(() => {
    if (window.location.hash === '#api-key-list') document.getElementById('api-key-list')?.scrollIntoView();
  }, []);

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: 'Products', href: '/products/' }, { label: p.name }]} />

      <Card className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold">{p.name}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{p.slug} · created {shortDate(p.created_at)} · {p.default_environment.charAt(0).toUpperCase() + p.default_environment.slice(1)}</p>
          </div>
          {data.is_admin && (
            <div className="flex gap-1">
              <Button asChild variant="ghost" size="icon" aria-label="Edit"><Link to={`/products/${p.id}/edit/`}><Pencil /></Link></Button>
              <Button variant="ghost" size="icon" aria-label="Delete" className="text-destructive" onClick={() => setConfirmDelete(true)}><Trash2 /></Button>
            </div>
          )}
        </div>
        {p.description && <p className="mt-4 border-t pt-4 text-sm text-muted-foreground">{p.description}</p>}
      </Card>

      <MilestoneFlow
        milestones={data.milestones}
        productName={p.name}
        busy={act.busy === 'milestone'}
        onAdd={act.addMilestone}
        onToggle={act.toggleMilestone}
        onDelete={act.deleteMilestone}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Open errors" value={p.counts.errors} tone="text-destructive" foot={<Link to={`/products/${p.id}/errors/`} className="text-primary hover:underline">Review errors →</Link>} />
        <Stat label="Open tickets" value={p.counts.tickets} tone="text-warning" foot={<Link to={`/products/${p.id}/tickets/`} className="text-primary hover:underline">Open board →</Link>} />
        <Stat label="Surveys" value={p.counts.surveys} tone="text-success" foot={<a href={`/products/${p.id}/surveys/`} className="text-primary hover:underline">Manage surveys →</a>} />
        <Stat label="Versions" value={p.counts.versions} tone="text-info" foot={<span className="text-muted-foreground">releases tracked</span>} />
      </div>

      <h2 className="text-base font-semibold">Configuration</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Discord webhook</h3>
            {data.is_admin && <Button asChild size="sm" variant="outline"><Link to={`/products/${p.id}/edit/`}>{p.webhook_configured ? 'Edit' : 'Add'}</Link></Button>}
          </div>
          {p.webhook_configured ? (
            <>
              <div className="flex items-center justify-between"><Badge variant="success" dot>Connected</Badge><span className="font-mono tracking-widest text-muted-foreground">••••••••••••••••</span></div>
              <p className="text-xs text-muted-foreground">Events are posted to your Discord channel as they happen.</p>
            </>
          ) : (
            <>
              <Badge dot>Not configured</Badge>
              <p className="text-xs text-muted-foreground">Get notified about tickets, errors, and feedback in Discord.</p>
            </>
          )}
        </Card>
        <VersionsCard data={data} act={act} />
      </div>

      <h2 className="text-base font-semibold">API keys</h2>
      <KeysCard data={data} act={act} />

      {data.is_admin && (
        <>
          <h2 className="text-base font-semibold">Team access</h2>
          <AccessCard data={data} act={act} />
        </>
      )}

      <AlertDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        destructive
        title={`Delete ${p.name}?`}
        description="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={async () => {
          if (await act.remove()) navigate('/products/');
        }}
      />
    </div>
  );
}

