import { ChevronDown, LogOut, Settings } from 'lucide-react';
import { useBootstrapData } from '@/lib/bootstrap';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export function AccountMenu() {
  const { user, urls, csrf } = useBootstrapData();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account menu" className="flex h-9 items-center gap-2 rounded-md px-1.5 outline-none hover:bg-secondary focus-visible:ring-2 focus-visible:ring-ring/40">
        <span className="grid size-7 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">{user.initial}</span>
        <span className="flex flex-col text-left leading-tight max-md:hidden">
          <span className="text-sm font-medium">{user.name}</span>
          <span className="text-[11px] text-muted-foreground">{user.role_label}</span>
        </span>
        <ChevronDown className="size-3.5 text-muted-foreground max-md:hidden" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuItem asChild><a href={urls.profile}><Settings /> Settings</a></DropdownMenuItem>
        {/* A real form post, so signing out works without JavaScript. */}
        <form method="post" action={urls.logout}>
          <input type="hidden" name="csrfmiddlewaretoken" value={csrf} />
          <DropdownMenuItem asChild onSelect={(e) => e.preventDefault()}>
            <button type="submit" className="w-full"><LogOut /> Sign out</button>
          </DropdownMenuItem>
        </form>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
