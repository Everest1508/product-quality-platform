"""Money helpers and the expense discussion. Amounts are whole paise."""


def format_paise(paise):
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    s = str(rupees)
    # Indian grouping: last three digits, then pairs.
    head, tail = s[:-3], s[-3:]
    if head:
        pairs = []
        while len(head) > 2:
            pairs.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(([head] if head else []) + pairs + [tail])
    return f"{sign}₹{s}.{p:02d}" if p else f"{sign}₹{s}"


def add_comment(expense, author, body):
    """Save a comment on an expense and tell the other owners and admins.

    Only owners and admins can open the ledger, so they are the only people who
    could ever read the thread. `notify` skips `author` by itself.
    """
    from apps.accounts.models import Membership
    from apps.expenses.models import ExpenseComment
    from apps.notifications import service as notifications
    from apps.notifications.models import Notification

    comment = ExpenseComment.objects.create(
        company=expense.company, expense=expense, author=author, body=body
    )
    who = author.get_full_name() or author.username
    admins = [
        m.user
        for m in Membership.objects.filter(
            company=expense.company, role__in=(Membership.Role.OWNER, Membership.Role.ADMIN)
        ).select_related("user")
    ]
    notifications.notify_many(
        admins,
        company=expense.company,
        kind=Notification.Kind.COMMENT,
        title=f"{who} commented on {expense.category_label} ({format_paise(expense.amount_paise)})",
        body=" ".join(body.split())[:140],
        url=f"/expenses/{expense.pk}/#discussion",
        actor=author,
    )
    return comment
