"""Inline icon set, sourced from Aria Icons.

Source: https://icons.leularia.com/ -- the `lucide-icons` collection, retrieved
with `GET /api/v1/icon?id=lucide:<name>`. Lucide is ISC licensed; the vendored
path inside Aria Icons is MIT. The icons are inlined here rather than linked from
a font or CDN because this project has no build step and no `static/` directory.
They are used app-wide: the sidebar nav, the leave policy editor, and the leave
balances on /leave/.

Every value below is developer-authored, hardcoded markup, audited at vendoring
time for `url(`, `javascript:`, `<script`, `on*=` handlers and external
references -- none are present. `render_icon` still refuses any name that is not
a key of `ICONS`, so user input can never reach `mark_safe` even if a caller
forgets to validate first. Icons are `stroke="currentColor"`, so they inherit
text colour and need no per-icon colours.
"""

from django.utils.html import format_html
from django.utils.safestring import mark_safe

ICONS = {
    "arrow-right": (
        '<path d="M5 12h14" /> <path d="m12 5 7 7-7 7" />'
    ),
    "baby": (
        '<path d="M10 16c.5.3 1.2.5 2 .5s1.5-.2 2-.5" /> <path d="M15 12h.01" />'
        '<path d="M19.38 6.813A9 9 0 0 1 20.8 10.2a2 2 0 0 1 0 3.6 9 9 0 0 1-17.6 0 2 2 0 0 1 0-3.6A9 9 0 0 1 12 3c2 0 3.5 1.1 3.5 2.5s-.9 2.5-2 2.5c-.8 0-1.5-.4-1.5-1" />'
        '<path d="M9 12h.01" />'
    ),
    "banknote": (
        '<rect width="20" height="12" x="2" y="6" rx="2" /> <circle cx="12" cy="12" r="2" />'
        '<path d="M6 12h.01M18 12h.01" />'
    ),
    "briefcase": (
        '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />'
        '<rect width="20" height="14" x="2" y="6" rx="2" />'
    ),
    "building-2": (
        '<path d="M10 12h4" /> <path d="M10 8h4" /> <path d="M14 21v-3a2 2 0 0 0-4 0v3" />'
        '<path d="M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2" />'
        '<path d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16" />'
    ),
    "calendar-days": (
        '<path d="M8 2v4" /> <path d="M16 2v4" />'
        '<rect width="18" height="18" x="3" y="4" rx="2" /> <path d="M3 10h18" />'
        '<path d="M8 14h.01" /> <path d="M12 14h.01" /> <path d="M16 14h.01" />'
        '<path d="M8 18h.01" /> <path d="M12 18h.01" /> <path d="M16 18h.01" />'
    ),
    "car": (
        '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" />'
        '<circle cx="7" cy="17" r="2" /> <path d="M9 17h6" /> <circle cx="17" cy="17" r="2" />'
    ),
    "chart-column": (
        '<path d="M3 3v16a2 2 0 0 0 2 2h16" /> <path d="M18 17V9" /> <path d="M13 17V5" />'
        '<path d="M8 17v-3" />'
    ),
    "check": (
        '<path d="M20 6 9 17l-5-5" />'
    ),
    "chevron-down": (
        '<path d="m6 9 6 6 6-6" />'
    ),
    "chevron-left": (
        '<path d="m15 18-6-6 6-6" />'
    ),
    "chevron-right": (
        '<path d="m9 18 6-6-6-6" />'
    ),
    "circle-check": (
        '<circle cx="12" cy="12" r="10" /> <path d="m9 12 2 2 4-4" />'
    ),
    "clipboard-list": (
        '<rect width="8" height="4" x="8" y="2" rx="1" ry="1" />'
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />'
        '<path d="M12 11h4" /> <path d="M12 16h4" /> <path d="M8 11h.01" />'
        '<path d="M8 16h.01" />'
    ),
    "clock": (
        '<path d="M12 6v6l4 2" /> <circle cx="12" cy="12" r="10" />'
    ),
    "coffee": (
        '<path d="M10 2v2" /> <path d="M14 2v2" />'
        '<path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14a4 4 0 1 1 0 8h-1" />'
        '<path d="M6 2v2" />'
    ),
    "coins": (
        '<circle cx="8" cy="8" r="6" /> <path d="M18.09 10.37A6 6 0 1 1 10.34 18" />'
        '<path d="M7 6h1v4" /> <path d="m16.71 13.88.7.71-2.82 2.82" />'
    ),
    "dumbbell": (
        '<path d="M17.596 12.768a2 2 0 1 0 2.829-2.829l-1.768-1.767a2 2 0 0 0 2.828-2.829l-2.828-2.828a2 2 0 0 0-2.829 2.828l-1.767-1.768a2 2 0 1 0-2.829 2.829z" />'
        '<path d="m2.5 21.5 1.4-1.4" /> <path d="m20.1 3.9 1.4-1.4" />'
        '<path d="M5.343 21.485a2 2 0 1 0 2.829-2.828l1.767 1.768a2 2 0 1 0 2.829-2.829l-6.364-6.364a2 2 0 1 0-2.829 2.829l1.768 1.767a2 2 0 0 0-2.828 2.829z" />'
        '<path d="m9.6 14.4 4.8-4.8" />'
    ),
    "eye": (
        '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" />'
        ' <circle cx="12" cy="12" r="3" />'
    ),
    "eye-off": (
        '<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" />'
        ' <path d="M14.084 14.158a3 3 0 0 1-4.242-4.242" />'
        ' <path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" />'
        ' <path d="m2 2 20 20" />'
    ),
    "file-text": (
        '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />'
        '<path d="M14 2v5a1 1 0 0 0 1 1h5" /> <path d="M10 9H8" /> <path d="M16 13H8" />'
        '<path d="M16 17H8" />'
    ),
    "gift": (
        '<rect x="3" y="8" width="18" height="4" rx="1" /> <path d="M12 8v13" />'
        '<path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7" />'
        '<path d="M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5" />'
    ),
    "heart-pulse": (
        '<path d="M2 9.5a5.5 5.5 0 0 1 9.591-3.676.56.56 0 0 0 .818 0A5.49 5.49 0 0 1 22 9.5c0 2.29-1.5 4-3 5.5l-5.492 5.313a2 2 0 0 1-3 .019L5 15c-1.5-1.5-3-3.2-3-5.5" />'
        '<path d="M3.22 13H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27" />'
    ),
    "history": (
        '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /> <path d="M3 3v5h5" />'
        '<path d="M12 7v5l4 2" />'
    ),
    "house": (
        '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" />'
        '<path d="M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />'
    ),
    "landmark": (
        '<path d="M10 18v-7" />'
        '<path d="M11.12 2.198a2 2 0 0 1 1.76.006l7.866 3.847c.476.233.31.949-.22.949H3.474c-.53 0-.695-.716-.22-.949z" />'
        '<path d="M14 18v-7" /> <path d="M18 18v-7" /> <path d="M3 22h18" />'
        '<path d="M6 18v-7" />'
    ),
    "layout-dashboard": (
        '<rect width="7" height="9" x="3" y="3" rx="1" />'
        '<rect width="7" height="5" x="14" y="3" rx="1" />'
        '<rect width="7" height="9" x="14" y="12" rx="1" />'
        '<rect width="7" height="5" x="3" y="16" rx="1" />'
    ),
    "log-out": (
        '<path d="m16 17 5-5-5-5" /> <path d="M21 12H9" />'
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />'
    ),
    "menu": (
        '<path d="M4 5h16" /> <path d="M4 12h16" /> <path d="M4 19h16" />'
    ),
    "music": (
        '<path d="M9 18V5l12-2v13" /> <circle cx="6" cy="18" r="3" />'
        '<circle cx="18" cy="16" r="3" />'
    ),
    "package": (
        '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z" />'
        '<path d="M12 22V12" /> <polyline points="3.29 7 12 12 20.71 7" />'
        '<path d="m7.5 4.27 9 5.15" />'
    ),
    "paw-print": (
        '<circle cx="11" cy="4" r="2" /> <circle cx="18" cy="8" r="2" />'
        '<circle cx="20" cy="16" r="2" />'
        '<path d="M9 10a5 5 0 0 1 5 5v3.5a3.5 3.5 0 0 1-6.84 1.045Q6.52 17.48 4.46 16.84A3.5 3.5 0 0 1 5.5 10Z" />'
    ),
    "percent": (
        '<line x1="19" x2="5" y1="5" y2="19" /> <circle cx="6.5" cy="6.5" r="2.5" />'
        '<circle cx="17.5" cy="17.5" r="2.5" />'
    ),
    "plane": (
        '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" />'
    ),
    "settings": (
        '<path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915" />'
        '<circle cx="12" cy="12" r="3" />'
    ),
    "sliders-horizontal": (
        '<path d="M10 5H3" /> <path d="M12 19H3" /> <path d="M14 3v4" /> <path d="M16 17v4" />'
        '<path d="M21 12h-9" /> <path d="M21 19h-5" /> <path d="M21 5h-7" />'
        '<path d="M8 10v4" /> <path d="M8 12H3" />'
    ),
    "sparkles": (
        '<path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z" />'
        '<path d="M20 2v4" /> <path d="M22 4h-4" /> <circle cx="4" cy="20" r="2" />'
    ),
    "stethoscope": (
        '<path d="M11 2v2" /> <path d="M5 2v2" />'
        '<path d="M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1" />'
        '<path d="M8 15a6 6 0 0 0 12 0v-3" /> <circle cx="20" cy="10" r="2" />'
    ),
    "target": (
        '<circle cx="12" cy="12" r="10" /> <circle cx="12" cy="12" r="6" />'
        '<circle cx="12" cy="12" r="2" />'
    ),
    "ticket": (
        '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" />'
        '<path d="M13 5v2" /> <path d="M13 17v2" /> <path d="M13 11v2" />'
    ),
    "tree-pine": (
        '<path d="m17 14 3 3.3a1 1 0 0 1-.7 1.7H4.7a1 1 0 0 1-.7-1.7L7 14h-.3a1 1 0 0 1-.7-1.7L9 9h-.2A1 1 0 0 1 8 7.3L12 3l4 4.3a1 1 0 0 1-.8 1.7H15l3 3.3a1 1 0 0 1-.7 1.7H17Z" />'
        '<path d="M12 22v-3" />'
    ),
    "triangle-alert": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />'
        '<path d="M12 9v4" /> <path d="M12 17h.01" />'
    ),
    "umbrella": (
        '<path d="M12 13v7a2 2 0 0 0 4 0" /> <path d="M12 2v2" />'
        '<path d="M20.992 13a1 1 0 0 0 .97-1.274 10.284 10.284 0 0 0-19.923 0A1 1 0 0 0 3 13z" />'
    ),
    "user": (
        '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /> <circle cx="12" cy="7" r="4" />'
    ),
    "users": (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />'
        '<path d="M16 3.128a4 4 0 0 1 0 7.744" /> <path d="M22 21v-2a4 4 0 0 0-3-3.87" />'
        '<circle cx="9" cy="7" r="4" />'
    ),
    "wallet": (
        '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" />'
        '<path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" />'
    ),
    "x": (
        '<path d="M18 6 6 18" /> <path d="m6 6 12 12" />'
    ),    "headset": (
        '<path d="M3 11h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5Zm0 0a9 9 0 1 1 18 0m0 0v5a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3Z" />'
        '<path d="M21 16v2a4 4 0 0 1-4 4h-5" />'
    ),
    "life-buoy": (
        '<circle cx="12" cy="12" r="10" /> <path d="m4.93 4.93 4.24 4.24" />'
        '<path d="m14.83 9.17 4.24-4.24" /> <path d="m14.83 14.83 4.24 4.24" />'
        '<path d="m9.17 14.83-4.24 4.24" /> <circle cx="12" cy="12" r="4" />'
    ),
    "messages-square": (
        '<path d="M16 10a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 14.286V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />'
        '<path d="M20 9a2 2 0 0 1 2 2v10.286a.71.71 0 0 1-1.212.502l-2.202-2.202A2 2 0 0 0 17.172 19H10a2 2 0 0 1-2-2v-1" />'
    ),
}

ICON_CHOICES = tuple((name, name.replace("-", " ").title()) for name in ICONS)
ICON_NAMES = frozenset(ICONS)


def render_icon(name, css_class="ic", size=None):
    """Inline one icon, or nothing if `name` is unknown or blank.

    Returns `""` instead of raising, so a policy with no icon (the default)
    renders no glyph rather than a placeholder box.
    """
    if not name or name not in ICONS:
        return ""
    return format_html(
        '<svg class="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
        '{} aria-hidden="true" focusable="false">{}</svg>',
        css_class,
        f' width="{size}" height="{size}"' if size else "",
        mark_safe(ICONS[name]),
    )
