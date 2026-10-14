"""The design kit page: every component and icon, with the HTML to copy.

Snippets are template source written by us, rendered here so the page shows the
real thing next to the code that makes it.
"""

from django.shortcuts import render
from django.template import Context, Template
from django.views import View

from apps.core.befui_icons import BEFUI_ICONS
from apps.core.icons import ICONS, UI_ICONS
from apps.core.mixins import CompanyMemberRequiredMixin

LOAD = "{% load icon_tags dropdown_tags %}"

COMPONENTS = [
    ("Buttons", "Every button carries an icon before its label.", """<button class="btn">{% icon 'copy' %}Default</button>
<button class="btn btn-primary">{% icon 'plus' %}Primary</button>
<button class="btn btn-danger">{% icon 'trash' %}Danger</button>
<button class="btn btn-sm">Small</button>
<button class="icon-btn" aria-label="Edit">{% icon 'edit' %}</button>"""),
    ("Badges", "Status and kind chips.", """<span class="bdg bdg-green">Healthy</span>
<span class="bdg bdg-orange">Warning</span>
<span class="bdg bdg-red">Critical</span>
<span class="bdg bdg-blue">Owner</span>
<span class="bdg bdg-outline">Draft</span>
<span class="pill open">Open</span> <span class="pill progress">In progress</span> <span class="pill resolved">Resolved</span>"""),
    ("Segmented tabs", "Links or buttons; the current one has is-on.", """<div class="seg" role="group">
  <a href="#" class="is-on">Today</a><a href="#">Yesterday</a><a href="#">Last 7 days</a>
</div>"""),
    ("Inputs", "Text, number, textarea.", """<input class="form-input" placeholder="Search tickets...">
<textarea class="form-input" rows="2" placeholder="Describe the problem"></textarea>"""),
    ("Dropdown", "Choices as a menu, with a hidden input of the same name. Native selects get the same popover.", """{% dropdown "status" "open:Open|closed:Closed"|opts "open" placeholder="Status" label="Status" %}"""),
    ("Cards and ledger rows", "A card, and a row in a list.", """<div class="card" style="padding:16px">A card</div>
<div class="ledger"><article class="lrow"><span class="lmark">{% icon 'package' 'lmark-ic' %}</span>
  <div class="lmain"><div class="lt"><a href="#">A row title</a></div></div></article></div>"""),
    ("Empty state", "When a list has nothing in it.", """<div class="empty-state">{% icon 'inbox' %}<strong>Nothing here yet</strong>Create the first one.</div>"""),
    ("Dialog", "A native dialog: centred, closes on Esc and a backdrop click. Dropdowns inside open on top.", """<button class="btn" onclick="document.getElementById('demo-dlg').showModal()">Open</button>
<dialog class="dlg" id="demo-dlg" style="max-width:420px">
  <div class="dlg-head"><h2>Title</h2><p>One line of help.</p></div>
  <div class="dlg-foot"><button class="btn" onclick="this.closest('dialog').close()">Close</button></div>
</dialog>"""),
    ("Confirm before a destructive action", "Add data-confirm to a form; it asks first.", """<form method="post" onsubmit="return false" data-confirm="Delete this?" data-confirm-text="This cannot be undone." data-confirm-label="Delete">
  <button class="btn btn-danger">{% icon 'trash' %}Delete</button>
</form>"""),
    ("Toast", "Call window.pqToast(text, kind) from any script. Kinds: success, error, warning, info.", """<button class="btn" onclick="pqToast('Saved.', 'success')">Success</button>
<button class="btn" onclick="pqToast('Something failed.', 'error')">Error</button>"""),
    ("Accordion", "Native details/summary: works without JavaScript, animates the arrow.", """<div class="kt-accordion" style="width:100%">
  <details open><summary>What is a product?</summary><div class="kt-body">Something your team ships and tracks errors for.</div></details>
  <details><summary>Who can see it?</summary><div class="kt-body">Owners and admins, plus anyone given access.</div></details>
</div>"""),
    ("Alert", "Inline message: info, ok, warn, bad.", """<div class="kt-alert info" style="width:100%">{% icon 'info' 'ic' %}<div><b>Heads up</b>Your key expires in 3 days.</div></div>
<div class="kt-alert ok" style="width:100%">{% icon 'check' 'ic' %}<div><b>Saved</b>Everything is up to date.</div></div>
<div class="kt-alert warn" style="width:100%">{% icon 'alert' 'ic' %}<div><b>Careful</b>This changes every ticket name.</div></div>
<div class="kt-alert bad" style="width:100%">{% icon 'x-circle' 'ic' %}<div><b>Failed</b>The webhook did not answer.</div></div>"""),
    ("Banner", "One line across the top of a section.", """<div class="kt-banner" style="width:100%">New release is out. <a href="#">See what changed</a></div>"""),
    ("Avatar and avatar group", "Initials in a circle; stack them for a team.", """<span class="kt-avatar sm">A</span> <span class="kt-avatar">AB</span> <span class="kt-avatar lg">C</span>
<span class="kt-avatars"><span class="kt-avatar">A</span><span class="kt-avatar">B</span><span class="kt-avatar">C</span></span>"""),
    ("Status dot", "A coloured dot before a label; live pulses.", """<span class="kt-dot ok"></span>Healthy <span class="kt-dot warn"></span>Slow <span class="kt-dot bad"></span>Down <span class="kt-dot live"></span>Live"""),
    ("Spinner and skeleton", "Loading states.", """<span class="kt-spinner"></span>
<div style="width:240px;display:grid;gap:8px"><span class="kt-skeleton" style="width:60%"></span><span class="kt-skeleton"></span><span class="kt-skeleton" style="width:80%"></span></div>"""),
    ("Progress and ring", "Set the width, or --v on the ring, as a number from 0 to 100.", """<div class="kt-progress" style="width:240px"><i style="width:64%"></i></div>
<div class="kt-ring" style="--v:72"><span>72%</span></div>"""),
    ("Stat card", "A number with a label and a change.", """<div class="kt-stat"><div class="l">Open tickets</div><div class="v">42</div><div class="d">+5 this week</div></div>
<div class="kt-stat"><div class="l">Error rate</div><div class="v">1.2%</div><div class="d down">-0.3% vs last week</div></div>"""),
    ("Timeline", "Events in order, newest first.", """<ul class="kt-timeline" style="width:100%">
  <li>Ticket resolved<small>Today, 4:10 pm</small></li>
  <li>Assigned to Dev One<small>Today, 11:02 am</small></li>
  <li>Ticket created<small>Yesterday</small></li>
</ul>"""),
    ("Description list", "Label and value pairs.", """<dl class="kt-dl"><dt>Owner</dt><dd>Aditya</dd><dt>Environment</dt><dd>Production</dd><dt>Created</dt><dd>14 Oct 2026</dd></dl>"""),
    ("Switch, checkbox and radio", "Real inputs, restyled; they work in forms.", """<label class="kt-switch"><input type="checkbox" checked><i></i>Email alerts</label>
<label class="kt-check"><input type="checkbox" checked>Remember me</label>
<label class="kt-radio"><input type="radio" name="r" checked>Daily</label>
<label class="kt-radio"><input type="radio" name="r">Weekly</label>"""),
    ("Chip and tag input", "Removable tags; type and press Enter to add.", """<div x-data="{ tags: ['bug','urgent'], v: '' }" class="kt-taginput">
  <template x-for="t in tags" :key="t"><span class="kt-chip"><span x-text="t"></span><button type="button" aria-label="Remove" @click="tags = tags.filter(x => x !== t)">{% icon 'x' 'ic' %}</button></span></template>
  <input x-model="v" placeholder="Add a tag" @keydown.enter.prevent="if(v.trim()){ tags.push(v.trim()); v='' }" @keydown.backspace="if(!v) tags.pop()">
</div>"""),
    ("Stepper", "Where you are in a flow.", """<ol class="kt-steps"><li class="done"><b>1</b>Account</li><li class="now"><b>2</b>Product</li><li><b>3</b>Keys</li></ol>"""),
    ("Popover", "A small panel from a button; closes on a second click.", """<details class="kt-pop"><summary class="btn">{% icon 'info' %}Details</summary><div class="kt-pop-body">Anything goes here: text, a form, links.</div></details>"""),
    ("Tooltip", "Add data-tip to anything.", """<button class="btn kt-tip" data-tip="Copies the link">{% icon 'copy' %}Copy</button>"""),
    ("Pagination", "Links; mark the current page with on.", """<nav class="kt-pager"><span class="off">&lsaquo;</span><a class="on" href="#">1</a><a href="#">2</a><a href="#">3</a><span>&hellip;</span><a href="#">9</a><a href="#">&rsaquo;</a></nav>"""),
    ("Bar list", "Ranked values; --w is the width as a number from 0 to 100.", """<div class="kt-bars"><div>Billing<i style="--w:90"></i><span>90</span></div><div>Checkout<i style="--w:62"></i><span>62</span></div><div>Mobile<i style="--w:30"></i><span>30</span></div></div>"""),
    ("Button group", "Buttons joined into one control.", """<div class="kt-btngroup"><button class="btn">Day</button><button class="btn">Week</button><button class="btn btn-primary">Month</button></div>"""),
    ("Number stepper", "Plus and minus around a number.", """<div class="kt-numstep" x-data="{ n: 3 }"><button type="button" @click="n = Math.max(0, n-1)">&minus;</button><input type="number" x-model.number="n"><button type="button" @click="n++">+</button></div>"""),
    ("Search and password fields", "An input with a button inside it.", """<span class="kt-field"><input class="form-input" placeholder="Search..." style="padding-left:12px"><button type="button" aria-label="Search">{% icon 'search' 'ic' %}</button></span>
<span class="kt-field" x-data="{ show: false }"><input class="form-input" :type="show ? 'text' : 'password'" value="secret123"><button type="button" @click="show = !show" aria-label="Show password">{% icon 'eye' 'ic' %}</button></span>"""),
    ("Underline tabs", "Tabs with content that switches.", """<div x-data="{ t: 'a' }" style="width:100%"><div class="kt-tabs"><button :class="{ on: t==='a' }" @click="t='a'">Overview</button><button :class="{ on: t==='b' }" @click="t='b'">Activity</button></div>
<p x-show="t==='a'" style="padding:12px 2px">The overview.</p><p x-show="t==='b'" style="padding:12px 2px;display:none">The activity.</p></div>"""),
    ("Animated icon", "Add icon-draw to a befui icon and the strokes redraw on hover.", """<span class="icon-hover">{% icon 'rocket' 'ic icon-draw' %}</span>"""),
]


def _render(src):
    return Template(LOAD + src).render(Context({}))


class DesignView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        blocks = [{"title": t, "note": n, "code": c, "demo": _render(c)} for t, n, c in COMPONENTS]
        lucide = sorted(set(ICONS) | set(UI_ICONS))
        befui = sorted(BEFUI_ICONS)
        return render(request, "core/design.html", {"blocks": blocks, "lucide": lucide, "befui": befui})
