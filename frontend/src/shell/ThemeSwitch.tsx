import { useState } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { Segmented } from '@/components/ui/segmented';
import { getTheme, setTheme, type Theme } from '@/lib/theme';

export function ThemeSwitch() {
  const [theme, set] = useState<Theme>(getTheme);
  return (
    <Segmented
      className="w-full [&>*]:flex-1"
      value={theme}
      onValueChange={(v) => { setTheme(v); set(v); }}
      options={[
        { value: 'light', label: <Sun />, ariaLabel: 'Light', title: 'Light' },
        { value: 'system', label: <Monitor />, ariaLabel: 'System', title: 'System' },
        { value: 'dark', label: <Moon />, ariaLabel: 'Dark', title: 'Dark' },
      ]}
    />
  );
}
