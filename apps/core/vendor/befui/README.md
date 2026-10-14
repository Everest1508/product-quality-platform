# befui (HTML build)

Vendored from https://befui.vercel.app/html/ on 2026-10-14, second drop (MIT licensed, https://github.com/befui).

- `befui.css`: the styles. `befui.js`: a tiny ES module that loads `chunks/entry.js`.
- `chunks/`: `entry.js` plus one file per component and its shared pieces (228 files). A page fetches a component's file only when it uses that tag, so a page that uses three components downloads three small files, not everything.
- Served by `apps/core/befui.py` at `/befui/` (`<script type="module" src="/befui/befui.js">`; see `templates/core/_befui.html`).

To update: download `befui.css`, `befui.js` and `chunks/entry.js` from the same place, then every file `entry.js` and the chunks import
(`"./name.js"`), until none are missing. Do not edit them by hand.
