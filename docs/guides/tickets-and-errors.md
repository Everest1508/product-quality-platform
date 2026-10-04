# Tickets and errors

## Reading the counts

| Place | What it counts |
|---|---|
| Sidebar badge | Open tickets, or open errors, across products you can see |
| Page header | The rows that match your filters, then how many of them are open |
| Product card | Open errors and open tickets for that product |

Open means not resolved or closed for tickets, and not resolved or ignored for
errors. If the header and the sidebar disagree, a filter is on. Press **Clear**.

## Ticket names

A ticket is named after its product: the product key, a dash and a number that
counts up inside that product, for example `AUM-014`. The key is made from the
product name (AU-Marketing gives AUM) and owners and admins can change it under
**Edit product, Ticket prefix**. It is 2 to 6 letters or digits, starts with a
letter and is unique in the company.

* Numbers are never reused, even after a ticket is deleted.
* Changing the key renames every ticket of that product at once. Links to a ticket
  keep working, but a name pasted into chat earlier will no longer match.
* Moving a ticket to another product gives it the next number there.
* A ticket with no product is shown as `#` and its id.
* Search finds a ticket by `AUM-14`, `aum14` or `aum 14`. Typing just `AUM` lists
  that product's newest tickets, and the old `#360` style number still works.

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
