import { Search } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useBootstrapData } from '@/lib/bootstrap';
import { useProductNav } from '@/lib/useProductNav';
import { Kbd } from '@/components/ui/kbd';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { AccountMenu } from './AccountMenu';
import { Bell } from './Bell';
import { NewMenu } from './NewMenu';
import { PresenceMenu } from './PresenceMenu';
import { Button } from '@/components/ui/button';

type Props = { onOpenPalette(): void };

export function Topbar({ onOpenPalette }: Props) {
  const b = useBootstrapData();
  const productNav = useProductNav(useLocation().pathname);
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-card px-4">
      <SidebarTrigger />
      <span className="truncate text-sm font-semibold">{productNav?.name ?? b.company.name}</span>
      <Button variant="outline" onClick={onOpenPalette} aria-label="Search" className="min-w-0 flex-1 justify-start gap-2 bg-muted px-3 font-normal text-muted-foreground md:max-w-md">
        <Search className="size-4 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-left max-sm:hidden">Search tickets, errors, products</span>
        <Kbd className="max-sm:hidden">Ctrl K</Kbd>
      </Button>
      <div className="ml-auto flex items-center gap-2">
        <NewMenu />
        <PresenceMenu />
        <Bell />
        <AccountMenu />
      </div>
    </header>
  );
}
