"""Limit failed sign-in attempts.

Two counters, both in the Django cache and both reset by a good sign-in:

* per (IP, username): 5 failures locks that pair for 15 minutes, which stops a
  password guess against one account without locking the real owner out of it
  from another network;
* per IP: 30 failures locks the address, which stops one machine trying many
  usernames.

The default cache is per process, which is right for a single daphne process
(the Docker setup). With several workers, point CACHES at Redis so the counts
are shared.
"""

from django.core.cache import cache

WINDOW_SECONDS = 15 * 60
MAX_PER_ACCOUNT = 5
MAX_PER_IP = 30


def client_ip(request):
    # REMOTE_ADDR only. X-Forwarded-For is client-controlled unless a trusted
    # proxy overwrites it, and trusting it would let an attacker rotate the key.
    return request.META.get("REMOTE_ADDR", "")


def _keys(request, username):
    ip = client_ip(request)
    return f"login-fail:acct:{ip}:{(username or '').strip().lower()[:150]}", f"login-fail:ip:{ip}"


def is_blocked(request, username):
    acct_key, ip_key = _keys(request, username)
    return (cache.get(acct_key, 0) >= MAX_PER_ACCOUNT) or (cache.get(ip_key, 0) >= MAX_PER_IP)


def record_failure(request, username):
    for key in _keys(request, username):
        # add() sets the expiry only on the first failure, so the window does
        # not slide forward on every attempt.
        cache.add(key, 0, WINDOW_SECONDS)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, WINDOW_SECONDS)


def record_success(request, username):
    cache.delete(_keys(request, username)[0])


BLOCKED_MESSAGE = "Too many failed attempts. Wait 15 minutes and try again."
