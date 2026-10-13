# befui: what this app needed that befui does not have

befui is not on npm; components are copied from its registry with `scripts/befui_add.py <name>` (it skips files that exist, `--force` overwrites, and prints the npm packages to install). These are the local patches and gaps we hit, written as suggestions for upstream.

## Local patches to befui files

| File | Change | Why |
| --- | --- | --- |
| `sidebar.tsx` | `SidebarItem` takes `to` (router `Link`) next to `href` | `href` is a full-page load, which throws away the SPA state on every click |
| `breadcrumb.tsx` | Items with `href` render a router `Link` | same |
| `empty-state.tsx` | `description` is `ReactNode`, not `string` | empty states carry links ("set a salary in Payroll setup") |
| `segmented.tsx` | options accept `ariaLabel` and `title` | icon-only options (grid/table, light/dark) need a name |
| `command.tsx` | `CommandDialog` takes `shouldFilter` | results come from the server, cmdk must not filter them again |

## Components worth adding to befui

1. **PageHeader** (title, one line of context, actions, optional count). Every page of this app opens with one; ours is `components/ui/page-header.tsx`.
2. **FilterTabs / link Tabs**: `Tabs` whose triggers are router links (`<TabsTrigger asChild><Link/></TabsTrigger>` works today, but a documented `to` prop would be nicer) and that can show a count.
3. **MonthCalendar grid** with per-day entries, holidays and a today marker. The leave calendar and attendance month are both hand-built.
4. **DataTable server mode**: controlled sorting, pagination and selection driven by URL params (the lists here all filter on the server).
5. **ConfirmDialog** wrapper over AlertDialog (title, body, destructive button, loading state): used for every delete.
6. **MoneyCell / NumericCell**: right-aligned, tabular figures, negative in red, currency prefix (payroll, timesheet).
7. **Kanban** that supports server-confirmed moves (optimistic, roll back on failure) and a selecting mode; our ticket board has both.
8. **Textarea and Field** (label, hint, error, required) as one component; forms here repeat `label > Input + error` dozens of times.
9. **Toaster with a `toast(text, tag)` function form**, matching how API hooks call it.

## Added in the second pass

- `date-picker.tsx` takes `aria-label` (the trigger needs a name when no label points at it).
- App glue, not patches: `date-field.tsx` converts ISO strings to the pickers' `Date`. An ISO-string `value`/`onChange` variant of DatePicker, and a DateTimePicker (date + time in one value), would remove it. befui has no `date-time-picker`.
- BarChart has one colour and no per-bar tone; our hours-this-week and score charts need per-bar colours.
- Sparkline needs `data: number[]`; a server that already draws the polyline cannot use it.
