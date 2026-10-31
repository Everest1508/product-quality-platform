# Pattern library — layouts by screen type

For each screen type, several proven layouts. Pick by the job, the users and the content — not by habit. When proposing directions, different directions may use different patterns, not just different colours.

---

## Dashboards & home screens

| Pattern | Shape | Best for | Watch out |
|---|---|---|---|
| **KPI strip + detail** | 3–4 headline numbers on top, one main chart/table below, secondary list on the side | Managers checking status | Don't let the strip grow past 4–5 |
| **My day** | Greeting + the user's own tasks/next actions first, team/status below | Personal home screens for staff (HR, CRM, service) | Keep personal and team clearly separated |
| **Command center** | One large live view (map, line, floor plan, status grid) + alarms rail + small KPIs | Monitoring, ops, energy/IoT, logistics | Alarms must dominate when active |
| **Bento grid** | Tiles of varied sizes on a grid; size = importance | Overview with many different kinds of info | Every tile needs a reason; avoid equal-size tile soup |
| **Feed / inbox** | Chronological or priority-sorted list of items needing action | Approvals, tickets, notifications, activity | Clear unread/priority states; bulk actions |
| **Split list-detail** | List left, selected item detail right | Triage, review, CRM leads, support | Keep list visible on desktop; stack on mobile |
| **Report / narrative** | Headline sentence → key numbers → explained charts, top to bottom | Weekly/monthly reports, owners and execs | Each chart answers one stated question |
| **Role-based home** | Same shell, different first section per role | Apps with clear roles (admin/manager/staff) | Re-check every role after changes |

## Navigation

| Pattern | Best for | Notes |
|---|---|---|
| **Sidebar** (collapsible) | Apps with 6+ sections, desktop-heavy | Group items; icon + label; collapse to icons; current page obvious |
| **Top nav** | 3–6 sections, content-heavy or public | Leaves full width for content |
| **Bottom tab bar** | Mobile apps, 3–5 main destinations | Labels under icons; one primary action may sit centre |
| **Command palette** (Ctrl/Cmd+K) | Power users, many destinations/actions | Complements, never replaces, visible nav |
| **Tabs** | Sibling views of one object | 2–7 tabs; show counts/status per tab |
| **Segmented control** | Switching a view's mode (list/board, day/week) | Not for navigation between pages |
| **Breadcrumbs** | Deep hierarchies (settings, file trees, catalogues) | Last item is the current page, not a link |
| **Stepper** | Linear multi-step tasks | Show step names, allow going back |

## Lists & collections

| Pattern | Best for |
|---|---|
| **Dense table** | Many rows, comparing values, sorting/filtering (orders, inventory, payroll) |
| **Card list** | Few fields per item with an image or status (people, products, properties) |
| **Kanban board** | Items moving through stages (tickets, leads, jobs, hiring) |
| **Timeline** | Events over time (history, audit, shipment tracking) |
| **Calendar / schedule** | Time-slot work (bookings, shifts, leave, rooms) |
| **Gallery / grid** | Visual items (menu items, products, media) |
| **Tree / nested list** | Hierarchies (accounts, BOMs, org charts, folders) |
| **Grouped list** | Items by category/date with sticky group headers |

Table extras: sticky header, column chooser, saved views, row density toggle, inline edit, bulk select, right-aligned numbers, frozen first column on mobile or card fallback.

## Detail pages

| Pattern | Best for |
|---|---|
| **Header + tabs** | Rich objects (customer, employee, project): summary header, tabs for areas |
| **Summary sidebar** | Main content left, key facts/actions in a sticky right column |
| **Activity-led** | Record whose history matters (ticket, deal): timeline is the main column |
| **Document-like** | Invoices, contracts, reports: looks like the printable result |

## Forms & data entry

| Pattern | Best for |
|---|---|
| **Single page, sections + index** | Long forms filled in one sitting by staff |
| **Wizard / stepper** | Occasional users, branching logic, high-stakes submissions |
| **Inline edit** | Editing one or two fields on a detail page |
| **Drawer form** | Creating/editing without losing the list context |
| **Modal quick-add** | Small creates (≤ 5 fields) from anywhere |
| **Spreadsheet grid entry** | Many similar rows (line items, attendance, stock counts) |
| **Conversational / one-question-per-screen** | Mobile, public onboarding, low-literacy audiences |

## Settings

Left sub-nav of categories + right content; each setting = label, short explanation, control, saved state. Group danger zone at the bottom, separated. Search for large settings areas.

## Onboarding & empty states

- **Empty state types** — first use (explain value + one action), no results (show the query, suggest a fix, clear filters), cleared/done (celebrate quietly), error (what happened + retry), no permission (who can grant it).
- **Onboarding** — checklist of 3–5 setup steps with progress; sample data option; contextual tips at the moment they're needed, not a tour up front.

## Feedback & status

Toast (non-blocking confirmations) · inline message (field/section level) · banner (page-wide state: offline, trial, maintenance) · skeletons for loading layout · progress for long jobs with time estimate · undo instead of "Are you sure?" where possible.

## Search & filter

Global search with recent items · filter chips above lists · faceted sidebar for large catalogues · saved views/segments · "N results" with clear filters link.

## Mobile

Bottom tab bar · one column · sticky bottom primary action · swipe actions on list rows (with visible alternative) · bottom sheets for options · large touch targets · inputs that trigger the right keyboard.
