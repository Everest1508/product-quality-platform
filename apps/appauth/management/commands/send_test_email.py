from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from apps.appauth import mailflare_backend


class Command(BaseCommand):
    help = "Send a test email through Mailflare with the current settings, and show the real error if it fails."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Address to send the test to (use your own)")

    def handle(self, *args, to, **opts):
        try:
            cfg = mailflare_backend.load_config()
        except mailflare_backend.MailflareError as exc:
            raise CommandError(str(exc))
        if cfg is None:
            self.stdout.write(self.style.WARNING("Mailflare is not configured (no key in the UI or MAILFLARE_API_KEY)."))
        else:
            self.stdout.write(f"Sending via Mailflare ({cfg.source} settings) from {settings.DEFAULT_FROM_EMAIL}")
        try:
            send_mail("CardSnap test email", "If you can read this, the CRM can send email.",
                      settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        except Exception as exc:
            raise CommandError(f"Could not send: {type(exc).__name__}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Sent to {to}. Check the inbox (and spam)."))
