"""Public pages the Play Store asks for: a privacy policy and how to delete an account. No login."""
from django.conf import settings
from django.http import HttpResponse

CONTACT = getattr(settings, "CARDSNAP_CONTACT_EMAIL", "support@beforth.in")

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · CardSnap</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;max-width:680px;margin:40px auto;padding:0 20px;color:#0f172a}}
h1{{font-size:28px}}h2{{font-size:19px;margin-top:28px}}a{{color:#2563eb}}li{{margin:4px 0}}small{{color:#5b6b80}}</style>
</head><body><h1>{title}</h1>{body}<p><small>CardSnap · Beforth · Last updated 24 November 2026</small></p></body></html>"""

_PRIVACY = """<p>CardSnap scans business cards and keeps them in a contact book on your phone. This page says what the app handles.</p>
<h2>What stays on your phone</h2><ul>
<li><b>Scanned cards and contacts.</b> Card photos, the text read from them, notes and reminders are stored only on your device. We do not receive them.</li>
<li><b>Text recognition.</b> Reading a card happens on the phone, using Google ML Kit.</li></ul>
<h2>What we store on our server</h2><ul>
<li><b>Your account:</b> your name, email address and a hashed password (or your Google account id if you sign in with Google), and the times you signed in.</li>
<li><b>Codes:</b> we email you a 6-digit code to confirm your email or reset your password. Codes are not stored; they are computed and expire in minutes.</li></ul>
<h2>Optional AI parsing</h2><p>If you turn on AI parsing and enter your own API key, the text read from a card is sent from your phone straight to the AI provider you chose (for example Groq or OpenAI) to be sorted into fields. The key stays on your phone in secure storage. We never see the key or that text. The provider's own privacy policy applies to it.</p>
<h2>Permissions</h2><ul>
<li><b>Camera</b> to photograph cards.</li>
<li><b>Contacts</b> only if you choose to save a card to your phone's address book.</li>
<li><b>Notifications</b> to remind you to follow up.</li></ul>
<h2>What we do not do</h2><p>No ads, no tracking, no selling or sharing of your data.</p>
<h2>Delete your data</h2><p>You can delete your account inside the app (Settings, then Delete account) or follow <a href="/cardsnap/delete-account">these steps</a>. Deleting removes your account from our server. Contacts on your phone are removed by clearing app data or uninstalling.</p>
<h2>Contact</h2><p>Questions: <a href="mailto:{contact}">{contact}</a></p>"""

_DELETE = """<p>You can delete your CardSnap account and the data we keep about it at any time.</p>
<h2>In the app</h2><ol><li>Open <b>Settings</b>.</li><li>Tap <b>Delete account</b> and confirm with your password (or your Google account).</li></ol>
<p>The account is removed immediately and permanently: name, email, password and sign-in history. The email can be used to sign up again.</p>
<h2>Without the app</h2><p>Email <a href="mailto:{contact}">{contact}</a> from the address on the account and we will delete it.</p>
<h2>On your phone</h2><p>Scanned contacts live only on your phone. Uninstall the app or clear its storage to remove them.</p>"""


def _page(title, body):
    return HttpResponse(_PAGE.format(title=title, body=body.replace("{contact}", CONTACT)))


def privacy(request):
    return _page("Privacy policy", _PRIVACY)


def delete_account_page(request):
    return _page("Delete your CardSnap account", _DELETE)
