import { Kbd } from '@/components/ui/kbd';
import { shortcutGroups } from './shortcuts';

export function ShortcutList() {
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {shortcutGroups().map((g) => (
        <section key={g.title} className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{g.title}</h3>
          <ul className="grid gap-1.5 text-sm">
            {g.items.map((s) => (
              <li key={s.keys.join('+') + s.label} className="flex items-center justify-between gap-4">
                <span>{s.label}</span>
                <span className="flex items-center gap-1">
                  {s.keys.map((k, i) => (
                    <span key={k} className="flex items-center gap-1">
                      {i > 0 && <span className="text-[10px] text-muted-foreground">{s.then ? 'then' : '+'}</span>}
                      <Kbd>{k}</Kbd>
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
