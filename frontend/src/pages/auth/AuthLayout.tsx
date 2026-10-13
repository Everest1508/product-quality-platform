import type { ReactNode } from 'react';
import { ActivityIcon, ClockIcon, SearchIcon, TicketIcon } from '@/components/ui/icons';

const POINTS = [
  { icon: SearchIcon, title: 'Errors', text: 'Grouped by fingerprint, ranked by volume.' },
  { icon: TicketIcon, title: 'Tickets', text: 'Raised by hand or by rule, tied to the product.' },
  { icon: ClockIcon, title: 'Time', text: 'Attendance, leave and payroll from the same records.' },
];

// The pages a person sees before there is a workspace to show: sign-in, first-run setup, the desktop app's sign-in.
export function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center bg-secondary/40 p-4">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-2xl border bg-card shadow-lg md:grid-cols-2">
        <aside className="hidden flex-col justify-between bg-neutral-900 p-8 text-neutral-100 md:flex">
          <div>
            <div className="flex items-center gap-2 font-semibold"><ActivityIcon className="size-5" /> PQ Platform</div>
            <p className="mt-6 text-lg font-medium leading-snug">Errors, tickets, feedback, attendance and payroll — kept per product.</p>
          </div>
          <ul className="space-y-4 text-sm">
            {POINTS.map(({ icon: Icon, title: t, text }) => (
              <li key={t} className="flex gap-3"><Icon className="mt-0.5 size-4 shrink-0 opacity-70" /><span><b className="block">{t}</b><span className="opacity-70">{text}</span></span></li>
            ))}
          </ul>
        </aside>
        <section className="p-8">
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-6">{children}</div>
          {footer && <p className="mt-6 border-t pt-4 text-center text-xs text-muted-foreground">{footer}</p>}
        </section>
      </div>
    </main>
  );
}
