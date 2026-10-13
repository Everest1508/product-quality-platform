import { Link } from 'react-router-dom';
import { CompassIcon, HomeIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';

// A lost page or a crashed one: say it plainly and give one way back.
export function NotFound({ title = 'We couldn’t find that page', detail = 'The link may be old, or the page was moved. Nothing is wrong with your account.' }: { title?: string; detail?: string }) {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center gap-4 py-20 text-center">
      <span className="grid size-16 place-items-center rounded-full bg-secondary text-muted-foreground motion-safe:animate-[float_6s_ease-in-out_infinite] [&_svg]:size-8"><CompassIcon /></span>
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">{detail}</p>
      </div>
      <Button asChild><Link to="/dashboards/"><HomeIcon />Back to Home</Link></Button>
      <p className="text-xs text-muted-foreground">Tip: press <kbd className="rounded border px-1 font-mono">/</kbd> to search for it.</p>
    </div>
  );
}
