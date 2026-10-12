import { Menu } from 'lucide-react';
import { useBootstrapData } from '@/lib/bootstrap';
import { Bell } from './Bell';
import { PresenceMenu } from './PresenceMenu';

type Props = { onOpenNav(): void; changelogOpen: boolean; onChangelogOpenChange(open: boolean): void };

export function Topbar({ onOpenNav }: Props) {
  const b = useBootstrapData();
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-card px-4">
      <button type="button" aria-label="Open navigation" onClick={onOpenNav} className="grid size-9 place-items-center rounded-md hover:bg-secondary md:hidden">
        <Menu className="size-5" />
      </button>
      <span className="truncate text-sm font-semibold">{b.company.name}</span>
      <div className="ml-auto flex items-center gap-2">
        <PresenceMenu />
        <Bell />
      </div>
    </header>
  );
}
