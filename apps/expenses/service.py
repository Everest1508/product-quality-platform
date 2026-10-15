"""Splitting and settling. All maths is whole paise."""

from collections import defaultdict


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


def shares(amount_paise, user_ids):
    """Split an amount over people. Cents that do not divide go to the first few
    (lowest ids), so the shares always add back to the amount."""
    ids = sorted(user_ids)
    base, extra = divmod(amount_paise, len(ids))
    return {uid: base + (1 if i < extra else 0) for i, uid in enumerate(ids)}


def balances(expenses):
    """user id -> paise. Positive: they are owed. Negative: they owe.

    Expects `split_with` prefetched.
    """
    net = defaultdict(int)
    for e in expenses:
        split = [u.pk for u in e.split_with.all()]
        if not split:
            continue
        net[e.paid_by_id] += e.amount_paise
        for uid, share in shares(e.amount_paise, split).items():
            net[uid] -= share
    return {uid: v for uid, v in net.items() if v}


def settlements(net):
    """Fewest-ish payments that clear everything: [(from_id, to_id, paise)].

    ponytail: greedy biggest-debtor-pays-biggest-creditor; not provably the
    minimum number of transfers, but never more than people - 1.
    """
    owe = sorted(((-v, u) for u, v in net.items() if v < 0), reverse=True)
    owed = sorted(((v, u) for u, v in net.items() if v > 0), reverse=True)
    out = []
    while owe and owed:
        (d, du), (c, cu) = owe[0], owed[0]
        pay = min(d, c)
        out.append((du, cu, pay))
        owe[0], owed[0] = (d - pay, du), (c - pay, cu)
        owe = sorted((x for x in owe if x[0]), reverse=True)
        owed = sorted((x for x in owed if x[0]), reverse=True)
    return out
