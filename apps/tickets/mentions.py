"""@mentions in ticket comments.

A mention only counts if it names a real person who can open the ticket. The
text stays as the author typed it; the mentioned users are stored on the comment
so the page can highlight them and so notifications go to the right people.
"""

import re

from django.contrib.auth import get_user_model
from django.db.models.functions import Lower
from django.utils.html import escape
from django.utils.safestring import mark_safe

# `@name` that is not part of an email address or another word. Trailing dots
# are trimmed afterwards so "thanks @ann." mentions ann.
_MENTION = re.compile(r"(?<![\w@.+-])@([\w.+-]{1,150})")


def extract_usernames(body):
    seen, names = set(), []
    for raw in _MENTION.findall(body or ""):
        name = raw.rstrip(".").lower()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def candidates(ticket, company):
    """People who can be mentioned on this ticket: those who can open it."""
    User = get_user_model()
    if ticket.product_id:
        from apps.products.access import product_users

        return product_users(ticket.product, company)
    return User.objects.filter(memberships__company=company).order_by("username").distinct()


def candidates_json(ticket, company):
    """Who the @ autocomplete may offer, as plain data for the page."""
    return [
        {"username": u.username, "name": u.get_full_name() or u.username}
        for u in candidates(ticket, company)
    ]


def resolve(body, ticket, company):
    names = extract_usernames(body)
    if not names:
        return []
    return list(
        candidates(ticket, company)
        .annotate(_lower=Lower("username"))
        .filter(_lower__in=names)
    )


def render_comment(comment):
    """The comment body as safe HTML with each real mention highlighted."""
    html = escape(comment.body)
    people = {u.username.lower(): u for u in comment.mentions.all()}
    if not people:
        return mark_safe(html)
    pattern = re.compile(
        r"(?<![\w@.+-])@(" + "|".join(re.escape(escape(n)) for n in sorted(people, key=len, reverse=True)) + r")(?![\w@+-])",
        re.I,
    )

    def wrap(match):
        user = people.get(match.group(1).lower())
        name = (user.get_full_name() or user.username) if user else ""
        return f'<span class="mention" title="{escape(name)}">@{match.group(1)}</span>'

    return mark_safe(pattern.sub(wrap, html))
