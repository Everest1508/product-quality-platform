import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeftIcon, CopyIcon, PlayIcon, TrashIcon } from '@/components/ui/icons';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api';
import { ago } from '@/lib/time';
import { cn } from '@/lib/utils';
import { useSurveyActions, useSurveyDetail } from './useFeedback';
import type { SurveyDetail } from './types';
import { StatCard } from '@/components/ui/stat-card';

const NEXT: Record<string, string> = { draft: 'Activate', active: 'Close', closed: 'Reopen' };

export function SurveyDetailPage() {
  const id = Number(useParams().id);
  const q = useSurveyDetail(id);
  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <Card className="p-8 text-center">
        <p className="text-sm">{missing ? 'Survey not found.' : 'Couldn’t load this survey.'}</p>
        <Button asChild variant="link" className="mt-3"><Link to="/feedback/"><ArrowLeftIcon /> Back to surveys</Link></Button>
      </Card>
    );
  }
  if (!q.data) return <div className="space-y-3" data-testid="survey-loading"><Skeleton className="h-8 w-64" /><Skeleton className="h-40 w-full" /></div>;
  return <Detail data={q.data} />;
}

function Detail({ data }: { data: SurveyDetail }) {
  const s = data.survey;
  const navigate = useNavigate();
  const act = useSurveyActions(s.id);
  const [confirm, setConfirm] = useState(false);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    document.title = `${s.name} — PQ Platform`;
  }, [s.name]);
  const link = `${window.location.origin}${s.public_path}`;
  const max = Math.max(1, ...data.distribution.map((d) => d.count));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{s.name} <span className="ml-2 text-sm font-normal text-muted-foreground">{s.response_count} response{s.response_count === 1 ? '' : 's'}</span></h1>
        <Button asChild variant="outline" size="sm"><Link to="/feedback/"><ArrowLeftIcon />Back to surveys</Link></Button>
      </div>
      <p className="text-sm text-muted-foreground">{s.product.name}{s.description ? ` · ${s.description}` : ''}</p>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard value={s.response_count} label="Responses" />
        <StatCard value={(s.type === 'nps' ? s.nps : s.avg_score) ?? '—'} label={s.type === 'nps' ? 'NPS Score' : 'Avg Score'} />
        <StatCard value={<Badge variant="info">{s.type_label}</Badge>} label="Type" />
        <StatCard value={<Badge variant={s.status === 'active' ? 'success' : s.status === 'draft' ? 'warning' : 'default'}>{s.status_label}</Badge>} label="Status" />
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Card className="min-w-64 flex-1 space-y-2 p-4">
          <div className="text-sm font-medium">Public link</div>
          <div className="flex gap-2">
            <Input readOnly aria-label="Public link" value={link} onFocus={(e) => e.currentTarget.select()} className="text-xs" />
            <Button variant="outline" onClick={() => navigator.clipboard.writeText(link).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); })}><CopyIcon /> {copied ? 'Copied!' : 'Copy'}</Button>
          </div>
          {s.status !== 'active' && <p className="text-xs text-muted-foreground">The link only works while the survey is active.</p>}
        </Card>
        <Button variant="outline" loading={act.busy === 'toggle'} onClick={() => act.toggle()}><PlayIcon />{NEXT[s.status]}</Button>
        <Button variant="destructive" onClick={() => setConfirm(true)}><TrashIcon />Delete</Button>
      </div>

      {s.type === 'nps' && (
        <Card className="space-y-3 p-5">
          <h2 className="text-sm font-medium">NPS distribution</h2>
          <div className="flex h-28 items-end gap-1" role="img" aria-label="Responses per score">
            {data.distribution.map((d) => (
              <div key={d.score} className="flex flex-1 flex-col items-center justify-end gap-1" title={`${d.score}: ${d.count}`}>
                <div className={cn('w-full rounded-t', d.score <= 6 ? 'bg-destructive' : d.score <= 8 ? 'bg-warning' : 'bg-success')} style={{ height: `${(d.count / max) * 100}%`, minHeight: d.count ? 4 : 0 }} />
                <span className="text-xs text-muted-foreground">{d.score}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-between text-xs text-muted-foreground"><span>Detractors (0-6)</span><span>Passives (7-8)</span><span>Promoters (9-10)</span></div>
        </Card>
      )}

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-medium">Recent responses</h2>
        {data.responses.length === 0 ? (
          <p className="py-5 text-center text-sm text-muted-foreground">No responses yet.</p>
        ) : (
          <ul className="divide-y">
            {data.responses.map((r) => (
              <li key={r.id} className="space-y-1 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className={cn('text-lg font-medium', s.type === 'nps' && (r.score >= 9 ? 'text-success' : r.score <= 6 ? 'text-destructive' : 'text-warning'))} title={r.label}>{r.score}</span>
                  {r.contact_name && <span className="text-sm">{r.contact_name}</span>}
                  <span className="text-xs text-muted-foreground">{ago(r.created_at)}</span>
                </div>
                {r.comment && <p className="text-sm text-muted-foreground">{r.comment}</p>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <AlertDialog
        open={confirm}
        onOpenChange={setConfirm}
        destructive
        title="Delete this survey?"
        description="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={async () => {
          if (await act.remove()) navigate('/feedback/');
        }}
      />
    </div>
  );
}
