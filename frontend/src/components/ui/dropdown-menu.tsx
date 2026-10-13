import * as React from 'react';
import * as M from '@radix-ui/react-dropdown-menu';
import { CheckIcon } from './icons';
import { cn } from '@/lib/utils';

export const DropdownMenu = M.Root;
export const DropdownMenuTrigger = M.Trigger;
export const DropdownMenuGroup = M.Group;

export const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof M.Content>,
  React.ComponentPropsWithoutRef<typeof M.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <M.Portal>
    <M.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        'z-50 min-w-[10rem] overflow-hidden rounded-lg border bg-popover p-1 text-popover-foreground shadow-lg animate-pop',
        className,
      )}
      {...props}
    />
  </M.Portal>
));
DropdownMenuContent.displayName = 'DropdownMenuContent';

export const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof M.Item>,
  React.ComponentPropsWithoutRef<typeof M.Item> & { destructive?: boolean }
>(({ className, destructive, ...props }, ref) => (
  <M.Item
    ref={ref}
    className={cn(
      'relative flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 text-[13px] outline-none data-[disabled]:opacity-50 data-[highlighted]:bg-secondary [&_svg]:size-4 [&_svg]:text-muted-foreground',
      destructive && 'text-destructive data-[highlighted]:bg-destructive/10 [&_svg]:text-destructive',
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = 'DropdownMenuItem';

export const DropdownMenuCheckboxItem = React.forwardRef<
  React.ElementRef<typeof M.CheckboxItem>,
  React.ComponentPropsWithoutRef<typeof M.CheckboxItem>
>(({ className, children, ...props }, ref) => (
  <M.CheckboxItem
    ref={ref}
    className={cn('relative flex cursor-pointer select-none items-center rounded-md py-1.5 pl-8 pr-2 text-[13px] outline-none data-[highlighted]:bg-secondary', className)}
    {...props}
  >
    <span className="absolute left-2 grid size-4 place-items-center">
      <M.ItemIndicator>
        <CheckIcon className="size-3.5 text-primary" strokeWidth={3} />
      </M.ItemIndicator>
    </span>
    {children}
  </M.CheckboxItem>
));
DropdownMenuCheckboxItem.displayName = 'DropdownMenuCheckboxItem';

export const DropdownMenuLabel = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof M.Label>) => (
  <M.Label className={cn('px-2 py-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground', className)} {...props} />
);
export const DropdownMenuSeparator = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof M.Separator>) => (
  <M.Separator className={cn('-mx-1 my-1 h-px bg-border', className)} {...props} />
);
export const DropdownMenuShortcut = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => (
  <span className={cn('ml-auto pl-4 font-mono text-[11px] text-muted-foreground', className)} {...props} />
);
