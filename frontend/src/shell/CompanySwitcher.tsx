import { Check, ChevronDown } from 'lucide-react';
import { api } from '@/lib/api';
import { useBootstrapData } from '@/lib/bootstrap';
import { toast } from '@/lib/toast';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export function CompanySwitcher({ collapsed }: { collapsed: boolean }) {
  const b = useBootstrapData();
  const switchTo = async (id: number) => {
    try {
      await api.post('company/switch/', { company_id: id });
      window.location.assign(b.urls.home);
    } catch {
      toast('Could not switch workspace.', 'error');
    }
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={b.company.name}
        className="flex w-full items-center gap-2 rounded-lg border bg-card px-2 py-2 text-left text-sm font-medium outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/40"
      >
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-accent text-xs font-semibold text-accent-foreground">
          {b.company.name.slice(0, 1).toUpperCase()}
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1 truncate">{b.company.name}</span>
            <ChevronDown className="size-3.5 text-muted-foreground" />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {b.workspaces.map((w) => (
          <DropdownMenuItem key={w.company_id} disabled={w.current} onSelect={() => !w.current && switchTo(w.company_id)}>
            <span className="min-w-0 flex-1 truncate">{w.name}</span>
            <span className="text-xs text-muted-foreground">{w.role_label}</span>
            {w.current && <Check className="size-4" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
