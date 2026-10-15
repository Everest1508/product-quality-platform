"""Money helpers. Amounts are whole paise."""


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
