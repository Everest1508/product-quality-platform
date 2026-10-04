from django import template

from apps.tickets.mentions import render_comment

register = template.Library()


@register.filter
def comment_html(comment):
    """A comment's body, escaped, with real @mentions highlighted."""
    return render_comment(comment)
