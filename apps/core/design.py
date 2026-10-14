"""The design kit page: every component and icon, with the HTML to copy.

Snippets are template source written by us, rendered here so the page shows the
real thing next to the code that makes it.
"""

from django.shortcuts import render
from django.template import Context, Template
from django.views import View

from apps.core import befui
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
    ("Animated icon", "Add icon-draw to a befui icon and the strokes redraw on hover.", """<span class="icon-hover">{% icon 'rocket' 'ic icon-draw' %}</span>"""),
]


def _render(src):
    return Template(LOAD + src).render(Context({}))


class DesignView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        blocks = [{"title": t, "note": n, "code": c, "demo": _render(c)} for t, n, c in COMPONENTS]
        lucide = sorted(set(ICONS) | set(UI_ICONS))
        groups = befui.demos()
        return render(request, "core/design.html", {
            "blocks": blocks, "lucide": lucide, "befui": sorted(BEFUI_ICONS),
            "groups": groups, "total": sum(len(items) for _, items in groups),
        })
