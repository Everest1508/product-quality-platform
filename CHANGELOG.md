# Changelog

This is what the **What's new** button in the sidebar shows, so write it for the
person using the app: what they can now do, what got easier, what was broken.
No class names, no field names, no test names, no file paths — if a change needs
that kind of detail it belongs in `AGENTS.md` instead, which is where the
engineering invariants live.

Format follows [Keep a Changelog](https://keepachangelog.com/). Each release starts
with a line beginning `> In short:` that says what it is about in one sentence, then
New, Better, Fixed and Security lists. Older releases are below the newest.

## [1.7.0] — 2026-10-09 · a to-do list on your home page

> In short: the home page now has a private to-do card where you can write down what you want to get done and tick it off.

### New

- **A to-do card on the home page.** Type a task, press Add, tick it when it is done or remove it. Only you can see your list.

## [1.6.1] — 2026-10-08 · messages show up again

> In short: the confirmation messages that pop up after you check in or out work again, and your open DSR tasks now show on the home page.

### Better

- **Your open DSR tasks are on the home page.** The DSR card now lists work that is in progress or blocked, so you can see what is still open without opening the sheet.

### Fixed

- **Confirmation messages show again after you check in or out.** Messages like "Checked in at 10:02 AM." were being lost and never appeared on screen. They now pop up, and the same fix brings back messages after other saves.

## [1.6.0] — 2026-10-07 · create tickets from your AI tool

> In short: type /ticket or /dsr-ticket in your AI tool to create tickets without opening the app, and the DSR table is easier to use.

### New

- **Create tickets from your AI tool.** Type /ticket in Claude Code, Codex or a similar tool, or just ask in chat. The ticket is created in the project you pick and assigned to you.
- **Create a ticket and your DSR together.** Type /dsr-ticket to make the ticket and log it in today's DSR in one go.
- **If no project fits, you are asked.** You can pick an existing project or create a new one. Only owners and admins can create projects, so everyone else is told to ask one of them.

### Better

- **Duplicate tickets are caught before they are made.** If an open ticket with the same title already exists in that project, you are shown it instead of getting a second copy.

### Fixed

- **The DSR table's dropdown menus are no longer cut off.** Menus near the edge of the table now open fully.
- **Editable cells in the DSR table now look editable.** You can tell at a glance which cells you can click and change.

## [1.5.0] — 2026-10-07 · build your DSR from your AI tool, and a table you can read

> In short: type /dsr in your AI tool to build today's DSR from your real work, log time in minutes, and read the DSR sheet as a table again.

### New

- **Build your DSR from your AI tool.** Type /dsr in Claude Code, Codex, OpenCode, Kiro or a similar tool. It reads your commits and tickets for the day, drafts the entries, and sends them only after you approve.
- **A purple "via MCP" tag on entries added that way.** You can tell at a glance which rows came from your AI tool and which you typed yourself.
- **Type time in minutes and hours.** Write 45m, 1h 30m, 1:30 or 1.5 in any time box. A plain number still means hours.

### Better

- **The DSR sheet is a table again.** Task, project, category, time and status sit in columns with a total at the bottom, and every cell can be edited in place.
- **Times show as 1h 30m and 45m.** The summary, the total, the copied DSR text and the team overview all use the same style instead of decimals.
- **Times show in 12-hour format everywhere.** Check-ins, check-outs and other clock times read like 9:30 AM across the app.
- **Quick time buttons are 15m, 30m, 1h, 2h and 4h.** One click fills the time when you log work.

### Security

- **The DSR connection cannot reach anything else.** The sign-in token the AI tool uses only works for your DSR, so it cannot read Server Operator teams or shared-server passwords, and Server Operator tokens cannot be used for the DSR.

## [1.4.0] — 2026-10-06 · team week, late preview, shortcuts and smarter search

> In short: admins get a week view of the whole team, the check-in card shows what being late would cost, tickets can be followed, and search explains its matches.

### New

- **A week view for the team.** On Team attendance, switch from Today to Week. Every person gets seven day cells with check-in and check-out times, how late they were, and approved leave, plus a total for the week. Move between weeks with the arrows.
- **See the cost of being late before you check in.** The check-in card says whether you are still on time, and if not, how many minutes late you would be and what the penalty is. It updates as the minutes pass.
- **A nudge to log your DSR.** Once your day is over and nothing is logged, Home shows a reminder and your notifications get one line. It stays quiet on weekends, on leave, and on days you did not check in.
- **Follow a ticket.** Press Follow on any ticket to get its comments and status changes without being assigned. Press it again to stop.
- **A Regressed tab on errors.** It lists errors that were resolved and then came back, with a count.
- **Linked tickets on every error.** An error now shows the tickets raised from it, only the ones you can open.
- **Keyboard shortcuts.** Press `c` for a new ticket, `j` and `k` to move through a list or board, Enter to open the highlighted ticket, `e` to edit the ticket you are viewing, and `?` to see them all.

### Better

- **Search tells you why something matched.** Results show a short piece of the description, comment or error detail with your words highlighted.
- **Narrow a search with words.** Add `in:tickets`, `in:errors`, `assignee:me` or `status:open` to what you type. The search box also remembers your last five searches.

## [1.3.0] — 2026-10-06 · a top bar, a bento home, and office hours of 10 to 6:30

> In short: a new top bar with search, online, notifications and your account, a home page of charts, a redesigned Products page, and the office day now ends at 6:30 PM.

### New

- **A top bar on every page.** Search sits in the middle, with a **New** menu for a ticket, leave request, correction or product. Next to it are who is online, your notifications and your account menu with Settings and Sign out.
- **Charts on the home page.** Hours worked each day this week against your daily goal, tickets by status, and errors over the last 14 days sit in a tidier grid next to Pay, Leave, DSR and your tickets.
- **A receipt when you check in or out.** You get a message right away and a line in your notifications.
- **Product tiles.** The Products page opens with totals for products, open errors, open tickets and how many need attention. Each product card shows its health, key, counts and a small chart of this week's errors.

### Better

- **Office hours are 10:00 to 6:30.** That is a 7 hour 30 minute working day after the one-hour break. Teams still on the old 7:00 PM end time were moved over; an end time someone set themselves was left alone.
- **Correction requests show what you asked for.** Each request lists the times you filled in next to the old ones, your reason, when you sent it and any note from the admin. The form previews your times as you type, and the confirmation repeats them.
- **Search looks everywhere.** It now finds words inside ticket descriptions and comments, error details and pages, product descriptions, feedback, surveys, automation rules, and your own DSR entries and leave reasons. It only shows what you are allowed to open.
- **The "waiting for you" chips on the home page are tidier.** They are now rounded with a count badge.
- **The new look is applied across the app.** Softer blue-grey background with white panels, and a dark card for today's punch.

### Fixed

- **Messages after quick actions now appear.** Saving, deleting or punching from a page that updates in place used to queue the message for a later page. Creating an API key and deleting tickets in bulk had no message at all.
- **The Recent days box on My attendance no longer disappears.** On a window shorter than the page it collapsed to nothing. It now keeps its size and the page scrolls.

## [1.2.2] — 2026-10-05 · a live countdown on the punch card

> In short: the punch card shows plain time with no circle, and once you check in it counts down to the end of your full day.

### New

- **A countdown after you check in.** The card shows the time left in your day, ticking by the second, and the time you finish. A full day is 8 hours of work plus the unpaid break, counted from the moment you checked in. Once you pass it, the card shows how long you have gone over.

### Better

- **No more circle.** Before you check in the card shows the time in large numbers. After you check out it shows the hours you worked. A thin bar under the countdown shows how far through the day you are.
- **The check-in and check-out buttons are full width.** They sit under the card text.

## [1.2.1] — 2026-10-05 · products on the DSR

> In short: you can say which product a DSR entry was for, and the form starts empty after each entry.

### New

- **Pick a product on a DSR entry.** The new entry form has a Product box that lists only the products you can open. Leave it on "No product" for meetings and the like. You can change it on a row later.
- **Product shows on every entry.** Entries made from a ticket take the ticket's product on their own, and older ticket entries were filled in. The copied summary names the product too.

### Better

- **The entry form stays open after you add one.** You can log the next entry straight away.

### Fixed

- **The form still held your last entry.** After adding a task, the text of that task was left in the form. It now starts empty. If an entry fails, what you typed stays so you can fix it.
- **Category and status colors on DSR rows never showed.** They now do.

## [1.2.0] — 2026-10-04 · tickets named after their product

> In short: every ticket now has a readable name like AUM-014, and My attendance and this What's new window were redesigned.

### New

- **Ticket names like AUM-014.** A ticket is named after its product, then a number that counts up inside that product. AU-Marketing tickets are AUM-001, AUM-002 and so on. AU-HRMS has its own AUH-001. You see the name in lists, on the board, on the ticket, in the DSR, in notifications, in Discord and in the audit log.
- **A prefix on every product.** It fills in while you type the product name, and it skips any prefix the company already uses, so a second "Billing Portal" becomes BIP2. Type in the box to pick your own. Owners and admins can change it later, which renames every ticket of that product.
- **Search by ticket name.** Type AUM-14, aum14 or aum 14. Type just AUM to list that product's newest tickets. The old # numbers still work.
- **A month at a glance on My attendance.** Each day is a square. Dark green is a full day, light green a part day, blue the day you are on the clock, orange a missing check-out. A count for each kind sits beside it.
- **A clearer What's new window.** Each version opens with one sentence on what it is about. New, Better, Fixed and Security have their own colors, and older versions fold away until you open them.

### Better

- **My attendance uses two columns.** The punch card sits beside the week, every day of the week shows its hours, and each worked time in the table has a small bar under it.
- **Hours this month.** The number strip now shows hours worked this month and your daily average.
- **Old tickets got names too.** Each product's tickets were numbered from 1 in the order they were created.
- **The ticket API returns the name.** Creating a ticket also returns its name, such as AUM-014, next to the existing fields.
- **The changelog is shorter and plainer.** Every earlier note for 1.1.0 is now one entry.

### Known issues

- DSR entries written before this release still show the old # number in their task text. New entries use the ticket name.

## [1.1.0] — 2026-10-04 · alerts, search, reports and a new look

> In short: you get told about things, can find anything with Ctrl K, see who is online, and the whole app was redrawn to work on a phone and install like an app.

### New

- **A notification bell.** Being assigned a ticket, being mentioned, a comment on a ticket you are on, a decision on your leave or attendance request, and a resolved error coming back all show up live with an unread count. Turn on alerts and your phone or computer tells you even when the app is closed.
- **Mentions in comments.** Type @ and a few letters to pick a colleague. Only people who can open the ticket are offered, and they are told.
- **Search from anywhere.** Press Ctrl K (Cmd K on a Mac, or / when you are not typing) to find tickets, errors, products and pages. It only shows what you can open.
- **Online now.** See who has the app open and what kind of page they are on, such as "Viewing ticket #14". It also shows who is clocked in. If your network blocks live updates, the list refreshes every 25 seconds instead.
- **Error trends.** Every error has a 14 day chart. Errors are flagged when they are new in a release, when they come back after being resolved, and when they are rising.
- **Attendance corrections.** If a punch is wrong, ask for a fix with a reason. An owner or admin approves or rejects it and you are told.
- **A leave calendar.** See who is off on which day, with company holidays shown. When someone asks for leave, approvers see who else is already off.
- **Reports with charts.** Five tiles compare each number with the same number of days before. A day by day chart, two completion rings and bars for busy products sit below. Pick Today, Yesterday, Last 7 days, Last 30 days or This month without a reload.
- **A welcome tile on home.** It greets you, shows the time from your own device and has a short line to keep you going. Press the arrow for another one.
- **Your work on the DSR.** Tickets you touched that day appear above the form with a guess at the hours. Check the number and add it in one click. Your open tickets also show as quick chips.
- **API docs and key rotation.** Each product has a page with real field lists and example requests. Make a new API key and keep the old one working for a day or a week while you switch over.
- **Install it as an app.** On a phone or computer, add PQ Platform to your home screen. It shows an offline page when the connection drops.
- **A new logo and colors.** One shared palette replaces the mixed colors from before.
- **Guides.** Short how-tos for attendance and leave, the DSR, tickets and errors, reports and live presence are written up in the guides folder of the repository.

### Better

- **The punch panel is live.** A clock ticks by the second, the elapsed time counts up, and it tells you when you are late.
- **The DSR reads like a work log.** Each entry is a row with its times, a colored status bar, the task and note, then hours, status and delete. Rows save themselves when you change them. Today's report closes at midnight, older days stay readable, and owners and admins can still correct a closed day.
- **Team attendance is easier to read.** Your own row comes first and is marked.
- **Home is a bento grid.** Its tiles fill each row.
- **The sign-in page was rebuilt.** It has two columns on a laptop and one on a phone, shows that it is working, lets you reveal what you typed, lets browsers fill the right fields, and keeps your destination after you sign in.
- **Every dropdown looks the same.** It shows people by name and has "All" back where it belongs.
- **Fewer boxes.** My attendance has one strip of numbers, product cards show open errors and open tickets, and the lists fit their columns. Long titles wrap and times read "2 days ago".
- **The collapsed sidebar shows names.** Hover or tab to an icon. An unread count becomes a dot.
- **Messages appear in the bottom right.** They stack neatly.
- **Phones and tablets use the full width.** The main pages fit a 390px screen.

### Fixed

- **Sidebar and page counts disagreed.** Headers now read "15 tickets · 9 open", and with no filter the open number is the sidebar number.
- **The ticket list was shifted one column.** Ticket numbers sat under the wrong heading.
- **Several dropdowns could be open at once.** Opening one closes the others.
- **DSR rows interfered with each other.** Choosing a category on one row cleared it on another, and a row went read-only after its first edit.
- **Tapping Check in twice ended your day.** A second tap within 45 seconds is now ignored.
- **You could not find your own attendance on the team page.**
- **The punch panel's elapsed time never counted up.**
- **Developer notes were printing on the page.** It happened in leave, attendance and the sign-in page.
- **Payroll runs are written all at once.** A failure part way through can no longer leave a half-finished run.
- **Locking a pay run, unlocking it and removing a holiday are in the audit log.**
- **Edited attendance times are checked.** A punch cannot be moved to a different day or put after its own check-out.
- **Attendance pages could break.** It happened if a company ever had two shift records.
- **A resolved error that happens again reopens.** Several errors arriving at once are now counted correctly.
- **Customers behind one office network were rejected after 60 errors a minute.** The limit is now per API key.
- **A long-running ticket no longer breaks your dashboard.**
- **The quick leave form now tells approvers.** It also appears in the audit log.
- **Sign-in page faults.** The eye icon was a giant blob, the desktop app's sign-in page had lost its styling, the show-password button could not be reached with a keyboard, and a wrong username and a wrong password gave different messages.
- **"Connecting to the live feed" never went away.** It happened behind some proxies.

### Security

- **API keys are limited to the right people.** Only owners, admins and developers with access to the product can create, rotate and revoke them. Before, any team member could revoke any key.
- **Shared server passwords are limited.** Only owners, admins and developers can read them. Viewers no longer can.
- **Repeated wrong passwords lock sign-in.** The account is locked for 15 minutes.
- **Live updates only accept connections from this site.** Another website cannot open them with your cookies.
- **Passwords and tokens in captured errors are hidden.** They are removed before the data is stored.
- **A production setup refuses to start on the built-in secret keys.**

## [1.0.1] — 2026-10-02 · punch panel, forgotten check-outs & leave caps

Every earlier release note is kept below this one. The reasoning behind all of
it, and the questions still open, are in [context.md](context.md).

**The short version:** confirmation messages never appeared anywhere in the app,
nobody was ever charged for being late, the punch button wouldn't tell you what
time you arrived, a forgotten check-out cost you the day, and going over your
leave allowance was refused instead of charged. All five are fixed.

### New

- **A leave request that runs past your allowance is now accepted, not refused.**
  The days up to your limit are paid and **the rest is simply unpaid**, so you no
  longer have to guess how much to ask for and get it turned away.
  - The split is decided when the request is made and stored with it, so a later
    change to the policy cannot rewrite a decision that has already been made.
  - Payroll reads the stored split, so editing a leave type later never restates
    a payslip that has already been issued.
- **You can see which days will be unpaid before you submit.** The apply screen
  prices the request as you choose your dates, so a spell that runs past your
  limit tells you on the spot instead of after it is approved.
  - The panel stays empty while the dates are incomplete or a range contains no
    working days, rather than claiming "0 paid" for something you haven't
    finished typing.
- **Approvers can correct the dates and the paid/unpaid split** when they
  approve, on the same screen, using the same numbers the applicant saw.
  - Rejecting still costs nothing, and never records a split — there is nothing
    to pay for a request that was turned down.
- **Working days are counted as you'd expect.** Friday to Monday is 2 days, not
  4, and a half day is charged as half.

### Improved

- **The punch button now tells you when you came in, and whether you were late.**
  It used to say "on the clock" and then print a *duration*, so the one number
  you actually wanted was nowhere on the screen — and it said nothing about
  lateness at all.
  - Your office hours sit right under the button, and the time ticks up while you
    work.
  - Lateness is spelled out the moment it happens — "45m late" — using exactly
    the same figure your payslip is built from, so the two can't disagree. Half a
    day says so.
  - Before you've arrived there is no arrival time, so nothing claims you're late.
  - Every state carries both the hours and the lateness. A punch used to swap
    "on the clock, late 45m" for "checked out" and lose both.
  - The check-in and check-out buttons are now visually distinct; they were
    styled identically, because the two styles they asked for had never been
    written.
  - The result is announced to screen readers. The running timer deliberately is
    not — it refreshes every 30 seconds and would interrupt you constantly.
  - Clicking twice in a row used to make the panel claim you'd "already checked
    in and out". The button now waits for the first punch to land. The button
    also works if your browser has JavaScript turned off.
- **A forgotten check-out is now something you find out about, not something you
  find in a payslip.** If you clocked in and never clocked out, the punch panel
  lists the day and explains what it is costing you.
  - Your hours on that day are counted from when you arrived, so you do not lose
    the day outright — but they are capped at one full working day until an admin
    closes it, because nobody can know when you actually left. The cap matters:
    without it a forgotten punch from last month would report hundreds of hours.
  - The warning covers **every** month, not just the one you are looking at.
  - Today's own open punch is never listed as forgotten — that would put the
    warning on every working day and stop it meaning anything.
  - This **cannot change anyone's pay**: payslips are priced in days, and only
    your arrival time can carry a late penalty.
- **Managers can fix a forgotten check-out from wherever they see it** — inline
  next to the day on the team page, and as a link on the calendar, which has no
  room for a form but has room for a link.
  - Leaving the check-out box empty fills it with closing time, since that is
    what the cap already assumes, so nobody has to retype 19:00 by hand.
  - Clearing the box on purpose keeps the day open.
  - Opening somebody else's attendance as a manager no longer hides the whole
    punch panel. The button is hidden, because it would punch *you*, but the
    warning about them stays — which is the reason you opened the page.
- **The approver's dialog is wide enough to use.** It holds two date boxes, a
  switch and two day boxes, and at its old width they stacked into unreadable
  slivers.
- **Panels driven by the page state no longer flash on load** before the page
  settles.

### Fixed

- **Confirmation messages never appeared — anywhere.** Every "Saved", "Approved",
  "Edited" and every error message in the app rendered nothing: **79 places in
  the app** asked for a confirmation and none of them showed one. The messages
  were being handed to the page before it was ready to receive them, so the
  whole queue was quietly discarded.
  - Nothing had gone wrong with the actions themselves, which is what made this
    so confusing: the edit worked, and the app said nothing.
  - **A handful of actions never asked for one at all**, and were found by
    auditing every save handler rather than by the pages people happened to
    visit. Deleting DSR time, deleting a milestone, and advancing a milestone's
    status all finished silently; a status change with no confirmation looks
    exactly like a dead button. They report what happened now — and the
    milestone reports what it *became*, not just that you clicked it.
- **The app was running four and a half hours behind India.** Times were shown,
  and — more seriously — **lateness was scored in the wrong zone, so nobody was
  ever charged for being late.** A 10:45 arrival was recorded as 05:15, compared
  against a 10:00 start, and came out as *on time*; the punch button also
  cheerfully printed "05:15 AM" for a morning shift.
  - An arrival of 10:45 now reads as 10:45 and lands in the Rs 100 band, as the
    policy always said it should.
  - The lateness bands now sit where you set them: up to 15 minutes is on time,
    up to 30 costs Rs 50, up to an hour costs Rs 100, later than that costs half
    a day.
  - Everything is stored in UTC behind the scenes; only what is shown to you, and
    where a day starts and ends, changed.
  - **Your existing attendance history is not rewritten**, so records taken
    before this change will read some hours off. Ask an admin to correct them, or
    re-seed the demo workspace.
- **The "What's new" panel was empty in production.** Release notes were dropped
  from the container image entirely, so the button in the sidebar opened onto
  nothing — no error, nothing in the logs, and every check on your machine looked
  fine because the file was right there.
  - A missing changelog is now written to the logs once, so if it ever goes
    missing again the cause is on the server rather than a guess.
  - A deployed image needs rebuilding to pick this up.
- **The timesheet and dashboard counted a forgotten check-out as zero hours**,
  which quietly cost you the day until somebody noticed.
- **Opening a colleague's attendance as a manager showed you your own
  forgotten days** instead of theirs, on any day they had not yet punched.
- **Day counts could crash a leave page.** A whole number of days was being
  formatted as though it were always a fraction, so a request of 12 days could
  raise an error in the middle of an approval.
- **The demo team arrived at 06:30 for a 10:00 shift.** The seeder was avoiding
  late penalties by inventing early arrivals; it now seeds a realistic spread
  around your office hours, including genuinely late ones.
- **Clicking the punch button twice made the panel say you had already checked
  in and out.** The second click was correctly ignored, and then reported the
  opposite of what happened.

### Known issues (pre-existing, not addressed here)

- `apps.accounts.tests.test_tenant_isolation`: `test_signup_creates_user`
  (`NoReverseMatch` for `accounts:signup` — self-signup is not wired up). Still
  the only failing test, and it is a product question about whether signup should
  exist at all, not a regression.
- The three older release blocks below are still tagged **Unreleased**, so the
  dialog labels them "In development". They describe shipped work; only this
  block has been versioned.

## [Unreleased] — 2026-09-30 · attendance, leave & payroll

Three new sections — Attendance, Leave and Payroll — plus a home page built around
your own week, a rebuilt sidebar and a pass over accessibility. The reasoning
behind each of these, and the questions still open, are in
[changes-2026-09-30.md](changes-2026-09-30.md).

### New

- **Clock in and out from anywhere in the app.** Your company sets its own office
  hours and decides how late is too late.
  - Office hours are 10:00–19:00 with a 60-minute unpaid break, so a full day
    reads 8 hours rather than 9.
  - Up to 15 minutes late is on time, up to 30 costs Rs 50, up to an hour costs
    Rs 100, and later than that costs half a day. A day you never clocked in is
    never charged.
- **Your own attendance and a monthly timesheet.** When you came in, when you left,
  and what it means for your pay — without asking an admin.
- **Request leave, and approve it.** Everyone can request time off; an approver
  works through a queue of requests waiting on them.
  - Approvers are picked per person in the team settings. Owners and admins can
    always approve, whatever the toggle says.
  - Owners and admins also see what is waiting on them, right on the home page.
- **Leave types you can tell apart.** Each type carries its own colour and icon, so
  casual and sick are not two identical grey rows.
- **Lateness on your payslip.** Every late arrival is listed with the date, the
  time you arrived and what it cost — on your own payslip, not just an admin's.
  - What the screen shows before the run is issued is calculated the same way, so
    the estimate and the payslip can never disagree.
- **A home page about you.** It shows your attendance, your pay, your leave balance
  and your own tickets, instead of company-wide totals that told you nothing about
  your week.
  - Managers and owners additionally see the team's numbers, and tickets from
    products you don't have access to stay hidden.
  - The main button is now **Request leave** rather than **New ticket**, and a
    banner tells you when you are on approved leave today.
- **What's new, in the sidebar.** The footer shows the version, and the button
  beside it opens these notes.
  - It opens on the current release. The two earlier ones are folded away, and you
    can filter down to just what was fixed or improved.
- **A show/hide button on the password field** when you sign in.

### Improved

- **Leave is simpler to keep track of.** 17 days a year — 12 casual and 5 sick —
  and you can take at most 3 working days off at a time, counted across all types
  together.
  - Counted in working days, so Friday to Monday costs 2 days, not 4.
- **The leave settings page is one clear row per type**, instead of a table whose
  headings didn't line up with the boxes you were editing.
  - A type with no limit now reads **No cap**, rather than "Unlimited" — 0 is a
    real setting.
- **Lunch breaks are handled honestly.** The hour comes out of your day only if
  your day was long enough to include it, so leaving at 11:00 is not reported as
  less time than you actually worked.
- **The sidebar knows where you are.** It highlights the page you're on, names its
  sections properly for screen readers, and keeps its highlight and tooltips when
  collapsed.

### Fixed

- **The app used to go blank next to the sidebar.** A misplaced closing tag made
  everything to the right of it invisible. The product edit form had the same
  fault.
- **Signing in used to land everyone on a 404.** You now go to your home page.
- **A bad month of lateness could tell you to hand money back.** Someone on a low
  salary who was late every day came out at **-99.96** on their payslip. The
  deduction is now capped at what the month can absorb, so a payslip can never go
  negative.
- **"Add entry" on the timesheet made up a row for you.** It quietly logged an hour
  of "New Task" as complete. It now asks for the task and the hours, and won't
  accept more than 24 in a day.
- **The timesheet ignored anything invalid you typed.** Bad values are now
  rejected with a message instead of being silently saved.
- **90 controls were unlabelled for screen readers.** Every field now has a label
  that is actually attached to it, so clicking it focuses the box and a screen
  reader announces it.
  - This covered search and sort boxes, the bulk-select boxes on ticket cards, the
    audit log's date filters, and the assignee picker's remove buttons — which all
    announced "Remove assignee" regardless of who you were removing.
  - Two of these were only found on a second pass, because the first check was
    itself looking the wrong way.
- **Seven pages had no sidebar highlight at all**, including Automation and
  Feedback, which you could only reach by typing the URL.
- **Your payslip said unpaid leave was the only thing that reduced your pay**, which
  stopped being true the moment lateness could, and three places still said
  "medical" after we renamed it to sick.
- **The demo data changed depending on what time you seeded it**, and past 10:15 it
  invented a late penalty for your demo team.
- **Two copies of the timesheet's add form shared the same field ids**, so labels
  pointed at the wrong box. Links that open in a new tab also now carry the
  attribute that stops the new page reaching back into this one.

### Security

- **A live API token is committed in the repository.** It does not validate against
  this app's database, but if it was ever valid anywhere it **should be rotated**.
  - Two files are named so the test runner picks them up, which is why
    `manage.py test` reports three errors that have nothing to do with your code.
  - They also send real requests to whatever is running on your machine when the
    test suite starts.
  - Not changed yet. It needs a decision about where the token should live.

## [Unreleased] — 2026-09-04 · dashboard & ticket boards

### Added

- **Home dashboard rework.** Stat cards for open errors, open tickets, tickets
  resolved this week, and tickets assigned to you — each with a week-over-week
  delta. Below them: a grouped "Needs attention" list (critical errors, stale
  tickets, unassigned tickets), a products table (health, open errors/tickets,
  CSAT, stale count), and — for owners/admins — recent activity and a team
  breakdown.
- **Inline actions on the dashboard.** Assign a ticket to yourself, resolve or
  ignore an error, and start or resolve your own tickets straight from the
  attention/assigned lists. Each action posts via htmx and refreshes the whole
  dashboard in place, so the counts and lists stay current without a reload.
- **One shared filter bar** across all four ticket boards (company-wide and
  product-scoped, kanban and list) — the same controls in the same order. The
  kanban board gained the sort dropdown it was missing.
- **htmx filtering on the ticket boards.** Changing a filter, sort, search term,
  or page swaps just the board or table in place instead of reloading the page;
  the count in the header updates with it.
- **Touch fallback for the kanban** — long-press a card to pick a target column,
  since native drag-and-drop doesn't work on touchscreens.
- Breadcrumb and a "Last seen" stat on the company-wide error detail page.

### Changed

- Relative dates ("3 days ago") are used consistently across ticket and error
  lists and detail pages, with the exact timestamp on hover. Removed the mix of
  relative and absolute formats (some panels showed both for the same value).
- The Kanban ⇄ List toggle carries the active filters across the switch.
- Consolidated the duplicated filter logic across the four ticket views into
  shared `apply_ticket_filters` / `sort_tickets` helpers, and extracted the
  kanban board markup and drag script into reusable partials.

### Fixed

- **htmx CSRF handler.** The global `htmx:configRequest` handler used htmx-1.x
  syntax (`evt.headers`) and so never attached the CSRF token under htmx 2.x —
  any header-based htmx `POST` failed with 403. Form-based htmx requests carried
  their own hidden CSRF field, which is why the bug went unnoticed. This also
  unblocks non-form htmx actions elsewhere in the app.
- Dashboard sections and their empty states ("All caught up", "Nothing assigned")
  are now contained in labelled panels instead of floating in whitespace, which
  made a sparse or new workspace hard to read.

## [Unreleased] — 2026-09-04

### Security

- **Per-product access is now enforced on the company-wide ticket views.** The
  global ticket board, list, detail page, and every mutation endpoint
  (status, priority, assign, comment, deadline, edit, delete, bulk-delete)
  filtered only by company. Any member — including one with no `ProductAccess`
  at all — could see and modify tickets belonging to products they were never
  granted. All of these now scope to `accessible_products` and 404 on tickets
  outside the caller's reach. Owners and admins are unaffected.
- **Same fix for the company-wide error views** (`apps/errors/views.py`): list,
  detail, status change, ignore, resolve, convert-to-ticket, and delete now
  enforce product access.
- The ticket and error "create" forms restrict the product dropdown to products
  the user can access, and the product-scoped create views reject a mismatched
  product in the POST body.

### Added

- `apps/products/access.py`: `accessible_tickets` / `require_ticket_access` and
  `accessible_error_groups` / `require_error_group_access` helpers.
- **Product switcher** in the sidebar — jump between accessible products without
  returning to the product list.
- **User menu** pinned to the sidebar footer (initials avatar + name + role →
  Settings, Sign out), replacing the bare "Sign out" button.
- **Collapsible sidebar** — toggles to a 60px icon rail with hover tooltips;
  state persists in `localStorage` and applies before first paint.
- **Mobile navigation** — the sidebar becomes an off-canvas drawer with a
  backdrop, opened from a hamburger in a new sticky top bar. `Escape` or a
  backdrop tap closes it. Page headers, tab strips, and toolbars now wrap
  instead of clipping off-screen on narrow viewports.
- **Breadcrumbs** on product ticket/error list, kanban, and detail pages.
- Company-wide open-ticket / open-error count badges on the primary nav.
- Regression tests: `TicketProductAccessTest`, `ErrorProductAccessTest`.

### Changed

- The company-wide boards are now clearly labelled **"All tickets"** and
  **"All errors"** (page title, breadcrumb, `every product` scope note in the
  header). The sidebar entries were renamed to match, and the primary nav
  (`Home · Products · All tickets · All errors · Reports`) is now identical in
  every context instead of reshuffling when you enter or leave a product.
- **Sidebar rebuilt**: icons on every row, a visible active state (accent fill +
  left bar), and grouped sections (`Operations`, `Admin`). Settings moved out of
  the flat list into the user menu.
- The **Kanban ⇄ List** toggle now carries the active filters across the switch.
- **Kanban board**: height is bounded to the viewport so the horizontal
  scrollbar stays on screen; the scrollbar is themed; columns scroll-snap.
  Overdue tickets show one indicator (`Overdue · <date>`) instead of a badge
  and a red date.
- The **"Delete Tickets"** button (a selection-mode toggle) is relabelled
  **"Select"**.
- Assignee avatar chips render as intended — the `--accent` / `--accent-soft`
  design tokens they referenced were never defined; they now are.

### Fixed

- Product error and ticket counts in the sidebar collapsed to `0` on every
  product page except Overview, because those views passed a bare `product`
  that shadowed the count-annotated one from the context processor. The
  ticket/error views now attach counts explicitly.
- `TicketDetailView` returned **HTTP 500** on any `HX-Request` GET to
  `/tickets/<pk>/` — it rendered `tickets/partials/_ticket_detail_content.html`,
  which has never existed. No caller relied on it; the dead branch was removed.
- `test_sidebar_renders_company_switcher` updated for the renamed switcher CSS
  class (`org-switch` → `switch`).

### Known issues (pre-existing, not addressed here)

- `apps.accounts.tests.test_tenant_isolation`: `test_signup_creates_user`
  (`NoReverseMatch` for `accounts:signup`) and `test_request_has_company_after_login`
  (expects 200, the root view now redirects). Both are stale tests against
  refactored auth flow, unrelated to the changes above.
