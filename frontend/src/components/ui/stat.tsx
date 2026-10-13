import type { ReactNode } from 'react';
import { Card } from './card';

export function Stat({ value, label, tone }: { value: ReactNode; label: ReactNode; tone?: 'danger' | 'success' }) {
  return (
    <Card className="p-4">
      <div className={`text-2xl font-semibold tabular-nums leading-tight ${tone === 'danger' ? 'text-destructive' : tone === 'success' ? 'text-success' : ''}`}>{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{label}</div>
    </Card>
  );
}
