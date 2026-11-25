"""Public pages the Play Store asks for: a privacy policy and how to delete an account. No login."""
from django.conf import settings
from django.http import HttpResponse

CONTACT = getattr(settings, "CARDSNAP_CONTACT_EMAIL", "support@beforth.in")

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · CardSnap</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;max-width:680px;margin:40px auto;padding:0 20px;color:#0f172a}}
h1{{font-size:28px}}h2{{font-size:19px;margin-top:28px}}a{{color:#2563eb}}li{{margin:4px 0}}small{{color:#5b6b80}}</style>
</head><body><h1>{title}</h1>{body}<p><small>CardSnap · Beforth · Last updated 25 November 2026</small></p></body></html>"""

_PRIVACY = """<p>CardSnap scans business cards and keeps them in a contact book on your phone. This page says what the app handles.</p>
<h2>What stays on your phone</h2><ul>
<li><b>Card photos.</b> Photos of cards are stored only on your device. They are never uploaded.</li>
<li><b>Text recognition.</b> Reading a card happens on the phone, using Google ML Kit.</li></ul>
<h2>What we store on our server</h2><ul>
<li><b>Your account:</b> your name, email address and a hashed password (or your Google or Apple account id if you sign in that way), and the times you signed in.</li>
<li><b>Codes:</b> we email you a 6-digit code to confirm your email or reset your password. Codes are not stored; they expire in minutes.</li></ul>
<h2>Optional cloud backup</h2>
<p>Cloud backup is off until you turn it on in the app, and you are asked to agree first.</p><ul>
<li><b>What is uploaded:</b> the text details of each card you have saved: name, company, job title, phone numbers, email addresses, website, address, notes, LinkedIn and Twitter details, tags, favourite mark and exhibition name. <b>Photos are never uploaded.</b></li>
<li><b>Why:</b> so you can restore your cards on a new phone.</li>
<li><b>Who can see it:</b> only you, and authorised staff at Beforth who run the service. Each time staff open backed-up cards, the visit is recorded in an access log.</li>
<li><b>Withdraw consent:</b> turn backup off in the app at any time. To erase what was uploaded, choose delete cloud data in the app. Your cards disappear from view at once and are permanently erased within 30 days.</li>
<li><b>Single cards:</b> deleting one card in the app removes its backup straight away.</li></ul>
<h2>Optional AI parsing</h2><p>If you turn on AI parsing and enter your own API key, the text read from a card is sent from your phone straight to the AI provider you chose (for example Groq or OpenAI) to be sorted into fields. The key stays on your phone in secure storage. We never see the key or that text. The provider's own privacy policy applies to it.</p>
<h2>Permissions</h2><ul>
<li><b>Camera</b> to photograph cards.</li>
<li><b>Contacts</b> only if you choose to save a card to your phone's address book.</li>
<li><b>Notifications</b> to remind you to follow up.</li></ul>
<h2>What we do not do</h2><p>No ads, no tracking, no selling or sharing of your data.</p>
<h2>Delete your data</h2>
<p>You can delete your account inside the app (Settings, then Delete account) or follow <a href="/cardsnap/delete-account">these steps</a>. Deleting removes your account and hides any backed-up cards at once; the cards are permanently erased within 30 days.</p>
<p><b>What we keep after you delete your account:</b> so we can count sign-ups and deletions, we keep your name, email address, sign-in method, sign-up date, last sign-in date and number of sign-ins. Nothing else. To have that erased too, email <a href="mailto:{contact}">{contact}</a> from the address on the account.</p>
<h2>Contact</h2><p>Questions: <a href="mailto:{contact}">{contact}</a></p>"""

_DELETE = """<p>You can delete your CardSnap account, and any cloud backup, at any time.</p>
<h2>In the app</h2><ol><li>Open <b>Settings</b>.</li><li>Tap <b>Delete account</b> and confirm with your password (or your Google or Apple account).</li></ol>
<p>The account is removed immediately: name, email, password and sign-in history. The email can be used to sign up again.</p>
<h2>Backed-up cards</h2><p>If you used cloud backup, your backed-up cards are hidden at once, including from our staff, and permanently erased within 30 days. To erase only the backup and keep your account, choose delete cloud data in the app.</p>
<h2>What we keep</h2><p>For counting sign-ups and deletions we keep your name, email address, sign-in method, sign-up date, last sign-in date and number of sign-ins. To have this erased too, email <a href="mailto:{contact}">{contact}</a> from the address on the account and we will remove it.</p>
<h2>Without the app</h2><p>Email <a href="mailto:{contact}">{contact}</a> from the address on the account and we will delete it, with any backup.</p>
<h2>On your phone</h2><p>Card photos and contacts live on your phone. Uninstall the app or clear its storage to remove them.</p>"""


def _page(title, body):
    return HttpResponse(_PAGE.format(title=title, body=body.replace("{contact}", CONTACT)))


def privacy(request):
    return _page("Privacy policy", _PRIVACY)


def delete_account_page(request):
    return _page("Delete your CardSnap account", _DELETE)
