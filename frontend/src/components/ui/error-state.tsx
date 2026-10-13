import { Button } from './button';
import { Card } from './card';

// What a page shows when its data could not be loaded: say so, offer a retry.
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card role="alert" className="flex flex-col items-center gap-3 px-6 py-8 text-center">
      <p className="text-sm">{message}</p>
      {onRetry && <Button size="sm" variant="outline" onClick={onRetry}>Try again</Button>}
    </Card>
  );
}
