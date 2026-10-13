import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const LOCALE = 'en-US'; // the calendar's own default (the trigger text uses en-GB)
const monthName = (y: number, m: number) => new Intl.DateTimeFormat(LOCALE, { month: 'long', year: 'numeric' }).format(new Date(y, m - 1, 1));
const dayLabel = (y: number, m: number, d: number) => new Intl.DateTimeFormat(LOCALE, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(y, m - 1, d));

/** Opens a DateField by its aria-label and clicks the day, paging months as needed. */
export async function pickDate(label: string | RegExp, iso: string) {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  await userEvent.click(screen.getByRole('button', { name: label }));
  for (let i = 0; i < 120 && !screen.queryByText(monthName(y, m)); i++) {
    const shown = screen.getByText(/^[A-Za-z]+ \d{4}$/).textContent!;
    const at = new Date(`1 ${shown}`);
    const forward = at.getFullYear() * 12 + at.getMonth() < y * 12 + (m - 1);
    await userEvent.click(screen.getByRole('button', { name: forward ? 'Next month' : 'Previous month' }));
  }
  await userEvent.click(screen.getByRole('button', { name: dayLabel(y, m, d) }));
}

/** Types an hour and a minute into a befui TimePicker (24-hour digits, the AM/PM segment is set from the hour). */
export async function pickTime(hh: number, mm: number) {
  const hour = screen.getByRole('spinbutton', { name: 'Hour' });
  hour.focus();
  await userEvent.keyboard(String(hh % 12 || 12).padStart(2, '0'));
  const minute = screen.getByRole('spinbutton', { name: 'Minute' });
  minute.focus();
  await userEvent.keyboard(String(mm).padStart(2, '0'));
  const ampm = screen.getByRole('spinbutton', { name: 'AM or PM' });
  if ((ampm.textContent === 'PM') !== hh >= 12) await userEvent.click(ampm);
}
