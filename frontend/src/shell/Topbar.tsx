import { Menu, Search } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useBootstrapData } from '@/lib/bootstrap';
import { useProductNav } from '@/lib/useProductNav';
import { Kbd } from '@/components/ui/kbd';
import { AccountMenu } from './AccountMenu';
import { Bell } from './Bell';
import { NewMenu } from './NewMenu';
import { PresenceMenu } from './PresenceMenu';

type Props = { onOpenNav(): void; onOpenPalette(): void };

export function Topbar({ onOpenNav, onOpenPalette }: Props) {
  const b = useBootstrapData();
  const productNav = useProductNav(useLocation().pathname);
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-card px-4">
      <button type="button" aria-label="Open navigation" onClick={onOpenNav} className="grid size-9 place-items-center rounded-md hover:bg-secondary md:hidden">
        <Menu className="size-5" />
      </button>
      <span className="truncate text-sm font-semibold">{productNav?.name ?? b.company.name}</span>
      <button
        type="button"
        onClick={onOpenPalette}
        aria-label="Search"
        className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-md border bg-muted px-3 text-left text-sm text-muted-foreground hover:bg-secondary md:max-w-md"
      >
        <Search className="size-4 shrink-0" />
        <span className="min-w-0 flex-1 truncate max-sm:hidden">Search tickets, errors, products</span>
        <Kbd className="max-sm:hidden">Ctrl K</Kbd>
      </button>
      <div className="ml-auto flex items-center gap-2">
        <NewMenu />
        <PresenceMenu />
        <Bell />
        <AccountMenu />
      </div>
    </header>
  );
}
