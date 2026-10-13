import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ShortcutList } from './ShortcutList';

export function ShortcutsHelp({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby={undefined} className="max-w-2xl">
        <DialogHeader><DialogTitle>Keyboard shortcuts</DialogTitle></DialogHeader>
        <ShortcutList />
      </DialogContent>
    </Dialog>
  );
}
