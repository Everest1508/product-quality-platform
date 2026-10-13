import * as React from 'react';
import * as AvatarPrimitive from '@radix-ui/react-avatar';
import { cn } from '@/lib/utils';

const tones = [
  'bg-blue-500/15 text-blue-600 dark:text-blue-300',
  'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300',
  'bg-violet-500/15 text-violet-600 dark:text-violet-300',
  'bg-amber-500/15 text-amber-600 dark:text-amber-300',
  'bg-rose-500/15 text-rose-600 dark:text-rose-300',
  'bg-cyan-500/15 text-cyan-600 dark:text-cyan-300',
];

function toneFor(name: string) {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return tones[h % tones.length];
}

const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join('');

const sizes = { xs: 'size-6 text-[10px]', sm: 'size-8 text-xs', md: 'size-10 text-sm', lg: 'size-14 text-lg', xl: 'size-20 text-2xl' };
const dots = { xs: 'size-2', sm: 'size-2.5', md: 'size-3', lg: 'size-3.5', xl: 'size-4' };
const presence = { online: 'bg-success', away: 'bg-warning', busy: 'bg-destructive', offline: 'bg-muted-foreground/50' };
export type AvatarStatus = keyof typeof presence;

/**
 * Shows the image when it loads, otherwise colored initials derived from `name`.
 * `shape="square"` for workspaces and brands, `status` adds a presence dot (online, away, busy, offline).
 */
export function Avatar({
  name,
  src,
  size = 'sm',
  shape = 'circle',
  status,
  className,
}: {
  name: string;
  src?: string;
  size?: keyof typeof sizes;
  shape?: 'circle' | 'square';
  status?: AvatarStatus;
  className?: string;
}) {
  const root = (
    <AvatarPrimitive.Root
      className={cn('inline-flex shrink-0 select-none overflow-hidden font-semibold', shape === 'circle' ? 'rounded-full' : 'rounded-[22%]', sizes[size], className)}
    >
      {src && <AvatarPrimitive.Image src={src} alt={name} className="size-full object-cover" />}
      <AvatarPrimitive.Fallback className={cn('grid size-full place-items-center', toneFor(name))}>
        {initials(name)}
      </AvatarPrimitive.Fallback>
    </AvatarPrimitive.Root>
  );
  if (!status) return root;
  return (
    <span className="relative inline-flex shrink-0">
      {root}
      <span role="img" aria-label={status} className={cn('absolute bottom-0 right-0 rounded-full ring-2 ring-background', dots[size], presence[status], shape === 'square' && '-bottom-0.5 -right-0.5')} />
    </span>
  );
}

/** Overlapping stack. Hover an avatar for its name; the +N chip lists everyone hidden. */
export function AvatarGroup({ names, max = 4, size = 'sm', shape = 'circle' }: { names: string[]; max?: number; size?: keyof typeof sizes; shape?: 'circle' | 'square' }) {
  const shown = names.slice(0, max);
  const hidden = names.slice(max);
  return (
    <div className="flex -space-x-2">
      {shown.map((n) => (
        <span key={n} title={n} className="inline-flex"><Avatar name={n} size={size} shape={shape} className="ring-2 ring-background" /></span>
      ))}
      {hidden.length > 0 && (
        <span title={hidden.join(', ')} className={cn('grid place-items-center bg-secondary font-semibold text-muted-foreground ring-2 ring-background', shape === 'circle' ? 'rounded-full' : 'rounded-[22%]', sizes[size])}>
          +{hidden.length}
        </span>
      )}
    </div>
  );
}

/** Avatar with a name and a second line (role, email, team). Use it in table cells, menus and headers. */
export function UserInfo({ name, subtitle, src, size = 'sm', status, className }: { name: string; subtitle?: React.ReactNode; src?: string; size?: keyof typeof sizes; status?: AvatarStatus; className?: string }) {
  return (
    <div className={cn('flex min-w-0 items-center gap-2.5', className)}>
      <Avatar name={name} src={src} size={size} status={status} />
      <div className="grid min-w-0 leading-tight">
        <span className="truncate text-[13px] font-medium">{name}</span>
        {subtitle && <span className="truncate text-xs text-muted-foreground">{subtitle}</span>}
      </div>
    </div>
  );
}
