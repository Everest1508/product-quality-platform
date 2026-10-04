# Tickets and errors

## Reading the counts

| Place | What it counts |
|---|---|
| Sidebar badge | Open tickets, or open errors, across products you can see |
| Page header | The rows that match your filters, then how many of them are open |
| Product card | Open errors and open tickets for that product |

Open means not resolved or closed for tickets, and not resolved or ignored for
errors. If the header and the sidebar disagree, a filter is on. Press **Clear**.

## Filters

Each filter is a dropdown. Only one opens at a time, a click anywhere else
closes it, and Escape closes it too. Choosing a value filters the list without
reloading the page.

## Mentions and watching

Type **@** in a comment to mention a colleague. Only people who can open the
ticket are offered. A ticket also shows who else has it open right now.

## Errors

Each error group shows a 14 day chart. A group is flagged **New in <release>**
where it first appeared, **Regression** if it returned after being resolved, and
**Rising** when the last 3 days had more occurrences than the 3 before. A resolved group that is reported again
reopens and the owners and admins are told once.
