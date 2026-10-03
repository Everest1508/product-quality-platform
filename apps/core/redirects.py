"""One definition of "is this a safe place to send the user back to?".

A `?next=` value is an attacker-supplied string that becomes a redirect target,
so it is validated rather than trusted. This lives in `core` because three
places need it (login, attendance, and anything else that resumes an
interrupted flow) and three copies of a security rule is three chances to
forget one of the rejected shapes.
"""

from django.utils.http import url_has_allowed_host_and_scheme


def safe_next(raw, allowed_hosts=None, require_https=False):
    """A same-site path from `raw`, or None when it cannot be trusted.

    The rule is a single leading slash, and specifically *not* ``//`` or
    ``/\\`` -- browsers read both as an absolute URL pointing at another host,
    which turns a convenience parameter into an open redirect that phishs
    somebody who trusts your own domain. Anything else is dropped so the caller
    falls back to its own default rather than honouring the attempt.

    Relative paths are kept as well as absolute ones, so `?next=team/` works
    for a same-page switch. The value is returned verbatim: callers are
    expected to hand it straight to `redirect()`.
    """
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    if not url_has_allowed_host_and_scheme(
        value, allowed_hosts=allowed_hosts, require_https=require_https
    ):
        return None
    # Belt and braces: url_has_allowed_host_and_scheme already rejects these,
    # but the reason this helper exists is that the check is not obvious to
    # every reader, and a future edit to the call above should not silently
    # reopen the "//evil.example" shape.
    if value.startswith("//") or value.startswith("/\\"):
        return None
    return value