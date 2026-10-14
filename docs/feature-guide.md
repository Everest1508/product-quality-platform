# Feature guide

What was added to PQ Platform, **when** it arrived, **why** it was added and **how to use** it. Each entry names the
release it came in with (version, name and date), so you can find the full notes in the [changelog](../CHANGELOG.md) or
the in-app **What's new** window. Earlier releases are in the [timeline](#release-timeline) at the end.

---

## 1.12.0 "Robin": a new look, dark mode and keyboard shortcuts (2026-10-14)

### A dark theme
- **Why:** the app is used all day, and a dark theme is easier on the eyes in the evening.
- **How:** open the account menu (your avatar, top right) and pick the sun, the monitor or the moon: light, match your system, or dark.
  Press **t** anywhere to flip it. The change fades in. Your choice is remembered in the browser.

### A redesigned Home
- **Why:** Home should open on what is yours today, not on company-wide numbers.
- **How:** a banner greets you by time of day and types out a line; below it are your numbers (open tickets, overdue, hours logged,
  hours worked), **Assigned / Due soon**, **Today** (punch in or out) and your **to-do** list, then this week, your leave and your DSR.
  Owners and admins also see a line of things waiting for them.

### Keyboard shortcuts
- **Why:** people who live in the app should not have to reach for the mouse.
- **How:** press **?** to see them all (also under **Profile → Keyboard shortcuts**). Press **g** then a letter to jump:
  **h** Home, **t** Tickets, **e** Errors, **p** Products, **d** DSR, **a** Attendance, **l** My leave, **r** Reports, **m** Team, **u** Profile.
  **t** switches the theme, **[** folds the sidebar, **c** makes a ticket. They show ⌘ on a Mac and Ctrl elsewhere and pause while you type.

### Search that can also do things
- **How:** press **Ctrl K** (**⌘ K** on a Mac) or **/**. Type "leave", "log" or "punch" and an **Actions** group offers to request leave, log work or open
  the punch clock. Results only ever include what you are allowed to open.

### On-time streak, milestones and small celebrations
- **Why:** friendly recognition makes the app feel less like a form.
- **How:** your **streak** is the number of working days in a row you checked in within the grace period; weekends, holidays and approved leave
  do not break it. It shows on Home and your profile from 2 days. A **milestone** line marks a work anniversary or a round number of resolved tickets.
  **Confetti** appears when you resolve a ticket or tick your last to-do, and the numbers on Home count up.

### Attendance reminders
- **Why:** forgotten check-outs cost people money.
- **How:** about 5 minutes after your shift starts you get a nudge if you have not checked in, and another after it ends if you have not checked out.
  Switch either off under **Profile → Notifications**. An admin has to schedule the command (see [Running the project](running-the-project.md#background-jobs)).

---

## 1.13.0 "Swift": a DSR that is one table (2026-10-14)

### One table of everything submitted
- **Why:** today and history were hard to read in separate views, and a spreadsheet look is what people expect.
- **How:** open **DSR**. Rows are grouped by day with the day's total (Date, Task, Project, Category, Time, Status). Switch between Today, Yesterday, 7 or 30
  days, search, and (owners and admins) pick a person or Everyone. The pencil edits a row and the bin deletes it (it asks first). **Log work** opens a small window.
  **Copy summary** puts a standup message on your clipboard. Members can edit today only; owners and admins can edit any past day.

### Export to a spreadsheet
- **How:** **Export CSV** on the DSR saves what you are looking at (range, person, search). Owners and admins can also export the **Timesheet** for a month and a **payroll run**.

### Suggestions and one-click catch-up
- **How:** a banner on today's DSR lists tickets you worked on that are not logged yet. **Add all** logs them at suggested hours; **Review** lets you change each time first.

### Honest hours for long-open tickets
- **Why:** a ticket open for weeks used to log weeks of hours (even about 1000) when it was resolved.
- **How:** a ticket open for less than a working day logs that time as before. A ticket open longer logs **0** counted time and shows "open for 11d 1h (not counted)".
  When you resolve it a message tells you to add the time you worked on it today, the DSR opens a small window for it, and a banner plus an **Add time** button
  stay until you enter it. Only the time you enter counts. Older rows keep their hours until an admin runs `python manage.py fix_dsr_hours --dry-run`, checks the list, then
  runs it without `--dry-run`: that moves those hours into the open-for time and stops them counting. That step is optional.

### Asking before it matters
- **How:** every delete (a DSR row, a product, a ticket, a rule) opens a small window that says what will go. Punching out says "You will be punched out for today" and shows your time worked so far.

---

## 1.14.0 "Tern": profile, team pages, lists and a calmer What's new (2026-10-14)

### A profile page
- **How:** account menu → **My profile**, or **g** then **u**. Tabs: **Overview** (numbers, milestones, recent activity), **Settings**, **Notifications**, **Keyboard shortcuts**.

### You choose what notifies you
- **How:** **Profile → Notifications** has a switch for each kind (mentions, comments, leave decisions, payslips, reminders). System messages cannot be turned off.
  The setting applies in every workspace you belong to.

### A page for each team member
- **How:** open **Team** and click a name. You see their role, streak, milestones and the open tickets of theirs that you are allowed to see. Only owners and admins see the email.

### Lists instead of cards
- **How:** **Products**, **Surveys**, **Automation rules** and **Team** are full-width strips with the numbers and actions on the same line; the stat rows on
  the Customer Success Hub and Reports are one divided sheet. A product's tickets open on the one ticket page.

### A one-column ticket page, with history
- **How:** status, priority, assignee and deadline sit in a strip at the top; below are the description, a **History** of status changes and assignments, and the comments (type **@** to mention someone).
  On the board, hover a card's title for a **peek**, use **Compact** to shrink the cards, and drag a card to move it (resolving one throws confetti and a toast).

### Notifications grouped by day
- **How:** open the bell, or **Notifications** in the sidebar. Rows are grouped under Today and dated headings, with an icon for their kind.

### What's new
- **How:** after the app is updated, the window opens by itself once. Close it and it stays closed until the next release. To read it again, click **What's new** at the bottom of the sidebar.
  Search for a word, filter by New, Better, Fixed or Security, and click an older release to open it. Every release has its own name.

---

## Release timeline

| Version | Name | Date | What it was about |
|---|---|---|---|
| 1.14.0 | Tern | 2026-10-14 | Profile, team pages, lists, a calmer What's new |
| 1.13.0 | Swift | 2026-10-14 | A DSR that is one table, honest hours for long tickets |
| 1.12.0 | Robin | 2026-10-14 | A new look, dark mode and keyboard shortcuts |
| 1.11.0 | Quail | 2026-10-12 | A toast for every action and an audit trail |
| 1.10.0 | Plover | 2026-10-09 | Priorities, overdue alerts and to-dos in your DSR |
| 1.9.0 | Osprey | 2026-10-09 | A fuller home page, DSR on a phone |
| 1.8.0 | Nightjar | 2026-10-09 | A bigger to-do list and a due-soon card |
| 1.7.2 | Martin | 2026-10-09 | A tidier ticket page and clearer messages |
| 1.7.1 | Lark | 2026-10-09 | Clearer ticket errors, tighter project privacy |
| 1.7.0 | Kestrel | 2026-10-09 | A to-do list on your home page |
| 1.6.1 | Jay | 2026-10-08 | Messages show up again |
| 1.6.0 | Ibis | 2026-10-07 | Create tickets from your AI tool |
| 1.5.0 | Heron | 2026-10-07 | Build your DSR from your AI tool |
| 1.4.0 | Grebe | 2026-10-06 | Team week, late preview, shortcuts, smarter search |
| 1.3.0 | Falcon | 2026-10-06 | A top bar, a bento home, office hours 10 to 6:30 |
| 1.2.2 | Egret | 2026-10-05 | A live countdown on the punch card |
| 1.2.1 | Dunlin | 2026-10-05 | Products on the DSR |
| 1.2.0 | Condor | 2026-10-04 | Tickets named after their product |
| 1.1.0 | Bittern | 2026-10-04 | Alerts, search, reports and a new look |
| 1.0.1 | Albatross | 2026-10-02 | Punch panel, forgotten check-outs and leave caps |
