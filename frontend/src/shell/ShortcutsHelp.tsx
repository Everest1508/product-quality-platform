import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Kbd } from '@/components/ui/kbd';

const rows: [string[], string][] = [
  [['Ctrl', 'K'], 'Search everything (or press /)'],
  [['c'], 'New ticket'],
  [['j', 'k'], 'Next / previous ticket in a list or board'],
  [['Enter'], 'Open the highlighted ticket'],
  [['e'], 'Edit the highlighted ticket'],
  [['?'], 'Show this help'],
];

export function ShortcutsHelp({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby={undefined}>
        <DialogHeader><DialogTitle>Keyboard shortcuts</DialogTitle></DialogHeader>
        <ul className="grid gap-2 text-sm">
          {rows.map(([keys, label]) => (
            <li key={label} className="flex items-center justify-between gap-4">
              <span>{label}</span>
              <span className="flex gap-1">{keys.map((k) => <Kbd key={k}>{k}</Kbd>)}</span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
