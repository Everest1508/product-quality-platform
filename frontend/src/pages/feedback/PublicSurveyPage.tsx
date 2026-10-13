import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useParams } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input, Textarea } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { usePublicSurvey } from './useFeedback';
import { Label } from '@/components/ui/label';
import { Segmented } from '@/components/ui/segmented';
import { SendIcon } from '@/components/ui/icons';

const QUESTION: Record<string, string> = {
  nps: 'How likely are you to recommend us to a friend?',
  csat: 'How satisfied are you with our product?',
  ces: 'How easy was it to use our product?',
};
const ENDS: Record<string, [string, string]> = { nps: ['Not likely', 'Very likely'], csat: ['Unsatisfied', 'Very satisfied'], ces: ['Difficult', 'Very easy'] };

type FieldErrors = Record<string, string[]>;

// Anyone with the link may answer while the survey is active: no login, no sidebar.
export function PublicSurveyPage() {
  const id = Number(useParams().id);
  const q = usePublicSurvey(id);
  const [score, setScore] = useState<number | null>(null);
  const [comment, setComment] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const sending = useRef(false);
  useEffect(() => {
    document.title = q.data?.name ?? 'Survey';
  }, [q.data?.name]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    if (score === null) return setErrors({ score: ['Choose a score.'] });
    sending.current = true;
    setSaving(true);
    setErrors({});
    try {
      await api.post(`public/surveys/${id}/`, { score, comment, contact_name: name, contact_email: email });
      setDone(true);
    } catch (err) {
      setErrors((err instanceof ApiError && (err.body as { errors?: FieldErrors } | undefined)?.errors) || { form: [err instanceof Error ? err.message : 'Could not send.'] });
      sending.current = false;
      setSaving(false);
    }
  };

  const shell = (children: React.ReactNode) => <div className="mx-auto my-10 max-w-lg px-4">{children}</div>;
  if (q.isError) {
    return shell(<Card className="p-8 text-center"><h1 className="font-semibold">This survey is not open</h1><p className="mt-1 text-sm text-muted-foreground">The link may be old, or the survey has been closed.</p></Card>);
  }
  if (!q.data) return shell(<Skeleton className="h-64 w-full" />);
  const s = q.data;
  if (done) {
    return shell(<Card className="p-8 text-center"><h1 className="text-lg font-semibold">Thank you!</h1><p className="mt-1 text-sm text-muted-foreground">Your response to “{s.name}” has been recorded.</p></Card>);
  }
  const [low, high] = ENDS[s.type] ?? ENDS.nps;

  return shell(
    <Card className="p-6 text-center">
      <h1 className="text-2xl font-semibold">{s.name}</h1>
      <p className="mb-5 text-sm text-muted-foreground">{s.product}</p>
      {s.description && <p className="mb-6 text-sm">{s.description}</p>}
      <form onSubmit={submit} className="space-y-4" noValidate>
        <fieldset>
          <legend className="mb-4 w-full text-sm font-medium">{QUESTION[s.type] ?? QUESTION.nps}</legend>
          <div aria-label="Score" role="radiogroup" className="flex justify-center">
            <Segmented className="flex-wrap justify-center" value={score === null || score === undefined ? '' : String(score)} onValueChange={(v) => setScore(Number(v))} options={s.scores.map((n) => ({ value: String(n), label: n }))} />
          </div>
          <div className="mt-2 flex justify-between text-xs text-muted-foreground"><span>{low}</span><span>{high}</span></div>
          {errors.score?.map((m) => <p key={m} className="mt-2 text-xs text-destructive">{m}</p>)}
        </fieldset>
        <div className="grid gap-1.5 text-left">
          <Label htmlFor="comment" className="text-sm font-medium">Comments (optional)</Label>
          <Textarea id="comment" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Tell us more..." />
        </div>
        <div className="grid gap-3 text-left sm:grid-cols-2">
          <div className="grid gap-1.5"><Label htmlFor="contact_name" className="text-sm font-medium">Name (optional)</Label><Input id="contact_name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" /></div>
          <div className="grid gap-1.5">
            <Label htmlFor="contact_email" className="text-sm font-medium">Email (optional)</Label>
            <Input id="contact_email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" aria-invalid={!!errors.contact_email} />
            {errors.contact_email?.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>)}
          </div>
        </div>
        {errors.form?.map((m) => <p key={m} className="text-sm text-destructive">{m}</p>)}
        <Button type="submit" className="w-full" loading={saving}><SendIcon />Submit Response</Button>
      </form>
    </Card>,
  );
}
