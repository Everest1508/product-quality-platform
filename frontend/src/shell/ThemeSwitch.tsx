import { useState } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { getTheme, setTheme, type Theme } from '@/lib/theme';

const OPTIONS: [Theme, string, typeof Sun][] = [['light', 'Light', Sun], ['system', 'System', Monitor], ['dark', 'Dark', Moon]];

export function ThemeSwitch() {
  const [theme, set] = useState<Theme>(getTheme);
  return (
    <div role="radiogroup" aria-label="Theme" className="flex gap-1 rounded-md bg-secondary p-0.5">
      {OPTIONS.map(([value, label, Icon]) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={theme === value}
          aria-label={label}
          title={label}
          onClick={() => { setTheme(value); set(value); }}
          className={`grid h-7 flex-1 place-items-center rounded-[5px] transition-colors ${theme === value ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  );
}
