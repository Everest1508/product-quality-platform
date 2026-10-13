import { useState } from 'react';
import { MonitorIcon, MoonIcon, SunIcon } from '@/components/ui/icons';
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
        { value: 'light', label: <SunIcon />, ariaLabel: 'Light', title: 'Light' },
        { value: 'system', label: <MonitorIcon />, ariaLabel: 'System', title: 'System' },
        { value: 'dark', label: <MoonIcon />, ariaLabel: 'Dark', title: 'Dark' },
      ]}
    />
  );
}
