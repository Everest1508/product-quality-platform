"""Django email backend that sends through the Mailflare API (CRM -> Mailflare -> Resend). No SMTP.

Settings come from the admin UI (MailflareConfig, key encrypted) or, failing that, from env:
MAILFLARE_API_URL, MAILFLARE_API_KEY, MAILFLARE_MAILBOX_ID, MAILFLARE_FROM_ADDRESS. The API key is never logged.
"""
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.utils import formataddr, parseaddr

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.console import EmailBackend as ConsoleBackend

DEFAULT_URL = "https://mailflare.riteshmahale15.workers.dev/api/v1/send"
TIMEOUT = 15


class MailflareError(Exception):
    pass


@dataclass
class Config:
    url: str
    key: str
    mailbox_id: str
    from_address: str
    source: str  # "ui" | "env"


def encrypt_key(raw):
    return Fernet(settings.SHARED_SERVER_ENCRYPTION_KEY).encrypt(raw.encode()).decode()


def load_config():
    from apps.appauth.models import MailflareConfig

    row = MailflareConfig.objects.first()
    if row:
        try:
            key = Fernet(settings.SHARED_SERVER_ENCRYPTION_KEY).decrypt(row.api_key_encrypted.encode()).decode()
        except InvalidToken:
            raise MailflareError("The saved Mailflare key cannot be decrypted (the encryption key changed). Enter it again.")
        return Config(row.api_url, key, row.mailbox_id, row.from_address, "ui")
    key = os.environ.get("MAILFLARE_API_KEY", "")
    if key:
        return Config(os.environ.get("MAILFLARE_API_URL", DEFAULT_URL), key, os.environ.get("MAILFLARE_MAILBOX_ID", ""),
                      os.environ.get("MAILFLARE_FROM_ADDRESS", ""), "env")
    return None


def _log(msg, status, error=""):
    from apps.appauth.models import MailLog

    try:  # the log must never break (or hide) the send itself
        MailLog.objects.create(to_addrs=", ".join(list(msg.to) + list(msg.cc) + list(msg.bcc))[:500],
                               subject=msg.subject[:255], status=status, error=error[:300])
    except Exception:
        pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # never forward the Authorization header to another host
        return None


_opener = urllib.request.build_opener(_NoRedirect)


class MailflareEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        try:
            cfg = load_config()
            if cfg is None:
                if settings.DEBUG:  # local dev with nothing configured: print instead of failing
                    return ConsoleBackend(fail_silently=self.fail_silently).send_messages(email_messages)
                raise MailflareError("Mailflare is not configured. An admin can add the key under Email settings.")
            sent = 0
            for msg in email_messages:
                try:
                    self._send(cfg, msg)
                except Exception as exc:
                    _log(msg, "failed", str(exc))
                    raise
                _log(msg, "sent")
                sent += 1
            return sent
        except Exception:
            if self.fail_silently:
                return 0
            raise

    def _send(self, cfg, msg):
        from_email = msg.from_email or settings.DEFAULT_FROM_EMAIL
        if cfg.source == "ui" and from_email == settings.DEFAULT_FROM_EMAIL and cfg.from_address:
            # The admin saved the mailbox in the UI: send as that mailbox, keeping the display name, so no
            # DEFAULT_FROM_EMAIL env setting is needed. An explicit different sender is still refused below.
            from_email = formataddr((parseaddr(from_email)[0], cfg.from_address))
        if not cfg.from_address or not cfg.mailbox_id:
            raise MailflareError("Mailflare needs a mailbox ID and the mailbox's sending address.")
        if parseaddr(from_email)[1].lower() != cfg.from_address.lower():
            raise MailflareError(
                f"From address '{parseaddr(from_email)[1]}' is not the allowed Mailflare mailbox '{cfg.from_address}'. "
                f"Set DEFAULT_FROM_EMAIL to it.")
        body = json.dumps({
            "mailboxId": cfg.mailbox_id, "from": from_email, "to": list(msg.to), "cc": list(msg.cc),
            "bcc": list(msg.bcc), "subject": msg.subject, "text": msg.body,
        }).encode()
        req = urllib.request.Request(cfg.url, data=body, method="POST", headers={
            "Authorization": f"Bearer {cfg.key}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": "pq-crm-mailflare/1.0",
        })
        try:
            with _opener.open(req, timeout=TIMEOUT):
                pass
        except urllib.error.HTTPError as e:
            detail = e.read(300).decode("utf-8", "replace")
            raise MailflareError(f"Mailflare answered {e.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise MailflareError(f"Could not reach Mailflare: {getattr(e, 'reason', e)}")
