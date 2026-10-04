# Changelog

This is what the **What's new** button in the sidebar shows, so write it for the
person using the app: what they can now do, what got easier, what was broken.
No class names, no field names, no test names, no file paths — if a change needs
that kind of detail it belongs in `AGENTS.md` instead, which is where the
engineering invariants live.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version 1.1.0 covers
every note down to the 1.0.1 heading, so it appears as several cards in the dialog.
Older releases are below the newest.

## [Unreleased] — 2026-10-04 · tickets named after their product

### Added

- **Ticket names like AUM-014.** Each ticket is now named after its product, with a
  number that counts up inside that product. AU-Marketing tickets are AUM-001,
  AUM-002 and so on, and AU-HRMS has its own AUH-001. The name shows in lists, on the
  board, on the ticket, in the DSR, in notifications, in Discord and in the audit log.
- **A ticket prefix on each product.** It fills in by itself while you type the product
  name, and it skips any prefix the company already uses, so a second "Billing Portal"
  becomes BIP2. Type in the box to choose your own and it stops following the name.
  Owners and admins can change it later by editing the product, which renames every
  ticket of that product.
- **A month at a glance on My attendance.** Every day of the month is a square, dark green
  for a full day, light green for a part day, blue for the day you are on the clock and
  orange for a missing check-out. Next to it are counts for each, and the number strip
  now shows hours worked this month and the daily average.
- **Search by ticket name.** Type AUM-14, aum14 or aum 14 in search. Typing just AUM lists
  that product's newest tickets. The old # numbers still work.
- **The ticket API returns the name.** Creating a ticket now also returns
  its name, such as AUM-014, next to the existing fields.

### Improved

- **My attendance is laid out in two columns.** The punch card sits beside the week,
  each day of the week shows its hours, and the table of recent days has a small bar
  under each worked time.
- **Existing tickets were numbered for you.** Each product's tickets are numbered from 1
  in the order they were created, so old tickets get names too.

### Known issues

- DSR entries written before this change still show the old # number in their task text.
  New entries use the ticket name.

## [1.1.0] — 2026-10-04 · a calmer interface, honest counts and real reports

### Added

- **A welcome tile on the home page.** It greets you, shows the time from your own
  device with seconds, and has a short line to keep you going. Press the arrow next
  to the line for another one. Only the line changes, the page does not reload. New
  ticket, Attendance and Request leave are one click away from the same tile.
- **Reports with charts.** Five tiles at the top show tickets created, tickets
  resolved, errors captured, errors resolved and all activity. Each one says how it
  moved against the same number of days just before. Under them, a column chart shows
  every day, two rings show how much got finished, and bars rank your busiest
  products and the most common events. The exact tables are still there, folded away.
  Pick Today, Yesterday, Last 7 days, Last 30 days or This month without a reload.
- **Guides.** Short how-tos for attendance and leave, the DSR, tickets and errors,
  reports and live presence are written up in the guides folder of the repository.

### Improved

- **The home page is a bento grid.** The tiles now fill each row, with wide and narrow
  ones side by side, instead of leaving gaps.
- **The DSR reads like a work log.** Each entry is a row with its times on the left, a
  colored bar for its status, the task and note in the middle, and hours, status and
  delete on the right. The three summary boxes became two tiles and a name. Every row
  saves itself when you change it.
- **Attendance has fewer boxes.** The five separate number boxes are one strip, and the
  punch panel no longer sits inside a second card.
- **Product cards show open work.** The errors and tickets numbers say "Open" and are
  colored, and the number box inside each card is gone.
- **The collapsed sidebar is easier to use.** Hover or tab to any icon to see its name.
  An unread count shows as a dot on the icon, and sections are separated by a line.
- **Ticket and error lists fit their columns.** Long titles wrap to two lines, times
  say "2 days ago" instead of "2 days, 3 hours ago", and the sparkline no longer sits
  on top of the last seen time.

### Fixed

- **The ticket list was shifted one column.** A hidden checkbox column left every
  cell under the wrong heading, so the ticket number sat under "Ticket Details" and the
  title was squeezed into a narrow strip.
- **Sidebar and page counts disagreed.** The sidebar counted open work and the page
  header counted everything. Headers now read "15 tickets · 9 open", and with no filter
  that open number is the sidebar number. The same applies on each product's pages.
- **Several dropdowns could be open at once.** Opening one now closes the others.
  Clicking elsewhere or pressing Escape closes it, and so does picking a value.
- **Choosing a category on one DSR row cleared it on another.** Rows share the same
  radio names, which the browser treated as one group. Each row is now its own form.
- **A DSR row went read-only after the first edit.** The row that came back from the
  save had lost its edit controls.
- **"Connecting to the live feed" never went away behind some proxies.** When the
  WebSocket cannot connect, the Online now list refreshes every 25 seconds instead, and
  the badge says so. If it stays on "Every 25s", see the presence guide for the proxy
  setting.

## [1.1.0] — 2026-10-04 · notifications, search, mentions, corrections and a leave calendar

### Added

- **A notification bell.** Being assigned a ticket, being mentioned, a comment on a
  ticket you are on, a decision on your leave or attendance correction, and a
  resolved error coming back all show up in the bell in the sidebar, live, with an
  unread count. Click one to go straight to it. "Turn on alerts" in the bell lets
  your phone or computer notify you even when the app is closed.
- **Mentions in ticket comments.** Type @ and a few letters to pick a colleague. Only
  people who can open the ticket are offered, they are told, and the mention is
  highlighted in the comment. A ticket also shows who else has it open right now.
- **Search from anywhere.** Press Ctrl+K (or Cmd+K, or / when you are not typing) to
  find tickets, errors, products and pages. It only shows what you can open.
  Searching a ticket number jumps to that ticket.
- **Error trends.** Every error shows a 14 day chart. Errors are flagged when they
  are new in the current release, when they came back after being resolved, and
  when they are climbing. The error page has a 30 day chart and a count per release.
- **Attendance corrections.** If a check-in or check-out is wrong, ask for a fix with
  a reason instead of waiting for someone to notice. An owner or admin approves or
  rejects it, and you are told. The "forgotten check-out" warning links straight to
  the form for that day.
- **A leave calendar.** See who is off on which day, with company holidays and
  waiting requests shown dashed. On a phone it becomes a list of the days that
  matter.
- **Clash warnings for leave.** When someone asks for leave, the approvers are told
  who else is already off and which day is busiest. The person applying sees it too.
- **Your work on the DSR.** Tickets you worked on that day appear above the form with
  a guess at the hours. Check the number and add it in one click.
- **API documentation for each product.** Real field lists, example requests in curl,
  Python, JavaScript and PHP, and what the errors mean.
- **Rotating API keys.** Make a new key and keep the old one working for a day or a
  week while you switch over, or stop it now. Keys also show when they were last used.

### Fixed

- **Any team member could create API keys, and revoke any key in the workspace** even
  for a product they cannot open. Only owners, admins and developers with access to
  the product can now.
- **Applying for leave from the quick form did not tell the approvers or appear in
  the audit log.** It now does both, the same as the full page.

## [1.1.0] — 2026-10-04 · live presence, a better punch panel, and an installable app

### Added

- **Online now.** A live list shows who is signed in and what they are doing,
  such as "Viewing ticket #14" or "Filling in the DSR". It sits in the sidebar
  on every page and beside the team attendance table, and it updates the moment
  someone moves to another page. It also shows who is clocked in and how many
  tickets each person has in progress. A person with the tab hidden or idle for
  five minutes shows as away.
- **Install it as an app.** On a phone or computer you can add PQ Platform to
  your home screen or desktop and open it like any other app, with its own icon.
  If the connection drops you get a clear "you are offline" page instead of a
  browser error, and a notice when you are back.
- **A new logo and favicon.** A ring with a Q tail, in the new blue and navy.
  It appears in the sidebar, on the sign-in page and in the browser tab.
- **Quick fill on the DSR.** Your open tickets show as one-click chips under the
  task box, and the hours box has 0.5, 1, 2 and 4 hour shortcuts.

### Improved

- **The punch panel is live.** It shows a clock that ticks by the second, the
  time you have been on the clock counting up in real time, a ring that fills as
  the shift goes by, how much of the shift is done and how long is left, and a
  bar for each day of this week. After checking out it says how far over or
  under a full day you were.
- **Team attendance is easier to read.** Your own row is first and marked, with a
  "Your day" card above it. Every person has a seven day strip, and clicking a
  name opens their attendance history. The counts at the top filter the table,
  and forgotten check-outs from earlier days have their own list.
- **Manual DSR entry was rebuilt.** One clear form with a big task box, category,
  status, hours and an optional note, instead of six cramped fields in one row.
- **Messages now appear in the bottom right** and stack neatly, instead of piling
  on top of each other in the top corner.
- **Phones and tablets.** Pages use the full width of a phone screen, stat cards
  and forms stack instead of running off the edge, wide tables scroll sideways
  inside their card, buttons are bigger to tap, and phones no longer zoom in when
  you tap a field.
- **New colors across the whole app.** One shared palette replaces the colors that
  were set page by page, so every screen matches.

### Fixed

- **Tapping Check in twice no longer ends your day.** The second tap used to
  check you out at once, record a day of zero hours, and stop you checking in
  again. A tap in the first minute after checking in is now ignored with a note.
- **You could not find your own attendance on the team page.** You now appear
  first, marked. Forgotten check-outs from earlier days also show up there again.
- **The elapsed time on the punch panel never counted up,** and the "Today" box
  stayed empty while you were on the clock.
- **Notes meant for developers were printing on the page** in leave, attendance
  and on any page that showed a message. They no longer appear.
- **Payroll runs are written all at once.** A failure part way through can no
  longer leave a run with some payslips missing.
- **Locking or unlocking a pay run and removing a holiday are now in the audit
  log,** and saving a monthly salary no longer records "0.00 per day".
- **Edited attendance times are checked.** A punch cannot be moved to a different
  day or into the future. An overnight shift can still end the next morning.
- **Attendance pages could break** if two shift records ever existed for a
  company. Only one is allowed now.
- **A resolved error that happens again reopens,** and several errors arriving at
  the same moment are all counted.
- **Customers behind one office network were rejected after 60 errors a minute.**
  The limit is now per key, at 600 a minute.
- **Passwords and tokens inside captured request data are hidden** before they
  are stored.
- **Live updates now work when you run the app with the standard start command,**
  including the Serop inbox, which was unreachable that way.

### Security

- **Shared server passwords are limited to owners, admins and developers.** Viewers
  and support staff can no longer read them, and only owners and admins can add a
  server.
- **Repeated wrong passwords lock sign-in for 15 minutes,** for that account on
  that network and for any one network trying many accounts.
- **Live updates only accept connections from this site,** so another website
  cannot open one using your session.
- **A production setup refuses to start on the built-in secret keys.** Set your own
  before turning debug mode off.

### Known issues

- People added to a team from Serop start as viewers, so they cannot read shared
  server passwords until an owner or admin changes their role.
- Pages are not cached for offline use. The installed app needs a connection and
  shows the offline page when there is none.

## [1.1.0] — 2026-10-03 · the sign-in page

### Improved

- **The sign-in page was rebuilt.** It now has a proper two-column layout on a
  laptop and desktop, dropping to a single clean column on a phone, instead of a
  small grey card floating in the middle of an empty screen.
- **Signing in shows that it is working.** The button reports that it is signing
  you in rather than sitting there looking broken while the page thinks about it.
- **You can see what you typed.** A button beside the password reveals what you
  entered, so a stray capital or a keyboard stuck in the wrong layout no longer
  means a failed sign-in and no idea why.
- **Browsers now fill the right fields.** Signing in offers your existing
  username and password rather than pushing you to save a new set.
- **Errors are actually announced.** A failed sign-in is read out to screen
  readers instead of only turning red, and each field's label says which field
  went wrong.

### Fixed

- **The eye icon beside the password was a giant blob.** It was drawn correctly
  but never told how big to be, so it ballooned across the field instead of
  sitting neatly inside the button.
- **The sign-in page offered by desktop apps had lost its styling entirely.** It
  fell back to bare text with no card, no spacing and no padding.
- **The "reveal password" button on that page sat too high,** overlapping the
  word "Password" rather than sitting beside the box.
- **Technical notes were printing themselves on the sign-in page.** Comments left
  in the page markup were being shown to visitors as if they were part of the
  page.
- **The "show password" button could not be reached with a keyboard.** It was on
  screen and looked usable, but any keyboard user tabbing through the page would
  skip straight past it.
- **The sign-in page had no top-level heading.** The page title was a second-level
  heading, which is why assistive technology described a page with no title. The
  branding line is now ordinary text and the page has one proper title.
- **A wrong username and a wrong password gave different messages**, which meant
  the page could tell you which accounts exist. They now read the same.
- **The page was laid out twice over**, making it unusually tall and awkward to
  scroll.
- **Signing in no longer loses your destination.** Following a link that needed
  authentication now returns you to that link afterwards instead of dropping you
  on the dashboard.

### Changed

- **The sign-in page has a quiet dotted background** instead of coloured light
  spilling in from the corners, and the panel beside the form is a flat dark
  blue rather than a bright gradient.
- **The text beside the form now just describes the app.** It listed what the
  product can do in the style of an advert; it now says plainly which parts of
  the app are covered.

### Known issues

- **Comments still print themselves as visible text on ten other screens** —
  the timesheet, team attendance, the leave calendar and its request screens.
  Each shows on the pages that render it. Not yet fixed.

## [1.1.0] — 2026-10-02 · long-running tickets & DSR day close

### Fixed

- **Your dashboard no longer breaks on a long-running ticket.** A ticket left
  open for weeks used to log an absurd number of hours against your name, and
  that was enough to crash the dashboard with an error — taking your timesheet
  and everything else on the page with it. Hours are now counted over a far wider
  range, so long-running work finally shows up as the figure it really is.

### Added

- **Today's timesheet closes at midnight.** Fill in your daily status report
  until 11:59pm and it is submitted; you no longer have to get it exactly right
  the first time. A day that has not happened yet is closed to everyone, so
  nobody can log hours they have not worked.
- **Older days stay open for checking.** Every past report is still readable, so
  you can look back at any earlier day, copy its summary and compare it, without
  being able to rewrite what you already submitted.
- **Managers can still put right a closed day.** An owner or admin can correct a
  past report for anyone, so a forgotten entry or a typo is never stuck.

## [1.1.0] — 2026-10-02 · one dropdown across the app

### Improved

- **Every dropdown in the app now looks the same.** Filters, sort menus, status
  and priority pickers, leave types, colours, categories and employee pickers all
  share one control instead of the browser's plain grey box, so the app reads as a
  single product rather than a mix of styles.
- **Filters still work the moment the page loads.** Choosing an option reloads
  the list exactly as before, and a filter you have not touched is still sent
  along, so nothing quietly drops out of your results.
- **"All" is back where it should be.** Clearing a filter to see everything is
  available again on every list screen.
- **People are shown by name, properly.** Dropdowns listing team members used to
  show the wrong text for some entries; they now show each person's name and fall
  back to their username, the same as everywhere else in the app.
- **Leave-type colours and the staff rows in the timesheet** use the new control
  too, without losing their colour coding.

### Fixed

- **Leave settings no longer look unlabelled.** The colour picker and the day
  limits are each clearly marked, so it is obvious what each number means.
- **The activity log filters** and the ticket filters no longer leave a filter
  with no way back to showing everything once you picked one.

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
