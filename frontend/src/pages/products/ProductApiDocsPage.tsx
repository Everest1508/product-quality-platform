import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api';
import { ago } from '@/lib/time';
import { cn } from '@/lib/utils';
import { KeyState } from './ProductDetailPage';
import { useApiDocs } from './useProducts';

const LANGS: [string, string][] = [['curl', 'curl'], ['python', 'Python'], ['javascript', 'JavaScript'], ['php', 'PHP']];
const METHOD = { GET: 'bg-info/15 text-info', POST: 'bg-success/15 text-success', PATCH: 'bg-warning/15 text-warning' } as Record<string, string>;

const readLang = () => {
  try {
    return localStorage.getItem('pqApiLang') || 'curl';
  } catch {
    return 'curl';
  }
};

export function ProductApiDocsPage() {
  const { pk } = useParams();
  const id = Number(pk);
  const q = useApiDocs(id);
  const [lang, setLang] = useState(readLang);
  const [copied, setCopied] = useState('');
  useEffect(() => {
    document.title = `API — ${q.data?.product.name ?? 'Product'} — PQ Platform`;
  }, [q.data?.product.name]);

  const pick = (l: string) => {
    setLang(l);
    try {
      localStorage.setItem('pqApiLang', l);
    } catch {
      /* private mode: the choice just is not remembered */
    }
  };
  const copy = (id: string, text: string) => navigator.clipboard.writeText(text).then(() => { setCopied(id); setTimeout(() => setCopied(''), 1800); });

  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <Card className="p-8 text-center">
        <p className="text-sm">{missing ? 'Product not found.' : 'Couldn’t load the API docs.'}</p>
        <Link to="/products/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to products</Link>
      </Card>
    );
  }
  if (!q.data) return <div className="space-y-3" data-testid="docs-loading"><Skeleton className="h-8 w-64" /><Skeleton className="h-48 w-full" /></div>;
  const d = q.data;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link to="/products/" className="hover:text-foreground">Products</Link><span>/</span>
        <Link to={`/products/${d.product.id}/`} className="hover:text-foreground">{d.product.name}</Link><span>/</span>
        <span className="font-medium text-foreground">API</span>
      </nav>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Send data to {d.product.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">Report errors, collect feedback and open tickets from your own app with one key and a few lines of code.</p>
        </div>
        <Button asChild size="sm" variant="outline"><Link to={`/products/${d.product.id}/#api-key-list`}>Manage keys</Link></Button>
      </div>

      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">Start in three steps</h2>
        <ol className="list-decimal space-y-1.5 pl-5 text-sm">
          <li><b>Make a key.</b> Keys belong to one product. {d.can_manage_keys ? <><Link to={`/products/${d.product.id}/#api-key-list`} className="text-primary hover:underline">Create one</Link> on the product page.</> : 'Ask an owner, admin or developer for one.'} It is shown once.</li>
          <li><b>Send a request.</b> Put the key in an <code>Authorization: Bearer</code> header and POST JSON to <code>{d.base_url}api/v1/errors/capture/</code>.</li>
          <li><b>Look in <Link to={`/products/${d.product.id}/errors/`} className="text-primary hover:underline">Errors</Link>.</b> It appears within a second, grouped with matching errors.</li>
        </ol>
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-muted-foreground">Base URL</dt><dd><code>{d.base_url}api/v1/</code></dd></div>
          <div><dt className="text-xs text-muted-foreground">Authentication</dt><dd><code>Authorization: Bearer YOUR_API_KEY</code></dd></div>
          <div><dt className="text-xs text-muted-foreground">Format</dt><dd>JSON in, JSON out</dd></div>
          <div><dt className="text-xs text-muted-foreground">Limit</dt><dd>600 requests a minute per key</dd></div>
        </dl>
        <p className="text-xs text-muted-foreground">Use <code>https</code> in production. Never put a key in front-end code that anyone can read. Send from your server, or use a key you are happy to rotate.</p>
      </Card>

      <div role="tablist" aria-label="Language" className="flex w-fit rounded-lg bg-secondary p-0.5">
        {LANGS.map(([v, l]) => (
          <button key={v} type="button" role="tab" aria-selected={lang === v} onClick={() => pick(v)} className={cn('rounded-md px-3 py-1 text-sm', lang === v ? 'bg-card font-medium shadow-sm' : 'text-muted-foreground hover:text-foreground')}>{l}</button>
        ))}
      </div>

      {d.endpoints.map((e) => {
        const code = e.snippets[lang] ?? e.snippets.curl ?? '';
        const cid = `${e.key}-${lang}`;
        return (
          <Card key={e.key} id={e.key} className="space-y-3 p-5">
            <div className="flex items-center gap-2"><span className={cn('rounded px-2 py-0.5 text-xs font-bold', METHOD[e.method] ?? 'bg-secondary')}>{e.method}</span><code className="text-sm">{e.path}</code></div>
            <h2 className="font-semibold">{e.title}</h2>
            <p className="text-sm text-muted-foreground">{e.summary}</p>
            {e.fields.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="py-1.5 pr-3 font-medium">Field</th><th className="pr-3 font-medium">Type</th><th className="pr-3 font-medium">Required</th><th className="font-medium">What it is</th></tr></thead>
                  <tbody>
                    {e.fields.map((f) => (
                      <tr key={f.name} className="border-b last:border-0 align-top">
                        <td className="py-1.5 pr-3"><code>{f.name}</code></td>
                        <td className="pr-3">{f.type}{f.limits && <div className="text-xs text-muted-foreground">{f.limits}</div>}</td>
                        <td className="pr-3">{f.required ? <b>Yes</b> : 'No'}</td>
                        <td>{f.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="relative">
              <Button size="sm" variant="outline" className="absolute right-2 top-2" onClick={() => copy(cid, code)}><Copy /> {copied === cid ? 'Copied' : 'Copy'}</Button>
              <pre className="overflow-x-auto rounded-md bg-neutral-900 p-4 pt-12 text-xs text-neutral-100"><code>{code}</code></pre>
            </div>
            <div><div className="mb-1 text-xs font-medium text-muted-foreground">Response</div><pre className="overflow-x-auto rounded-md bg-secondary p-3 text-xs"><code>{e.response}</code></pre></div>
            {e.notes.map((n) => <p key={n} className="text-sm text-muted-foreground">{n}</p>)}
          </Card>
        );
      })}

      <Card className="space-y-2 p-5">
        <h2 className="font-semibold">If something goes wrong</h2>
        <table className="w-full text-sm"><tbody>{d.error_codes.map(([code, text]) => <tr key={code} className="border-b last:border-0"><td className="py-1.5 pr-3 align-top"><code>{code}</code></td><td>{text}</td></tr>)}</tbody></table>
      </Card>

      <Card className="space-y-2 p-5">
        <h2 className="font-semibold">Keys for this product</h2>
        {d.keys.length === 0 && <p className="text-sm text-muted-foreground">No keys yet.</p>}
        {d.keys.map((k) => (
          <div key={k.id} className="flex flex-wrap items-center gap-2 text-sm">
            <code>{k.prefix}...</code><span>{k.name}</span><KeyState k={k} />
            <span className="text-xs text-muted-foreground">{k.last_used_at ? `used ${ago(k.last_used_at)}` : 'never used'}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}
