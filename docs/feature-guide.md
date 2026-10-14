# Feature guide

What was added to PQ Platform, **when** it arrived, **why** it was added and **how to use** it. Every entry names the
release it came in with (version, name and date) so you can find the full notes in the [changelog](../CHANGELOG.md) or
the in-app **What's new** window.

Most of this arrived during the move to the new React interface, between 1.12.0 and 1.38.1. Earlier releases are listed
in the [release timeline](#release-timeline) at the end.

- [Getting around](#getting-around)
- [Home and you](#home-and-you)
- [Tickets](#tickets)
- [Errors, products, surveys and automation](#errors-products-surveys-and-automation)
- [The DSR](#the-dsr)
- [Attendance, leave and payroll](#attendance-leave-and-payroll)
- [Team and profile](#team-and-profile)
- [Notifications](#notifications)
- [Exports](#exports)
- [For whoever runs the app](#for-whoever-runs-the-app)
- [Release timeline](#release-timeline)

---

## Getting around

### One design, light and dark
- **Added:** dark mode in 1.25.0 "Finch"; every page on one component set by 1.28.0 "Junco" (2026-10-13). The theme
  switch fades smoothly from 1.29.0 "Linnet".
- **Why:** the app had grown from five different looks. One set of components makes every page behave the same and
  makes the interface quicker to change. Dark mode is easier on the eyes in the evening.
- **How:** open the account menu (your avatar, top right) and choose Light, Dark or System. Press **t** to flip it from
  the keyboard.

### A new sidebar and top bar
- **Added:** 1.13.0 "Swift" (2026-10-13). The sidebar slides open and closed from 1.32.0 "Pelican".
- **Why:** one place for navigation, search, alerts and who is online, instead of each page doing its own thing.
- **How:** the arrow at the bottom (or **[**) folds the sidebar to icons. On a phone it opens as a drawer from the menu
  button. Hover an icon to see its name. A product you have open gets its own menu under Tickets.

### Search that can also do things
- **Added:** search in 1.13.0 "Swift"; actions in search in 1.36.0 "Puffin" (2026-10-13).
- **Why:** finding the page, then the button, takes longer than typing what you want.
- **How:** press **Ctrl K** (**⌘ K** on a Mac) or **/**. Type a ticket, error, product or page name. Type "leave", "log" or
  "punch" and an **Actions** group offers to request leave, log work or open the punch clock. You only ever see results
  you are allowed to open. Narrow with `in:tickets`, `assignee:me` or `status:open`.

### Keyboard shortcuts
- **Added:** `c`, `/`, `?` and the ticket keys earlier; "go to" shortcuts, `t` and `[` in 1.35.0 "Wagtail" (2026-10-13).
- **Why:** people who live in the app should not have to reach for the mouse.
- **How:** press **?** anywhere for the full list, or open **Profile → Keyboard shortcuts**, or **Account menu → Keyboard
  shortcuts**. Press **g** then a letter to jump: **h** Home, **t** Tickets, **e** Errors, **p** Products, **d** DSR,
  **a** Attendance, **l** My leave, **r** Reports, **m** Team, **u** Profile. They show ⌘ on a Mac and Ctrl elsewhere,
  and pause while you type in a field.

### What's new, shown once
- **Added:** the dialog in 1.12.0; a searchable timeline in 1.38.0 "Cormorant"; shown once per release and smooth
  animation in 1.38.1 "Bluethroat" and 1.39.0 "Thrasher" (2026-10-13). Every release also has its own name.
- **Why:** people missed changes. Showing a release once, then keeping it one click away, tells them without nagging.
- **How:** after the app is updated, the window opens by itself a moment after you load a page. Close it and it stays
  closed until the next release. To read it again, click **What's new** at the bottom of the sidebar. Search for a word,
  filter by New, Better, Fixed or Security, and click an older release to open it.

### Smooth, clear feedback
- **Added:** a toast for every action in 1.11.0 "Quail"; every write shows one centrally in 1.33.0 "Rook"; tooltips on
  icon buttons in 1.33.0; confirm boxes before deletes and punching out in 1.34.0 "Starling" (2026-10-13).
- **Why:** an action that says nothing leaves you unsure whether it worked, and one click on a trash icon should not be
  the end of something.
- **How:** nothing to switch on. Hover an icon button to see its name. Deleting asks first and says what will go.

---

## Home and you

### A home page that follows your day
- **Added:** a new Home in 1.19.0 "Yellowhammer"; a calmer one in 1.29.0 "Linnet"; the greeting in 1.33.0 "Rook" and
  its typewriter line in 1.34.1 "Thrush" (2026-10-13).
- **Why:** the old home opened on company-wide numbers that told a person nothing about their own day.
- **How:** Home shows what is yours first: open tickets, overdue, hours logged, hours worked, then Assigned and Due soon,
  Today and your to-do list, this week, pay and leave. The banner changes colour and icon through the day and types out a
  line. Hover its icon to see it redraw.

### Punch in and out from Home
- **Added:** 1.19.0 "Yellowhammer"; the confirmation in 1.34.0 "Starling" (2026-10-13).
- **Why:** a punch-out ends your day, and an accidental click was easy.
- **How:** use the button on the **Today** card (or the punch panel on Attendance). Punching out asks "Punch out for
  today?" and shows the time you have worked so far.

### To-do list
- **Added:** 1.7.0 "Kestrel", with priorities and overdue reminders in 1.10.0 "Plover" (2026-10-09); back on Home beside
  Today in 1.33.0 "Rook".
- **Why:** a place for small things that are not tickets. Finished ones land in your DSR so the day is easy to report.
- **How:** type a task, pick a priority and an optional due date, press Add. Tick it to finish it; overdue ones turn red
  and you get one reminder a day. Deleting asks first.

### On-time streak, milestones and celebrations
- **Added:** 1.35.0 "Wagtail" (2026-10-13).
- **Why:** small, friendly recognition makes the app feel less like a form to fill.
- **How:** your **streak** is the number of working days in a row you checked in within the grace period; weekends,
  holidays and approved leave do not break it. It appears on your profile and Today card from 2 days. **Milestones**
  mark a work anniversary or a round number of resolved tickets. **Confetti** appears when you resolve a ticket, tick your
  last to-do or finish a full working day.

### A page for you
- **Added:** 1.33.0 "Rook" (2026-10-13).
- **Why:** there was only a settings form; people wanted to see their own numbers and recent activity.
- **How:** account menu → **My profile**, or press **g** then **u**. Tabs: Overview (numbers, milestones, recent
  activity), Settings, Notifications, Keyboard shortcuts.

---

## Tickets

### Board
- **Added:** a new board in 1.14.0 "Tern"; a new look in 1.27.0 "Ibisbill"; compact cards, peek and drag animation in
  1.37.0 "Kite" (2026-10-13).
- **Why:** moving work between stages is the most common thing you do, so it should feel direct.
- **How:** drag a card to another column, or focus it and press **Alt + arrow**, or use the Move menu (the arrows icon)
  on a touch screen. Hover a card's title for a peek (status, priority, people, due date). The button beside Kanban/List
  switches to **compact cards**; the choice is remembered. Press **j / k** to move through tickets, **Enter** to open one
  and **e** to edit it.

### List and filters
- **Added:** 1.14.0 "Tern" (2026-10-13).
- **Why:** a dense view for scanning many tickets, with a link you can share.
- **How:** switch to **List**, search, and filter by status, priority, type, product and assignee. The filters are in the
  address, so a copied link shows the same view. **Select** lets you pick several tickets and delete them together.

### A ticket page with its whole story
- **Added:** a new page in 1.15.0 "Umbrellabird"; one column in 1.30.0 "Merlin"; the activity timeline in 1.36.0
  "Puffin" (2026-10-13).
- **Why:** status changes were separate from the conversation, so you could not read what happened in order.
- **How:** change status, priority, assignees and deadline at the top and each saves as you go. The **Activity** section
  merges status and priority changes, assignments and comments in time order. Type **@** in a comment to mention someone
  (they are notified). **Follow** gets you notices without being assigned. You can see who else has the ticket open.

### Forms that keep Save in reach
- **Added:** 1.37.0 "Kite" (2026-10-13).
- **Why:** on a long form the Save button used to scroll out of sight.
- **How:** nothing to do. The Save and Cancel row stays at the bottom of the window on the ticket, error, product, survey,
  rule, leave and correction forms and on your profile.

---

## Errors, products, surveys and automation

| Feature | Added | Why | How |
|---|---|---|---|
| **Errors** list and page, with one-click resolve or ignore, a trend chart and a "Create ticket" button | 1.16.0 "Vireo" (2026-10-13) | Triage should take a click, not a form. | Open **Errors**, click an error, then Resolve, Ignore or Create ticket. |
| **Products** as a list of strips, with a tabbed page for roadmap, versions, API keys and team access | 1.17.0 "Wren", 1.30.1 "Nuthatch" (2026-10-13) | One product's settings were scattered. | Open **Products**, click one. A new API key is shown once where you made it; rotating a key asks first. |
| **Surveys** and the **CS Hub**, including the public survey page | 1.18.0 "Xenops" (2026-10-13) | Customer feedback should reach the backlog. | Open **Surveys** to create one and share its link; open **CS Hub** to turn feedback into tickets. People only see surveys for products they can open. |
| **Automation rules** that file a ticket when an error repeats | 1.18.0 "Xenops" | Surges should not wait for someone to notice. | Open **Automation**, create a rule (threshold and time window). It runs from a scheduled command (see below). |
| **Reports** as one divided sheet with a day-by-day chart | 1.19.0, 1.31.0 "Oriole" (2026-10-13) | Numbers read better together than in cards. | Open **Reports**, pick a period, and Generate. |
| **Audit log** and **product dashboard** | 1.19.0 "Yellowhammer" | Who did what, and how a product is doing. | Open **Audit log** (owners and admins) or a product's Dashboard button. |

---

## The DSR

### One table of everything submitted
- **Added:** 1.29.0 "Linnet" and 1.30.0 "Merlin" (2026-10-13), after an editable sheet in 1.20.0 "Zebra Finch".
- **Why:** history and today were hard to read in separate views, and a spreadsheet look is what people expect.
- **How:** open **DSR**. Rows are grouped by day with the day's total (Date, Task, Project, Category, Time, Status). Switch
  between Today, Yesterday, 7 or 30 days, search, and (owners and admins) pick a person or Everyone. Click the pencil to
  edit a row or the bin to delete it (it asks first). **Log work** opens a small window. **Copy summary** puts a standup
  message on your clipboard. Members can edit today only; owners and admins can edit any past day.

### Suggestions and one-click catch-up
- **Added:** suggestions in 1.20.0 "Zebra Finch"; **Add all** in 1.37.0 "Kite" (2026-10-13).
- **Why:** nobody remembers what they did at 6pm, but the activity log does.
- **How:** a banner on today's DSR lists tickets you worked on that are not logged yet. **Add all** logs them at
  suggested hours; **Review** lets you change each time first.

### Honest hours for resolved tickets
- **Added:** capped in 1.33.0 "Rook"; shows how long a ticket was open in 1.39.1 "Wigeon"; asks for your real time in
  1.40.0 "Nightingale" (2026-10-13).
- **Why:** a ticket open for weeks logged weeks of hours (even about 1000) when it was resolved, but the real time taken
  is still worth seeing.
- **How:** a ticket open for less than a working day logs that time as before. A ticket open for longer logs **0** counted
  time and shows "Created … → completed … · open for 11d 1h (not counted)". When you resolve it a message tells you to add
  the time you worked on it today, the DSR opens a small window for it, and a banner plus an **Add time** button stay until
  you enter it. Only the time you enter counts. Older rows keep their full hours until an admin runs
  `python manage.py fix_dsr_hours --dry-run`, reads the list, then runs it without `--dry-run`: that moves those hours into the
  open-for time and stops them counting. That step is optional.

---

## Attendance, leave and payroll

### Attendance
- **Added:** a new punch panel and sheets in 1.22.0 "Bunting"; punch-out confirmation in 1.34.0 "Starling"; one tidy sheet
  in 1.36.0 "Puffin"; reminders in 1.37.0 "Kite" (2026-10-13).
- **Why:** the numbers here feed payroll, so they need to be clear, and forgotten check-outs cost people money.
- **How:** punch from Home or **Attendance**. The month calendar and your days sit side by side; a day with no check-out is
  flagged, and **Ask for a correction** sends it to an approver. Owners and admins see **Team attendance** and the
  **Timesheet**. **Reminders:** a nudge shortly after your shift starts if you have not checked in, and another after it
  ends if you have not checked out. Switch either off in Profile → Notifications.

### Leave
- **Added:** 1.23.0 "Curlew" (2026-10-13).
- **Why:** people want to know the paid/unpaid result before they submit.
- **How:** open **My leave**, then Request leave. A live preview shows the paid and unpaid days. Approvers use
  **Approvals** and the team **Calendar**. You cannot approve your own request while another approver is available.

### Payroll
- **Added:** 1.24.0 "Dipper" (2026-10-13).
- **Why:** a payslip should explain itself, and holidays and leave must not cost anyone by accident.
- **How:** admins use **Payroll** (cycle preview, runs, salary setup, holidays). People open **My payslips**; a payslip
  shows how each figure was worked out and has a **Print** button for saving as PDF. Locking a run and removing a holiday
  ask first.

---

## Team and profile

### Strips, and a page for each person
- **Added:** the team as strips in 1.32.0 "Pelican"; each member's page in 1.36.0 "Puffin" (2026-10-13).
- **Why:** you often want to see what a colleague is working on before you ask.
- **How:** open **Team** and click a name. You see their role, streak, milestones, numbers and the open tickets of theirs
  that you are allowed to see. Only owners and admins see the email. Owners and admins add, edit and remove members.

---

## Notifications

### A page worth reading, and switches
- **Added:** the page in 1.12.0 "Robin" (2026-10-12); grouped by day with icons and filters in 1.37.0 "Kite"; a switch per
  kind in 1.36.0 "Puffin" (2026-10-13).
- **Why:** not everyone wants every ping.
- **How:** click the bell, or open **Notifications** from the sidebar. Filter by unread or type; **Mark all read** clears
  them. Under **Profile → Notifications** turn off a kind you do not need (mentions, comments, leave decisions, payslips,
  reminders). System messages cannot be turned off. The setting applies in every workspace you belong to.

---

## Exports

- **Added:** 1.36.0 "Puffin" (2026-10-13).
- **Why:** reports often end up in a spreadsheet or an email anyway.
- **How:** click **Export CSV** on the DSR (it uses the range, person and search you have on screen), on the attendance
  **Timesheet** for the chosen month (owners and admins) and on a **payroll run** (owners and admins). Open a payslip and
  press **Print** to save it as a PDF; the sidebar and top bar are left out of the printout.

---

## For whoever runs the app

| Feature | Added | What you need to know |
|---|---|---|
| **Scheduled commands** | 1.37.0 "Kite" and earlier | `evaluate_rules`, `send_attendance_reminders` and `notify_todos` only run if you schedule them. See [Running the project](running-the-project.md#background-jobs). |
| **Release names** | 1.37.1 "Hoopoe" (2026-10-13) | Every numbered release in `CHANGELOG.md` has a unique bird name in its heading; a test fails on a missing or repeated one. |
| **Show once** | 1.39.0 "Thrasher" | The browser remembers the last release it showed in `localStorage` (`pq:seen-version`). A new `APP_VERSION` shows the window again. |
| **Docs** | 1.38.1 onward | [Running the project](running-the-project.md), the [user guides](guides/README.md) and this guide. |

---

## Release timeline

| Version | Name | Date | What it was about |
|---|---|---|---|
| 1.40.0 | Nightingale | 2026-10-13 | Long-open tickets ask for your real time |
| 1.39.1 | Wigeon | 2026-10-13 | How long a ticket was open, shown in the DSR |
| 1.39.0 | Thrasher | 2026-10-13 | What's new shown once per release |
| 1.38.1 | Bluethroat | 2026-10-13 | A smoother What's new |
| 1.38.0 | Cormorant | 2026-10-13 | A calmer What's new |
| 1.37.1 | Hoopoe | 2026-10-13 | The right shortcut hint |
| 1.37.0 | Kite | 2026-10-13 | Reminders, one-click DSR and a smoother board |
| 1.36.0 | Puffin | 2026-10-13 | Exports, team pages, notification settings, tidier pages |
| 1.35.0 | Wagtail | 2026-10-13 | Friendlier, with more keyboard shortcuts |
| 1.34.1 | Thrush | 2026-10-13 | A friendlier greeting |
| 1.34.0 | Starling | 2026-10-13 | Ask before punching out or deleting |
| 1.33.0 | Rook | 2026-10-13 | Profile, greeting, tooltips, honest DSR hours |
| 1.32.0 | Pelican | 2026-10-13 | Team and CS Hub strips, smoother sidebar |
| 1.31.0 | Oriole | 2026-10-13 | Ledgers and sheets |
| 1.30.1 | Nuthatch | 2026-10-13 | Products as a ledger |
| 1.30.0 | Merlin | 2026-10-13 | A spreadsheet DSR, simpler product and ticket pages |
| 1.29.0 | Linnet | 2026-10-13 | A calmer Home and a DSR you can read |
| 1.28.1 | Kingfisher | 2026-10-13 | Icons on every button |
| 1.28.0 | Junco | 2026-10-13 | The whole app, in one design |
| 1.27.0 | Ibisbill | 2026-10-13 | Pickers, board and charts |
| 1.26.0 | Harrier | 2026-10-13 | One component set everywhere |
| 1.25.1 | Godwit | 2026-10-13 | Matching empty and error screens |
| 1.25.0 | Finch | 2026-10-13 | Dark mode and a tidier layout |
| 1.24.1 | Eagle | 2026-10-13 | Sturdier forms |
| 1.24.0 | Dipper | 2026-10-13 | Payroll, redone |
| 1.23.0 | Curlew | 2026-10-13 | Leave, redone |
| 1.22.0 | Bunting | 2026-10-13 | Attendance, redone |
| 1.21.0 | Avocet | 2026-10-13 | Sign-in, team and settings, redone |
| 1.20.0 | Zebra Finch | 2026-10-13 | The DSR sheet, redone |
| 1.19.0 | Yellowhammer | 2026-10-13 | Home, reports and the audit log, redone |
| 1.18.0 | Xenops | 2026-10-13 | Surveys and automation, redone |
| 1.17.0 | Wren | 2026-10-13 | Products, redone |
| 1.16.0 | Vireo | 2026-10-13 | Errors, redone |
| 1.15.0 | Umbrellabird | 2026-10-13 | A new ticket page |
| 1.14.0 | Tern | 2026-10-13 | Tickets, redone |
| 1.13.0 | Swift | 2026-10-13 | A new navigation |
| 1.12.0 | Robin | 2026-10-12 | A fresher notifications page |
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
