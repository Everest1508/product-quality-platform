import { CheckIcon, ChevronDownIcon } from '@/components/ui/icons';
import type { ProductNav } from '@/lib/useProductNav';
import { useSidebar } from '@/components/ui/sidebar';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export function ProductSwitcher({ nav }: { nav: ProductNav }) {
  const { collapsed } = useSidebar();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={nav.name}
        className="flex w-full items-center gap-2 rounded-lg border bg-muted px-2 py-1.5 text-left text-sm font-medium outline-none hover:bg-secondary focus-visible:ring-2 focus-visible:ring-ring/40"
      >
        <span className="grid size-5 shrink-0 place-items-center rounded bg-primary text-[11px] font-semibold text-primary-foreground">
          {nav.name.slice(0, 1).toUpperCase()}
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1 animate-in truncate">{nav.name}</span>
            <ChevronDownIcon className="size-3.5 text-muted-foreground" />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {nav.products.map((p) => (
          <DropdownMenuItem key={p.id} asChild>
            <a href={p.url}>
              <span className="min-w-0 flex-1 truncate">{p.name}</span>
              {p.id === nav.id && <CheckIcon />}
            </a>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <a href={nav.all_url}>View all products</a>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
