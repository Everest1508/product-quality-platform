import { CalendarDays, Clock, Package, Plus, Ticket } from 'lucide-react';
import { useBootstrapData } from '@/lib/bootstrap';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export function NewMenu() {
  const { urls, is_admin } = useBootstrapData();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground outline-none hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring/50">
        <Plus className="size-4" />
        <span className="max-sm:hidden">New</span>
        <span className="sr-only sm:hidden">New</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuItem asChild><a href={urls.ticket_create}><Ticket /> New ticket</a></DropdownMenuItem>
        <DropdownMenuItem asChild><a href={urls.leave_apply}><CalendarDays /> Request leave</a></DropdownMenuItem>
        <DropdownMenuItem asChild><a href={urls.correction_request}><Clock /> Request a correction</a></DropdownMenuItem>
        {is_admin && <DropdownMenuItem asChild><a href={urls.product_create}><Package /> New product</a></DropdownMenuItem>}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
