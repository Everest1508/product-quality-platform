# Changelog

This is what the **What's new** button in the sidebar shows, so write it for the
person using the app: what they can now do, what got easier, what was broken.
No class names, no field names, no test names, no file paths — if a change needs
that kind of detail it belongs in `AGENTS.md` instead, which is where the
engineering invariants live.

Format follows [Keep a Changelog](https://keepachangelog.com/). Each release starts
with a line beginning `> In short:` that says what it is about in one sentence, then
New, Better, Fixed and Security lists. Older releases are below the newest.

## [1.55.0] "Dove" — 2026-10-26 · early-bird greetings and who is in today

> In short: checking in before the shift starts now gets a friendly line, and owners and admins see who is in today on Home.

### New

- **A friendly line when you check in early.** It shows as a badge in your Today box and in the check-in message. There are several lines, and you get a different one each day.
- **A "Team today" card on Home for owners and admins.** It lists everyone who has punched in today, when they came in, and when they left or that they are still working.

## [1.54.1] "Dunnock" — 2026-10-23 · project costing page that shows every calculation

> In short: saving a project in Project costing now opens a page that explains every number in plain steps.

### New

- **A project page that shows how every number is worked out.** It walks through what each person costs, rent, AI and other charges, the total cost, and then the price, profit and margin, each with the sum written out.

### Better

- **Saving a project takes you to that page.** You used to stay on the form after saving. Clicking a project in the list opens the same page, and an Edit button there takes you back to the form.

## [1.54.0] "Chickadee" — 2026-10-23 · newest tickets first, rows per page, creation dates

> In short: the ticket board shows the newest tickets at the top, every table lets you pick how many rows to show, and tickets show when they were created.

### New

- **Choose how many rows a table shows.** Every table with pages now has a Rows per page menu (10, 20, 50 or 100) next to the "1–10 of 16" count. Your choice stays while you move between pages and filters.
- **Tickets show their creation date.** Each card on the board shows the day it was created, and the ticket lists have a Created column beside Updated.

### Better

- **The ticket board lists the newest tickets first.** Within each column the latest ticket is at the top and the oldest at the bottom, instead of ordering by priority first. You can still sort by priority from the sort menu.
- **Tables show 20 rows by default.** It used to be 25, so it matches the new menu.

## [1.53.2] "Chiffchaff" — 2026-10-23 · stack traces back on the project error page, and search finds team leave

> In short: the stack trace shows again on a project's error page, and approvers can search everyone's leave requests.

### Better

- **Approvers can search team leave.** Owners, admins and leave approvers now find other people's leave requests by name or reason from the search bar, under a Team leave group that opens the approvals page. Everyone else still finds only their own leave.

### Fixed

- **The stack trace was missing on a project's error page.** Each occurrence on the error page opened from a project now shows its stack trace underneath, as the main Errors page already did.

## [1.53.1] "Bushtit" — 2026-10-19 · a tidier sidebar and the Expenses page laid out properly again

> In short: the Admin menu is split into small groups, and the Expenses page and its Add expense form look right again.

### Better

- **The Admin menu is split into smaller groups.** Admin now has People (team attendance, timesheet, corrections, leave approvals, leave policy, team), Money (payroll, payroll setup, expenses, project costing) and System (audit log, automation). Each group opens on its own, remembers whether you left it open, and the one holding your current page opens by itself. An open group sits in a soft panel, the page you are on lifts out of it, every item has its own icon, and the sidebar has Workspace and Admin headings.

### Fixed

- **The Expenses page is laid out properly again.** The filters sit in one row, the total shows "Total spent · October 2026", the amount and the count as separate pieces, the category and payer summaries line up in a side column, and the Add expense form has normal spacing. The empty-state icon is no longer huge, and date fields on Firefox show one calendar icon instead of two.
- **The date field in the Add expense form was stretched tall.** It is a normal height again.

## [1.53.0] "Bulbul" — 2026-10-19 · work out what a project costs and what to charge

> In short: owners and admins get a Project costing page where you type the people, hours and costs of a project and see what it costs us and what to charge.

### New

- **Project costing for owners and admins.** Open **Project costing** under Admin, add a project, its team with their salaries, office rent, AI cost and any other charges, and the total cost and the price appear as you type. Nobody else can open it, and nothing is taken from payroll or attendance: you type every salary yourself.
- **Margin and your own pitch price.** Add a margin percent as a markup on cost or as a true margin on the price, and type a pitch price to see the profit it leaves. You can save, reopen and duplicate estimates.
- **A report over your saved estimates.** The Project costing page adds up cost, price and profit, shows them by client, can be narrowed to one month, and exports to a spreadsheet. Set an estimate's quote date to add an old quote under the right month.
- **A client quote with line items.** The quote page for each estimate lists the team, office and other items with their prices and a total, on a BeForth quotation layout that can be printed. It never shows salaries, rates, costs or margin.

### Better

- **Pages open faster.** The app's look used to be sent again inside every page, about 230 KB each time, and nothing was compressed. It is now one file your browser keeps, and pages are compressed, so a page is a fraction of what it was.
- **The ticket board opens much faster with many tickets.** Each column shows its first 30 tickets with a "Show more" link for the rest, and the counts still include every ticket. With hundreds of tickets the page used to be over a megabyte.
- **BeForth fonts everywhere.** Text is DM Sans and headings are Manrope across the whole app, not only on Project costing.
- **Project costing looks like your estimates screen.** The list is a table with a search box and totals on top, and each estimate has a row of cost, price, profit and margin cards above its form, with the margin and results in a side column. The pages use DM Sans for text and Manrope for headings and figures.

### Fixed

- **The online panel could show an error when the live connection was down.** If the live connection could not be reached, the fallback check-in could fail with a server error. It now always records that you are here.
- **The DSR log could not be scrolled to its last rows.** On some screen sizes the table was squeezed into a short box and the rows below it were cut off. The table now takes the height it needs and the page scrolls to the end.

## [1.52.7] "Auklet" — 2026-10-17 · weekly off days you choose, punch in on Home any day, and a thread on each expense

> In short: you choose which days of the week are weekly offs and nothing counts against anyone on them, Home lets you punch in on any day, and every expense has a discussion for owners and admins.

### New

- **Choose your weekly off days.** Owners and admins can pick the days nobody is expected to work from the **Weekly off** button on Team attendance. It starts as Saturday and Sunday. Payroll and leave count the days you pick as non-working from then on, and pay runs you have already locked do not change.
- **Every expense has a discussion.** Under each expense, owners and admins can ask about a bill or agree what to do with it. Nobody else can see it. The other owners and admins get a notification, the Expenses list shows how many comments each one has, and you can delete your own comments.

### Better

- **Work on a weekly off day carries no rules.** Checking in or out on one is never late, never a penalty or a half day, and the day is never short or absent. The punch card says it is a weekly off instead of showing the shift countdown, and Team attendance shows "Weekly off" instead of "Absent".
- **Punching from Home brings you back to Home.** You used to land on the Attendance page after pressing Punch in or Punch out on Home.

### Fixed

- **Punch in was missing from Home on Saturday and Sunday.** The Today card hid the button on weekends and just said "Weekend". It now shows on every day, and says when it is a weekly off.
- **Home showed worked hours before the break was taken off.** After you punched out, the Today card showed 8.5h for a 10:00 to 6:30 day. It now shows 8h, like the rest of the app.

## [1.52.6] "Wheatear" — 2026-10-16 · a team member you remove can no longer sign in

> In short: a person you remove from a team can no longer sign in or start a company of their own, and sees a message telling them to ask an owner or admin to add them back.

### Fixed

- **A removed team member can no longer sign in.** Removing someone used to leave their login working, and their next page offered to set up a brand new company that they would own. They are now stopped at the sign-in page with a message to ask an owner or admin to add them back.
- **Someone removed while signed in is signed out on their next click.** They no longer stay in the app or get offered a new company: they land on the sign-in page with the same message. People who are still in another workspace simply lose the one they were removed from.
- **A removed member's open tab stops showing who is online.** The live "online now" list used to keep updating in a tab that was already open when the person was removed. It now disconnects within a few seconds of the next heartbeat.

### Security

- **Starting a new company is closed to people who belong to no workspace.** It is still there for the first person on a new install and for staff accounts, so setting up a fresh install works as before.

## [1.52.5] "Veery" — 2026-10-16 · long task names no longer stretch the DSR log

> In short: the DSR log fits more entries on screen because long task names stop at two lines, with the full name shown when you hover.

### Better

- **Long task names in the DSR log stop at two lines.** A long commit message used to make its row very tall. It now shows two lines, and the full name appears when you hover over it.

## [1.52.4] "Towhee" — 2026-10-16 · long lists scroll, and the DSR log shows more rows

> In short: dropdown lists and the date picker stay open while you scroll them, and the DSR log table is no longer squeezed into a small box.

### Fixed

- **Long dropdown lists can be scrolled again.** Scrolling a dropdown or the date picker used to close it before you could reach the last options. It now stays open.
- **The DSR log shows many more rows at once.** The table is no longer boxed into a small scrolling area, and category and project names stay on one line so each row is shorter.

## [1.52.3] "Sandpiper" — 2026-10-16 · punching in no longer fails when the app is busy

> In short: checking in or out waits its turn when other people are saving at the same moment, instead of showing a "database is locked" error.

### Fixed

- **Check in and check out no longer fail with "database is locked".** When several people saved something at the same moment, a punch could be turned away with an error page. It now waits a few seconds for its turn and goes through.

## [1.52.2] "Ouzel" — 2026-10-16 · the What's new close button is back in the corner

> In short: the cross that closes the What's new window sits in its top right corner again instead of under the title.

### Fixed

- **The What's new close button is in the corner.** It had slipped down below the heading; it is back at the top right of the window.

## [1.52.1] "Jacana" — 2026-10-16 · tagging works in the project log

> In short: typing @ in a project's log now suggests everyone who can open the project, so you can tag people even when the project has no Pod yet.

### Fixed

- **Tagging people in the project log.** The @ list was empty on projects with no Pod, so nobody could be tagged. It now offers the Pod first, then everyone else who can open the project, and tagging them notifies them.

## [1.52.0] "Lapwing" — 2026-10-16 · move a card from its own menu

> In short: every kanban card has an arrow that lists the statuses so you can move it in one click, and the Projects board now has search and filters like the tickets board.

### New

- **Move a card without dragging.** Each ticket and project card has an arrow icon; click it, pick a status or phase, and the card goes there.
- **Search and filters on the Projects board.** Find a project by name, narrow by lead, or show only projects that are running late or have a Crunch.

## [1.51.3] "Phoebe" — 2026-10-16 · a calmer greeting with a reaction for every line

> In short: the greeting on Home types and changes at a relaxed pace, and Pintu gives each line its own short reaction and then holds one face while you read.

### Better

- **A slower, calmer greeting.** Pintu waves first, then the line types out gently, stays on screen long enough to read, and pauses before the next one.
- **One reaction per line.** Each of the 36 lines has its own two or three faces from Pintu, ending on the face he keeps while the line is on screen, instead of flicking through frames.

## [1.51.2] "Merganser" — 2026-10-16 · My work opens out in the sidebar

> In short: My work is now a dropdown in the sidebar with Attendance, Leave, Calendar, DSR and Payslips one click away, and the bell on the DSR notices card is back to its normal size.

### New

- **My work is a dropdown.** Open it in the sidebar to go straight to Attendance, Leave, Calendar, DSR or Payslips. It opens by itself on those pages and remembers whether you left it open.

### Fixed

- **A huge bell on the DSR page.** The "Needs your attention" card on the DSR page showed an oversized bell icon. It is small again.

## [1.51.1] "Sparrow" — 2026-10-15 · meet Pintu on Home

> In short: Pintu, a small teal robot, now sits in the Home greeting and acts out every line of text with his own pixel frames, and the greeting has more funny lines.

### New

- **Pintu on Home.** Pintu waves hello, then plays his own pixel frames for each line as it is typed: sleepy for the slump line, a cool face and party for shipping, hearts and his drink for chai, dizzy for too many tabs. No two lines play the same frames.
- **More funny greeting lines.** There are nine for each time of day, and each visit starts on a different one.

### Better

- **Leave balance is a normal card.** It sits under your assigned tickets instead of inside a "More" fold, and an uncapped type like Unpaid no longer shows a full bar.

## [1.51.0] "Tanager" — 2026-10-15 · Expenses, better search and a tidier Home

> In short: a new Expenses page for owners and admins, wider search, a tidier Home, and a 30 minute office break.

### New

- **An Expenses page for owners and admins.** Add what it was for, the amount, who paid, the date and a category (Tea, Milk, AI subscription, Server rent, Team trip, or Other, where you type what it was) from an Add expense button.
- **Filters and totals.** Pick a month (or all time), a category, who paid, or search the details. The total, the spend by category and the amount each person paid follow your filters.
- **Export to CSV.** Download what you are looking at as a spreadsheet, with a total at the bottom.

### Better

- **A tidier Home.** Today, your assigned tickets and the week chart now stack neatly on the left, and your to-do list runs the full height on the right, with a scrolling list when it gets long. Empty cards no longer take up a big blank space.
- **Search finds more.** The top search box now also looks through expenses and attendance corrections (owners and admins), project updates, and your notifications.
- **Button names are no longer cut off.** The little name that appears over an icon button, including in the top bar, now always shows in full.
- **The office break is 30 minutes.** Hours worked are now counted net of a 30 minute break (1:00 to 1:30 pm), so a 10:00 to 6:30 day is 8 hours everywhere.
- **Hours match the week bars.** The punch panel, history and Today figure show the same hours as the bars, instead of the longer raw time.
- **Everyone hears who decided a correction.** When an owner or admin approves or rejects an attendance correction, the other owners and admins are told.

## [1.50.1] "Whimbrel" — 2026-10-14 · every project action is in the Audit log

> In short: everything done on a project now appears in the Audit log, and people taken off a Pod are told.

### Better

- **Project actions are in the Audit log.** Moving a phase, writing in a project's log, changing the plan or the Pod, and adding or finishing a Crunch item are all recorded with who did it and when, and you can filter the log by them.
- **People taken off a Pod are told.** They get a notification, just as people added to a Pod do.

## [1.50.0] "Siskin" — 2026-10-14 · a simpler app, with smoother movement

> In short: the sidebar is much shorter, project settings live in one place, Home keeps only what you need today, the DSR has one notices card, and the whole app moves more smoothly.

### Better

- **A shorter sidebar.** Home, Projects, Tickets, Errors, Feedback, My work and Reports are always there, and everything for admins is folded into one Admin group that remembers whether you left it open.
- **My work brings your own pages together.** Attendance, Leave, Calendar, DSR and Payslips share one set of tabs, so they feel like one place.
- **Project settings are in one place.** The Plan, versions and webhook, API keys and team access are sections on a single Settings page that you open one at a time.
- **A calmer Home.** It keeps your tickets, today's punch with how much of the day is in your DSR, your to-do and your week, and puts leave balance under More.
- **One notices card on the DSR.** Long-open tickets, tickets you have not logged and locked days now appear in a single Needs your attention card instead of stacked bars.
- **Smoother movement everywhere.** Pages fade between each other, cards and rows rise in one after another, buttons respond when pressed, menus pop open, folds slide, and bars grow to their value. It all switches off if your device is set to reduce motion.

## [1.49.0] "Greenfinch" — 2026-10-14 · pick any dates on the DSR and see today's progress

> In short: the Daily Status Report has From and To date pickers, and a bar showing how much of today's time at work is in your DSR.

### New

- **Pick any dates on the DSR.** Choose a From and a To date to see exactly that span, up to a year, and the CSV export follows the same dates.
- **How much of today is logged.** A bar at the top shows how much of the time you have worked today is already in your DSR and how much is left, and with no punch yet it compares against a full working day.

## [1.48.1] "Waxwing" — 2026-10-14 · tagging, ticket page layout and New ticket in a project

> In short: the list of people when you type @ is now visible, ticket pages use the full width, and New ticket remembers the project you are in.

### Better

- **Ticket pages use the width of the screen.** The ticket is no longer squeezed into a narrow column in the middle, with big empty sides.
- **New ticket remembers your project.** From inside a project, the New ticket link in the top bar creates the ticket in that project, and a link with a project in it opens the form with that project already chosen.

### Fixed

- **The list of people when you type @ was cut off.** It now opens above the comment box, so you can see everyone you can tag.
- **A ticket page could fail to open.** If its history had an entry made by the system rather than a person, the page showed an error instead of the ticket.

## [1.48.0] "Pewit" — 2026-10-14 · the Projects release goes live

> In short: this release carries the new Projects pages, the Pod and the project log to everyone, and updates the database on its own when the app starts.

### Better

- **The Projects pages are live.** The board, the journey view, the project log and the clearer project form are all part of this release, and the database is updated automatically the first time the app starts.

## [1.47.0] "Yellowthroat" — 2026-10-14 · one Projects list, clearer forms and roomier pages

> In short: products and projects are now one thing called Projects, the project form says what is needed and what each part is for, and pages have more breathing room.

### Better

- **Products and projects are one thing.** The sidebar has a single Projects entry, with Board, Journey and List views, and the New project button opens the full project form.
- **The project form says what is needed.** Only the name is required, every section is marked Required or Optional, and each one explains what it is for.
- **Choosing the Pod is clear.** Each person is a card with their name, username and role, a visible tick, a count of how many you picked, and a search box when the team is big.
- **Crunch rows are labelled.** The form explains that a Crunch item is a feature that must be ready before the project ends, and its fields say what to enter, with an example.
- **Cards have room to breathe.** Project pages and the Home grid use a consistent spacing scale, so cards no longer sit tight against each other.

### Fixed

- **The Design kit page is gone.** It was only a showcase and is no longer in the sidebar.

## [1.46.0] "Whinchat" — 2026-10-14 · project phases, a Pod and a full log

> In short: every project now has a life from Creation to Close, with a board, a journey view, a team called the Pod and a dated log of everything that happens.

### New

- **A Projects board.** Nine phases, one column each: Creation, FE, BE, Connection, Deploy, Testing, UAT, Live and Close. Add a project in any column and drag it along.
- **A Journey view.** One row per project shows how far it has got, with the date each step was reached, and you can click a step to move there.
- **A reason for every move.** The project lead, the Pod, owners and admins can move a project, and they always say why. The reason is saved with their name and the time.
- **The Pod.** The people assigned to a project can write updates, blockers and decisions in its log, tag each other with at-names, and everyone on the Pod is told.
- **A full log for every project.** It runs from creation to close with exact times, and entries cannot be edited, only corrected with a new entry.
- **A plan for each project.** Set dates, tech stack, the SRS, which phases the project uses and a schedule for each phase, and unused phases are grayed out and skipped.
- **Crunch items.** List features that must ship before the project ends, each with a due date and reason, and see the next one on the project card.

## [1.45.0] "Pipit" — 2026-10-14 · a bento Home, calmer colours, faster ticket lists

> In short: Home is laid out as a grid of cards that fill the space, the yellow tones are gone, attendance numbers are tidier, and the ticket lists load faster.

### Better

- **Home is a grid of cards that fill the space.** Empty cards no longer leave a hole, and the to-do card keeps its list inside the card and scrolls when it grows.
- **No more yellow.** The greeting banner is now blue and violet, and warnings use a softer orange.
- **Attendance numbers are tidier.** The team attendance counts are separate cards with the icon beside the number, and long labels no longer break awkwardly.
- **Ticket lists load faster.** Showing who is assigned no longer asks the database once for every ticket.

## [1.44.0] "Cetti" — 2026-10-14 · a design kit page with every component and icon

> In short: a new Design kit page shows all 199 befui components and 350 icons with the HTML to copy, and the animated befui icons are available on every page.

### New

- **A Design kit page.** Open it from the sidebar to see buttons, badges, tabs, inputs, dropdowns, windows, confirmations and toasts, each with the code to copy.
- **The whole befui icon set.** 283 more icons can be used anywhere, and they redraw themselves when you hover over them.
- **All 199 befui components, as plain HTML.** The Design kit lists every one with a live demo and the code to copy, in light and dark. Pages can use tags like bef-button and bef-dialog with no React.
- **Click an icon to copy its tag.** The Design kit lists every icon with a search box, so you can find one and paste it straight into a page.

## [1.43.2] "Dollarbird" — 2026-10-14 · dropdowns open on top of pop-ups, and What's new shows once

> In short: the dropdown lists and date pickers in pop-up windows, such as Log work in the DSR, now open in front of the window instead of behind it.

### Fixed

- **Dropdowns opened behind the Log work window.** Project, category, status and date lists now appear on top of any pop-up window, so you can pick from them.
- **What's new opened on every visit for some browsers.** It now remembers that you have read a release even when the browser blocks or clears its usual storage, so it shows once per release.

## [1.43.1] "Dotterel" — 2026-10-14 · a product switcher you can actually switch with

> In short: the product dropdown in the sidebar lists every product you can open, with a search box when there are many.

### Better

- **The product dropdown lists all your products.** Pick one straight from the sidebar, with "View all products" pinned underneath.
- **Find a product by typing.** With more than a few products, a search box at the top of the dropdown narrows the list as you type.

### Fixed

- **The dropdown could show only "View all products".** The product you are on is now always in the list, and the list scrolls on its own so the link stays visible.

## [1.43.0] "Cuckoo" — 2026-10-14 · pick an icon for each product, and centred windows

> In short: every product can now have its own icon, shown in the list and the product switcher, and pop-up windows open in the middle of the screen again.

### New

- **Choose an icon for each product.** Pick one when you create or edit a product, and it replaces the plain letter tile in the products list and the product switcher.

### Better

- **The product switcher shows each product with its icon.** Jump between products from the sidebar without going back to the list.

### Fixed

- **What's new and confirmation windows opened in the top-left corner.** They now open in the middle of the screen.
- **The Settings page sat against the left edge.** Every tab in your profile is now centred.

## [1.42.0] "Bobolink" — 2026-10-14 · back to the fast, simple pages, with a how-to for the SDK

> In short: the app is back to pages that load straight from the server in its new look, with dark mode, a friendlier Home, and a step-by-step SDK guide for every framework.

### New

- **Dark mode and a refreshed look everywhere.** Switch themes from the top bar, and every page, table and window follows.
- **A friendlier Home and a one-table DSR.** The greeting types itself out, and the DSR sheet shows each day as a single table with honest hours for long tickets.
- **Keyboard shortcuts that work on Mac, Windows and Linux.** The full list is in your profile, and the command palette can run actions.
- **An SDK guide for each framework.** Pick Python, Django, Flask, FastAPI, Express, Fastify, Koa, NestJS, Electron or the browser on a product's API page, or open the SDK guide tab in your profile beside Settings.
- **A box before you punch out.** It tells you the day is ending and shows the total time worked.
- **A confirmation before anything is deleted.** Every delete now says what will be removed and asks first.

### Better

- **Pages are plain server pages again.** There is nothing extra to download or build, so the app opens faster and works the same everywhere.
- **Reporting errors from your app no longer waits on Discord.** The message is sent in the background, so a slow Discord cannot delay your app.
- **API keys no longer write to the database on every request.** The last used time is refreshed at most once a minute.

### Fixed

- **The install command was wrong.** The SDK is installed with pq-befu, not pq-sdk, and the README now says so.

## [1.41.0] "Redstart" — 2026-10-14 · the app can be hosted on its own address

> In short: the app can now run on a separate host such as Vercel while the server stays where it is, and signing out no longer needs a page form.

### New
- **The app can be hosted on its own address.** Set it up once and the screens come from a static host while the server keeps your data. The default, where the server serves everything, is unchanged.

### Better
- **Signing out works the same everywhere.** It now signs you out through the server and shows the sign-in page.
- **Opening a notification works from a separately hosted app.** It is marked read and opens in the app you are already using.

## [1.40.2] "Meadowlark" — 2026-10-14 · no pay widget on Home

> In short: Home no longer shows a pay card.

### Better
- **Home no longer shows your pay.** The pay card is gone, so the bottom row holds only your week, your leave and your DSR. Your payslips are still under My payslips in the sidebar.

## [1.40.1] "Skylark" — 2026-10-14 · much faster loading

> In short: pages open much faster, and opening another page of the app downloads almost nothing.

### Better
- **The first load is about five times smaller.** The app is now split into pages that load when you first open them, and the files are sent compressed, so the first screen downloads about a fifth of what it did.
- **Opening another page, or refreshing, downloads almost nothing.** The browser only checks whether the app changed, and reuses what it already has.
- **The search box no longer calls the server on every page.** It only asks when you open it.
- **The Docker version starts the server directly.** It no longer runs the development server with its file watcher.

## [1.40.0] "Nightingale" — 2026-10-13 · long-open tickets ask for your real time

> In short: a ticket that was open for a long time shows how long it took, but counts no time in your DSR until you enter the time you really worked on it.

### New
- **You are asked for your time on a long-open ticket.** When you resolve a ticket that was open for more than a working day, a message tells you to add the time you worked on it today, and the DSR opens a small window to enter it.
- **A banner stays on the DSR until you add the time.** The row shows an Add time button, and only the time you enter counts.

### Better
- **A long-open ticket no longer adds weeks to your day.** Its row shows how long it was open, such as "open for 11d 1h", marked as not counted, so the real elapsed time is still there to read.
- **The cleanup command keeps the open-for time.** Old rows with huge hours stop counting but still show how long they took, instead of being cut to a fixed number.

## [1.39.1] "Wigeon" — 2026-10-13 · how long a ticket was open

> In short: an auto-logged DSR row now says how long its ticket was open, so the real elapsed time is never lost.

### Better
- **The DSR shows how long a ticket was open.** Under an auto-logged task you now see its created and completed times and, beside them, how long it was open, such as "open for 11d 1h".

## [1.39.0] "Thrasher" — 2026-10-13 · What's new shows itself once

> In short: when the app is updated, the What's new window opens by itself one time so you can read it, and stays one click away in the sidebar.

### New
- **A new release is shown to you once.** A moment after you open a page, What's new opens with the latest changes, and it will not open again until the next update.
- **A feature guide and a guide to running the project.** They explain what was added, when, why and how to use it, and how to set the app up and run it.

### Better
- **What's new stays in the sidebar.** Open it any time to read an update again, search it, or look back through older releases.

## [1.38.1] "Bluethroat" — 2026-10-13 · a smoother What's new

> In short: the What's new window and its cards now open, close and slide in smoothly.

### Better
- **The What's new window rises in and fades out.** It no longer pops in or vanishes.
- **A release card opens and closes smoothly.** Its height glides and its content fades in, whatever its length.
- **Release cards slide in one after another.** Older releases, search results and filters arrive in a short cascade.
- **People who prefer reduced motion see none of this.** The window and cards simply appear and disappear.

## [1.38.0] "Cormorant" — 2026-10-13 · a calmer What's new

> In short: the What's new window is easier to scan, search and filter.

### Better
- **Each release is its own card on a timeline.** You see the version, its name, the date and how many changes it holds, and the newest one starts open.
- **You can search the whole history.** Type a word and every release that mentions it opens with the matching changes.
- **The type buttons count what is behind them and look through every release.** Pick Fixed or Security to see only those, all the way back.
- **Older releases load a few at a time.** Open one by clicking it, instead of scrolling through all of them at once.

## [1.37.1] "Hoopoe" — 2026-10-13 · the right shortcut hint

> In short: the search box now shows the shortcut your computer actually uses.

### Fixed
- **The search box said Ctrl K even on a Mac.** It now shows ⌘ K on a Mac and Ctrl K on Windows and Linux.

## [1.37.0] "Kite" — 2026-10-13 · reminders, one-click DSR and a smoother board

> In short: attendance reminders, adding all your worked tickets to the DSR in one click, and a friendlier board, notifications page and loading screens.

### New
- **Attendance reminders.** You are nudged shortly after your shift starts if you have not checked in, and again after it ends if you have not checked out. Each can be switched off in your profile.
- **Add everything you worked on to the DSR in one click.** A banner on the DSR lists the tickets you touched today and adds them all at sensible hours.
- **Compact cards on the board.** One button shrinks the cards to the key, title and people, and your choice is remembered.

### Better
- **Hover a board card to peek at it.** A small card shows the status, priority, people and due date without opening the ticket.
- **Cards lift when you drag them and settle in when dropped.** Moving a ticket now feels like moving a thing.
- **Notifications are grouped by day.** Each one has an icon for its kind, and you can filter by type.
- **Long forms keep Save in reach.** The Save and Cancel buttons stay at the bottom of the window while you scroll.
- **Loading screens now look like the page that is coming.** Tickets, boards, forms, details and lists no longer jump when the data arrives.

## [1.36.0] "Puffin" — 2026-10-13 · exports, team pages, notification settings and tidier pages

> In short: export your data, open a colleague's page, choose what notifies you, and see a ticket's whole story in one column.

### New
- **You can export to a spreadsheet.** The DSR, the attendance timesheet and each payroll run have an Export CSV button.
- **Every team member has their own page.** Click a name in Team to see their streak, their numbers and the open work of theirs you are allowed to see.
- **You choose what notifies you.** The new Notifications tab in your profile has a switch for each kind of notification.
- **Ticket pages show one activity timeline.** Status changes, priority changes, assignments and comments appear together in time order.
- **The search box can do things.** Press Ctrl or ⌘ K and type "leave", "log" or "punch" to jump straight to the action.

### Better
- **Attendance is one tidy sheet.** The month calendar and your days sit side by side under one set of figures.
- **Charts replaced the hand-drawn bars.** The week, error history, survey scores and product trends use the same charts as Reports.
- **Tables are easier on a phone.** Tickets and the DSR hide their less important columns on small screens.

## [1.35.0] "Wagtail" — 2026-10-13 · friendlier, with more keyboard shortcuts

> In short: celebrations, an on-time streak, milestones, friendlier empty and error pages, and many more keyboard shortcuts.

### New
- **Keyboard shortcuts for moving around.** Press g and then h, t, e, p, d, a, l, r, m or u to jump to Home, Tickets, Errors, Products, DSR, Attendance, My leave, Reports, Team or your profile.
- **More shortcuts for everyday things.** Press t to switch light and dark, and [ to fold the sidebar. They work on Mac, Windows and Linux, and show ⌘ on a Mac and Ctrl elsewhere.
- **A list of every shortcut lives in your profile and the account menu.** Press ? anywhere to see it too.
- **An on-time streak.** Your profile and the Today card show how many working days in a row you checked in on time, and leave and holidays do not break it.
- **Milestones get a line of praise.** A work anniversary or a round number of resolved tickets shows on Home and in your profile.
- **Small celebrations.** Confetti when you resolve a ticket, tick the last to-do, or finish a full working day.

### Better
- **The numbers on Home count up when the page opens.** It is a small touch that makes the page feel alive.
- **Empty states look friendlier.** A missing page, or a page that fails, now says so calmly and gives you a way back.
- **The greeting icon redraws itself when you hover it.** The strokes draw in again, one by one.

## [1.34.1] "Thrush" — 2026-10-13 · a friendlier greeting

> In short: the Home greeting types out its lines, and its icon wiggles when you hover it.

### Better
- **The greeting line on Home now types itself out.** It cycles through a few lines for the time of day, and stays still if you prefer reduced motion.
- **The greeting icon reacts when you hover it.** It grows and wiggles a little.

## [1.34.0] "Starling" — 2026-10-13 · ask before punching out or deleting

> In short: punching out now shows how long you worked, and every delete asks first.

### New
- **Punching out asks first and shows your time.** A box says you will be punched out for today and how long you have worked so far.

### Better
- **Every delete now asks before it happens.** To-do tasks, product versions, removed product access, holidays and withdrawn leave all show a box explaining what will be removed.

## [1.33.0] "Rook" — 2026-10-13 · profile, greeting, tooltips and honest DSR hours

> In short: you get a profile page, a greeting that follows the time of day, tooltips on icon buttons, a toast for every change, and DSR hours that no longer count weeks.

### New

- **A profile page.** Your name, role, company, since when you've been a member and your last sign-in, five numbers about your work, your recent activity, and your settings on a second tab.
- **A greeting that follows the clock.** The Home banner changes colour and icon through morning, afternoon, evening and night, with one line for the moment.
- **Tooltips on icon buttons.** Hover or focus an icon-only button and it says what it does.
- **Line and bar charts from the shared library.** The report's day by day chart and the week on Home.

### Better

- **Every change shows a toast.** Anything the server confirms, such as adding or removing a holiday, appears as a message, errors stay longer, and the same message never shows twice.
- **Links no longer reload the whole app.** Links inside the page, the New menu and notifications switch pages in place, so the live online list stays steady.
- **My to-do is back on Home.** It sits beside Today instead of hiding in a tab.
- **Payroll setup fits the screen.** The Save button is no longer cut off.

### Fixed

- **A resolved ticket no longer logs weeks of hours in the DSR.** It logs at most one working day and keeps its created and completed times, shown on the entry. The `fix_dsr_hours` command caps entries logged the old way.

## [1.32.0] "Pelican" — 2026-10-13 · team and CS Hub strips, and a smoother sidebar

> In short: the team list and the CS Hub follow the same strip style as the rest, and the sidebar slides open and closed.

### Better

- **The team is a list of strips.** Each member has a coloured edge for their role, their avatar, role and leave-approver badges, and Edit and Remove beside them.
- **The CS Hub reads as one sheet.** The four headline numbers are one divided strip, products are strips coloured by their rating, and the surveys and sentiment panels share one sheet.
- **The sidebar animates.** It glides between wide and narrow with its labels fading in, and on a phone it slides in from the edge and slides back out.

## [1.31.0] "Oriole" — 2026-10-13 · ledgers and sheets

> In short: surveys, automation rules and reports follow the products page, so lists read as full-width strips and reports as one divided sheet.

### Better

- **Surveys and automation rules are strips.** A coloured edge shows state (active, draft, closed), a short badge shows the type or severity, and the numbers sit in a divided row with the actions beside them.
- **Reports read as one sheet.** The five headline numbers are one divided strip and the charts share one panel with hairline dividers instead of separate cards.
- **One list style across the app.** The strip is a single shared piece, so the next list that needs it looks the same.

## [1.30.1] "Nuthatch" — 2026-10-13 · products as a ledger

> In short: the products page is a list of full-width strips instead of cards.

### Better

- **Each product is one strip.** A coloured edge shows its health, the product key stands in as its badge, and errors, tickets, versions and keys sit in one divided row with the last seven days of errors beside it.

## [1.30.0] "Merlin" — 2026-10-13 · a spreadsheet DSR, and simpler product and ticket pages

> In short: the DSR reads like a spreadsheet, and the product and ticket pages show one thing at a time.

### New

- **The DSR is a spreadsheet-style grid.** Date, task, project, category, time and status each get a bordered column, with the day's total in the date cell and an Employee column when you look at everyone.

### Better

- **The product page has tabs.** Roadmap, Versions, API keys, Team access and Integrations each have their own tab instead of one long page, and the open errors, tickets and surveys are quick links under the title.
- **The ticket page is one clear column.** Status, priority, assignee and deadline sit in a single row under the title, then the description and the comments.

## [1.29.0] "Linnet" — 2026-10-13 · a calmer Home and a DSR you can read

> In short: the DSR is now one table of everything submitted, today and before, Home is much simpler, and switching theme fades smoothly.

### New

- **The DSR is one table.** See today and past days together, grouped by day with a total, then search it, pick Today, Yesterday, Last 7 days or Last 30 days, and fix or delete an entry from the row.
- **Owners and admins can read everyone's DSR in one list.** Pick Everyone or one person, and the table adds a Person column.
- **Log work opens in a small window.** It has the form and the suggestions from your own tickets, so the page itself stays clear.

### Better

- **Home shows what matters first.** Your tickets, what is due and your to-dos share one tabbed card, with Today and This week beside it and Pay, Leave and DSR as short summaries.
- **Switching theme fades smoothly.** The page no longer jumps between light and dark.

## [1.28.1] "Kingfisher" — 2026-10-13 · icons on every button

> In short: every button now has an icon next to its words, and the whole app uses one icon set.

### Better

- **Buttons show an icon and a label.** Save, Add, Delete, Approve, Sign in, Print and the rest tell you what they do at a glance.
- **One icon set across the app.** Menus, tables, the sidebar and forms all draw from the same icons, so weights and sizes match.

## [1.28.0] "Junco" — 2026-10-13 · the whole app, in one design

> In short: every page now uses the same design and components, with a dark theme, calendar and clock pickers, and a faster, steadier experience from sign-in to payroll.

### New

- **One look across the whole app.** Home, tickets, errors, products, feedback, automation, attendance, leave, payroll, team and settings all share one set of tables, filters, buttons, forms and screens for empty and failed pages.
- **A dark theme and a calendar picker for every date.** Choose Light, Dark or System from your account menu.

### Better

- **Pages open faster and move between each other without a reload.**
- **Forms refuse odd input with a clear message.** You no longer land on an error page, and double clicks no longer send things twice.

### Security

- **You can't approve your own leave while another approver is available.** The old admin pages are gone too.

## [1.27.0] "Ibisbill" — 2026-10-13 · pickers, board and charts

> In short: dates and times are chosen from a calendar and a clock, the ticket board and charts use the same library as everything else, and buttons look the same everywhere.

### New

- **Calendar and clock pickers.** Every date, date and time, and time field opens a calendar or a clock, with days that can't be chosen greyed out.

### Better

- **The ticket board has a new look.** Drag cards between columns, or move one with Alt and the arrow keys.
- **Charts are drawn by the same library.** The ticket status ring on Home, the report rings and the product sparklines.
- **Payslips read as a clean list of lines.** Buttons, links that act like buttons, filter chips and the automation on/off switch match the rest of the app.

## [1.26.0] "Harrier" — 2026-10-13 · one component set everywhere

> In short: tables, tabs, switches, alerts, avatars, progress bars, the sidebar, the search box and breadcrumbs now all come from the same component library, so they look and behave the same on every page.

### Better

- **A new sidebar.** It collapses to an icon rail with tooltips, and slides in over the page on a phone.
- **Search opens in a cleaner box.** Results are grouped, arrow keys move through them and Enter opens the highlighted one.
- **Filters and view switches look the same everywhere.** Status filters, Kanban/List, Grid/Table and the report ranges are one segmented control.
- **On/off settings are switches.** Payroll on/off, rule active and paid leave.
- **Warnings and errors use one alert style, and people show as coloured initials everywhere.**

## [1.25.1] "Godwit" — 2026-10-13 · matching empty and error screens

> In short: every list now shows the same empty and "couldn't load" screens, with the same stat tiles and page titles.

### Better

- **Empty lists look the same everywhere.** Tickets, errors, products, surveys, rules, team, the audit log, reports and notifications show a centred title with a hint about what to try.
- **A failed load looks the same everywhere too.** It says what couldn't load and offers Try again.

## [1.25.0] "Finch" — 2026-10-13 · dark mode and a tidier layout

> In short: the app has a dark theme, a wider page area, and tables, page titles and empty screens that look the same everywhere.

### New

- **Dark mode.** Pick Light, Dark or System from your account menu; the choice is remembered and System follows your device.

### Better

- **Every table looks the same.** Column headings are small capitals, rows highlight under the pointer and numbers line up.
- **Page titles and empty screens match across the app.** Titles are one size and empty lists say what to do next.
- **A wider page area on big screens, and a gentle fade between pages.**

## [1.24.1] "Eagle" — 2026-10-13 · sturdier forms

> In short: odd or broken input no longer ends in an error page, and leave approvals follow two stricter rules.

### Better

- **Double clicks no longer send things twice.** Toggling an automation rule, deciding or cancelling a correction request, and saving an attendance edit now ignore a second click while the first is still going.
- **Punching from the home page refreshes your attendance page.** It shows your new state straight away.

### Fixed

- **Saving a product with a broken milestone list no longer half-saves it.** Odd input in product, key, milestone, correction, attendance and payroll forms is refused or ignored instead of ending in an error page.
- **A leave request whose start date has passed can now be rejected.** It used to be stuck as waiting forever.

### Security

- **You can't approve your own leave while another approver exists.** The request waits for someone else, the same rule attendance corrections already follow.

## [1.24.0] "Dipper" — 2026-10-13 · payroll, redone

> In short: payroll has a new look, from the cycle preview and runs to payslips, holidays and salary setup, and every page of the app now uses the same new design.

### New

- **A new cycle preview.** Pick any date to see the whole cycle with each person's monthly salary, the days it is divided by, leave, deductions and gross, then generate the payslips when it looks right.
- **A new salary setup page.** Each person has their own row with an on/off switch, the monthly salary, the date the rate starts and the day rate it works out to as you type.
- **Payslips that explain themselves.** Both the admin's copy and your own show how the day rate was worked out and every late arrival with what it cost.

### Better

- **Locking a run and removing a holiday are one click.** Removing a holiday still asks first, because open runs recalculate.
- **Payroll pages share one set of section tabs.** Runs, Salaries, Holidays and My payslips are a click apart.

### Security

- **Payslips stay private.** Anyone else's payslip, or one from another company, still answers "not found" rather than confirming it exists.

## [1.23.0] "Curlew" — 2026-10-13 · leave, redone

> In short: leave has a new look, from your balances and the apply form with a live paid/unpaid preview to the calendar, the approvals queue and the leave types page.

### New

- **A live preview when you apply.** Pick your dates and see how many days are paid and unpaid, and who else is already off, before you send the request.
- **A new approvals screen.** Review a request in one dialog: correct the dates, make it a half day, accept the automatic paid/unpaid split or set your own, and add a note to the person.
- **A new leave calendar.** A month grid on a wide screen and an agenda list on a phone, with holidays named and waiting requests drawn dashed.

### Better

- **My leave shows every balance as a bar.** What you have taken, what is waiting and what is left, for each type and any year.
- **The leave types page edits in a dialog.** Blank still means unlimited, and a mistake is shown under the field you typed it in.

### Fixed

- **Adding a leave type with a name that already exists no longer fails with an error page.** It now tells you the name is taken.

## [1.22.0] "Bunting" — 2026-10-13 · attendance, redone

> In short: attendance has a new look, from the punch clock and your month at a glance to the team view, the timesheet and correction requests, with every number the same as your payslip uses.

### New

- **A new punch panel.** A live clock before you check in with a warning if arriving now would be late, a countdown to the end of your day while you work, and the hours worked after you check out.
- **Your month at a glance.** A calendar that tells a full day from a part day, a missing punch and a day you never checked out of.
- **A new team page.** Who is on the clock now, anyone who forgot to check out with a button to fix it, and a week view with late arrivals marked.
- **A new timesheet.** Month totals for everyone, and one person's day-by-day calendar with a link to correct any day.
- **Correction requests in one place.** Ask for new times, see your open requests, and owners and admins approve or reject them with a note.

### Better

- **Forgotten check-outs are easy to spot and fix.** The warning lists each day and links straight to the request form, and admins get the end of the shift filled in.
- **Late arrivals read the same everywhere.** The punch panel, the notification and the payslip all use one rule.

## [1.21.0] "Avocet" — 2026-10-13 · sign-in, team and settings, redone

> In short: the sign-in page, first-run company setup, the team page and your settings have a new look, and the owner can no longer be demoted by an admin by mistake.

### New

- **A new sign-in page.** Wrong passwords are announced clearly without saying which half was wrong, and after signing in you land where you were heading.
- **A new team page.** Filter by role, search, sort, add people, edit them in a window and remove them after a confirmation.
- **New settings.** Your name, email and Discord ID in one place, with mistakes shown next to the field.
- **A new first-run page.** If you have no workspace yet you can create one and become its owner.

### Fixed

- **The owner can no longer be edited from the team page.** Before, an admin who sent the form by hand could change the owner's role.

### Security

- **Signing in now checks that the request really came from our page.** A form on another site can no longer sign someone in as a different person.

## [1.20.0] "Zebra Finch" — 2026-10-13 · the DSR sheet, redone

> In short: the daily status report has a new look where every row saves as you edit it, and your work from the day is suggested for you to confirm.

### New

- **A new DSR sheet.** Change a task, its project, category, time or status right in the row and it saves when you leave the field.
- **Suggestions from your work.** Tickets you touched or have in progress are listed with a guess at the time, and one click logs them with the time you confirm.
- **Pick any day.** Step back and forward or choose a date, and past days stay readable while only today can be edited.

### Better

- **Owners and admins can open a teammate's sheet.** The team overview shows who has logged how much, and a click opens their day.
- **Times are easy to type.** Write 45m, 1h 30m or 1.5 and the sheet understands.

## [1.19.0] "Yellowhammer" — 2026-10-13 · home, reports and the audit log, redone

> In short: the home page, the reports, the audit log and each product's dashboard have a new look, and the home page now punches you in and out without leaving it.

### New

- **A new home page.** Your tickets, hours, to-dos, pay, leave and DSR in one view, with a clock and greeting that always match your own time.
- **A to-do list that updates as you tick things off.** Add a task with a priority and a due date, tick it, delete it or clear everything that is done.
- **New reports.** Pick a date range or a quick range, see how each number moved against the period before, and fold open the tables by product and by day.
- **A new audit log.** Search it, filter by event, person or date, and click an entry to open what it is about.
- **A new product dashboard.** Errors, tickets, survey score and uptime with 30-day trends.

### Better

- **Punch in and out from the home page.** It does the same as the attendance page, including the receipt in your notifications.
- **Cleaner code behind the home page.** Old buttons that no page used any more were removed.

## [1.18.0] "Xenops" — 2026-10-13 · surveys and automation, redone

> In short: surveys, the customer success hub and automation rules have a new look, and people now only see surveys and rules for the products they can open.

### New

- **A new survey list, survey page and form.** Filter by status or type, see the score distribution, copy the public link and activate, close or delete a survey from one page.
- **A new customer success hub.** Satisfaction by product, the surveys that are live and the latest sentiment in one view.
- **A new public survey page.** Customers pick a score and leave a comment, and the page works for anyone with the link while the survey is active.
- **New automation pages.** Rules are listed with what they trigger on, switched on or off with one click, and created or edited in a clearer form.

### Better

- **Product surveys and rules have the same pages as the global ones.** Open them from a product and they are already scoped to it.

### Security

- **Surveys and rules follow product access.** You only see and change the ones on products you can open, and only owners and admins can make a rule for every product.

## [1.17.0] "Wren" — 2026-10-13 · products, redone

> In short: the products list, the product page and its forms have a new look, with the roadmap, versions, API keys and team access all on one page that saves as you go.

### New

- **A new product list.** Switch between cards and a table, search, sort, and see how healthy each product is at a glance.
- **A new product page.** The milestone roadmap, versions, API keys and team access, each with buttons that save straight away and tell you what happened.
- **A new form for creating and editing a product.** The ticket prefix is suggested from the name as you type.
- **A new page that shows how to send data to a product.** Pick your language and copy a ready-made example.

### Better

- **A new API key is shown once, right where you made it.** You can copy it with one click.
- **Rotating a key asks you first.** You choose whether the old key stops now or keeps working for a day or a week.

## [1.16.0] "Vireo" — 2026-10-13 · errors, redone

> In short: the error list, the error page and the report form have a new look, with one-click resolve and ignore, a trend chart and a ticket button on every error.

### New

- **A new error list.** Search, filter by product, severity and status, sort, and jump to the Regressed tab for errors that came back after being resolved.
- **A new error page.** The last 30 days as a chart, occurrences split by release, linked tickets, and Resolve, Ignore and Create Ticket buttons that save straight away.
- **A new form for reporting an error by hand.** Mistakes are shown next to the field they belong to.

### Better

- **The sidebar counts update as you work.** Resolving or deleting an error changes the open count at once, without reloading.
- **Opening an error from the wrong product is a clean not-found.** Moving around the app now behaves like a fresh page load.

## [1.15.0] "Umbrellabird" — 2026-10-13 · a new ticket page

> In short: the ticket page and the new-ticket and edit forms have a new look, with comments, mentions and every control on one screen that saves as you go.

### New

- **A new ticket page.** Status, priority, assignees, deadline and follow are all on the side, and each change saves straight away and tells you it did.
- **Comments with @mentions that are easier to write.** Type @ and pick a person with the arrow keys and Enter; the people you mention are highlighted and get a notification.
- **A new form for creating and editing tickets.** Mistakes are shown next to the field they belong to, and what you typed is kept.

### Better

- **Assigning several people is one step.** Tick everyone you want and the ticket is updated once, a moment after you stop.
- **You can see who else has the ticket open.** The ticket page tells you when a teammate is looking at it too.
- **Deadlines stay exactly as you typed them.** It no longer matters which time zone your computer is set to.

## [1.14.0] "Tern" — 2026-10-13 · tickets, redone

> In short: the ticket board and the ticket list have a new look and feel quicker, and each product now shows its own menu in the sidebar.

### New

- **A new ticket board.** Drag a ticket to another column and it moves straight away; if it cannot move you see why and the ticket jumps back. On a phone, use the Move button on the ticket instead.
- **A new ticket list.** Search, filter and sort as before, with the filters kept in the web address so you can bookmark a view or come back to it with the Back button.
- **Keyboard shortcuts on tickets.** Press j and k to move through tickets, Enter to open one and e to edit it.
- **A menu for each product.** Inside a product, the sidebar shows its Overview, Errors, Tickets, Feedback and Automation with their counts, and a switcher to jump to another product.

### Better

- **Deleting several tickets is clearer.** Choose Select, tick the tickets and confirm; you are told how many were deleted and how many were skipped because you may not delete them.
- **Counts stay right.** The numbers in the sidebar and on the product menu update as soon as you move or delete a ticket.

## [1.13.0] "Swift" — 2026-10-13 · a new navigation

> In short: the notifications page now opens inside a new, faster navigation bar and sidebar, with search, alerts and who-is-online built in.

### New

- **A new sidebar and top bar.** The notifications page now has the new navigation, and the rest of the app will follow page by page. Pages that have not moved yet still look and work as before.
- **Search from anywhere.** Press Ctrl K (or /) to search tickets, errors, products and pages, with your recent searches kept close.

### Better

- **The bell and the notifications page stay in step.** Marking everything as read, or a new notification arriving, updates both at once without a reload.
- **Messages you get after an action show up on the new pages too.** For example, "Switched to Acme." appears once after you change workspace.
- **Old links keep working.** A link to your unread notifications opens on the Unread filter.

## [1.12.0] "Robin" — 2026-10-12 · a fresher notifications page

> In short: the notifications page has a cleaner, more modern look and updates in place, and it is the first page of a gradual move to a new interface.

### New

- **A fresher look for the notifications page.** Each notification shows its kind, a short summary and how long ago it arrived, with unread ones marked clearly, on a layout that works well on a phone.

### Better

- **Marking everything as read no longer reloads the page.** The list, the unread count and the bell at the top all update straight away, and a message confirms it.
- **Loading and errors are clearer.** You see placeholders while notifications load, and a Try again button if something goes wrong.

## [1.11.0] "Quail" — 2026-10-12 · a toast for every action, and an audit trail behind it

> In short: every action now confirms itself with a pop-up message, more of your changes are written to the activity log, and the punch notifications show Indian time with the late fee or how your day went.

### New

- **More actions are recorded in the activity log.** Creating a workspace, editing your profile, adding, editing or removing a DSR entry (including one picked from a suggestion), adding or changing a milestone, following or unfollowing a ticket, and cancelling an attendance-correction request are all written down with who did it, visible on the activity log page.
- **Every to-do action confirms itself.** Adding a task, marking it done, reopening it, deleting it and clearing the finished ones each pop up a message now, so you never wonder whether the click took.
- **Rotating an API key tells you what happened.** The confirmation names what happened to the old key — revoked immediately or still working until a date — instead of swapping keys in silence.

### Better

- **Punch notifications now say what they mean.** Checking in tells you whether you were late and the late fee, or that you were on time. Checking out tells you how much of your day you worked and reminds you of any earlier days you left unclosed.

### Fixed

- **Check-in and check-out times show Indian time again.** A 10:02 punch used to read "Checked in at 04:32 AM" in the pop-up and the notification, because the stored time was read back as UTC. It now shows the real Indian time wherever the punch is announced.

## [1.10.0] "Plover" — 2026-10-09 · priorities, overdue alerts and to-dos in your DSR

> In short: your to-dos now have a priority, show in red when they are overdue, remind you once a day, and land in today's DSR when you finish them.

### New

- **Pick a priority for each to-do.** Choose Low, Medium or High when you add a task. The most important open tasks sit at the top of the list.
- **Overdue to-dos stand out in red.** A task past its due date gets a red card and an Overdue label, and moves to the top.
- **A daily reminder about overdue to-dos.** You get one notification a day, in the bell and as a push, while any task is overdue.
- **Finished to-dos are added to today's DSR.** Tick a task and it appears on today's sheet. Add the time you spent there. Untick it the same day and the row goes away.

### Better

- **The to-do card has a cleaner look.** Sharper borders, a blue focus ring and tidy badges.

## [1.9.0] "Osprey" — 2026-10-09 · a fuller home page, and the DSR works on a phone

> In short: the home page now opens with the numbers that matter today and shows your recent activity, and adding a DSR entry and opening dropdowns now work on a phone or in the installed app.

### New

- **Four numbers at the top of the home page.** Open tickets, overdue tickets, to-dos left and hours this week, each one a link to where you act on it.
- **Your recent activity on the home page.** A short list of the last things you did, so you can pick up where you left off.

### Better

- **Dropdowns open as a sheet at the bottom of the screen on a phone.** They are bigger and easier to tap, and nothing can cut them off.
- **The add-entry form opens by itself on an empty DSR day.** After you check out, it is right there waiting.

### Fixed

- **You can add a DSR entry on a phone again.** The add form on an empty day was wider than the screen and half hidden.
- **The DSR page no longer stretches wider than a phone screen.** A hidden label was pushing the whole page sideways, which also made dropdowns and the layout behave oddly in the installed app.

## [1.8.0] "Nightjar" — 2026-10-09 · a bigger to-do list and a due-soon card

> In short: your home page to-do list is bigger and smarter, and a new card shows the tickets that are due soon.

### New

- **A "Due soon" card on the home page.** It lists your open tickets that are overdue or due in the next 7 days, soonest first.
- **Due dates on your to-do list.** Pick a date when you add a task, and it shows as Today or Overdue when it matters.

### Better

- **The to-do list is bigger and easier to use.** It now takes half the row, shows how many tasks are done with a progress bar, and has a Clear done button.

## [1.7.2] "Martin" — 2026-10-09 · a tidier ticket page and messages that say what changed

> In short: the ticket details panel is cleaner, and the pop-up messages now tell you exactly what changed.

### Better

- **The ticket details panel is easier to read.** Status, assignees and deadline now sit under their labels at full width, and the repeated status badge, name list and "No deadline" text are gone.
- **Ticket messages say what changed.** They now name the ticket and show the change, like "CHA-006: status Open → In progress" or "CHA-006 assigned to Ritesh Mahale".

## [1.7.1] "Lark" — 2026-10-09 · clearer ticket errors and tighter project privacy

> In short: creating a ticket with assignees no longer fails for people who cannot open the project, forms now tell you what went wrong, and the Customer Success page only shows your own projects.

### Better

- **Ticket forms tell you what went wrong.** When a ticket cannot be saved, a message now lists every field that needs fixing instead of the page quietly reloading.

### Fixed

- **Creating a ticket no longer fails when you assign someone without project access.** The ticket is created, that person is left off, and you get a message saying who was skipped.

### Security

- **The Customer Success page only shows projects you have been added to.** It used to list every project, survey and response in the company to every member.

## [1.7.0] "Kestrel" — 2026-10-09 · a to-do list on your home page

> In short: the home page now has a private to-do card where you can write down what you want to get done and tick it off.

### New

- **A to-do card on the home page.** Type a task, press Add, tick it when it is done or remove it. Only you can see your list.

## [1.6.1] "Jay" — 2026-10-08 · messages show up again

> In short: the confirmation messages that pop up after you check in or out work again, and your open DSR tasks now show on the home page.

### Better

- **Your open DSR tasks are on the home page.** The DSR card now lists work that is in progress or blocked, so you can see what is still open without opening the sheet.

### Fixed

- **Confirmation messages show again after you check in or out.** Messages like "Checked in at 10:02 AM." were being lost and never appeared on screen. They now pop up, and the same fix brings back messages after other saves.

## [1.6.0] "Ibis" — 2026-10-07 · create tickets from your AI tool

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

## [1.5.0] "Heron" — 2026-10-07 · build your DSR from your AI tool, and a table you can read

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

## [1.4.0] "Grebe" — 2026-10-06 · team week, late preview, shortcuts and smarter search

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

## [1.3.0] "Falcon" — 2026-10-06 · a top bar, a bento home, and office hours of 10 to 6:30

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

## [1.2.2] "Egret" — 2026-10-05 · a live countdown on the punch card

> In short: the punch card shows plain time with no circle, and once you check in it counts down to the end of your full day.

### New

- **A countdown after you check in.** The card shows the time left in your day, ticking by the second, and the time you finish. A full day is 8 hours of work plus the unpaid break, counted from the moment you checked in. Once you pass it, the card shows how long you have gone over.

### Better

- **No more circle.** Before you check in the card shows the time in large numbers. After you check out it shows the hours you worked. A thin bar under the countdown shows how far through the day you are.
- **The check-in and check-out buttons are full width.** They sit under the card text.

## [1.2.1] "Dunlin" — 2026-10-05 · products on the DSR

> In short: you can say which product a DSR entry was for, and the form starts empty after each entry.

### New

- **Pick a product on a DSR entry.** The new entry form has a Product box that lists only the products you can open. Leave it on "No product" for meetings and the like. You can change it on a row later.
- **Product shows on every entry.** Entries made from a ticket take the ticket's product on their own, and older ticket entries were filled in. The copied summary names the product too.

### Better

- **The entry form stays open after you add one.** You can log the next entry straight away.

### Fixed

- **The form still held your last entry.** After adding a task, the text of that task was left in the form. It now starts empty. If an entry fails, what you typed stays so you can fix it.
- **Category and status colors on DSR rows never showed.** They now do.

## [1.2.0] "Condor" — 2026-10-04 · tickets named after their product

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

## [1.1.0] "Bittern" — 2026-10-04 · alerts, search, reports and a new look

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

## [1.0.1] "Albatross" — 2026-10-02 · punch panel, forgotten check-outs & leave caps

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
