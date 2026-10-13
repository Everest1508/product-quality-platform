import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const toggleVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium outline-none transition-all duration-200 focus-visible:ring-2 focus-visible:ring-ring/50 active:scale-95 disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4',
  {
    variants: {
      variant: {
        default: 'text-muted-foreground hover:bg-secondary hover:text-foreground aria-pressed:bg-accent aria-pressed:text-accent-foreground',
        outline: 'border text-muted-foreground hover:bg-secondary hover:text-foreground aria-pressed:border-primary aria-pressed:bg-accent aria-pressed:text-accent-foreground',
      },
      size: { sm: 'h-8 px-2.5', md: 'h-9 px-3', icon: 'size-9' },
    },
    defaultVariants: { variant: 'default', size: 'md' },
  },
);

export interface ToggleProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'>, VariantProps<typeof toggleVariants> {
  pressed: boolean;
  onPressedChange: (pressed: boolean) => void;
}

/** Two-state button for bold, favourite, mute and similar. Announces its state with aria-pressed. */
export function Toggle({ pressed, onPressedChange, variant, size, className, ...props }: ToggleProps) {
  return (
    <button type="button" aria-pressed={pressed} onClick={() => onPressedChange(!pressed)} className={cn(toggleVariants({ variant, size }), className)} {...props} />
  );
}
