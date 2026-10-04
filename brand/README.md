# PQ Platform brand assets

The mark is a ring, an inner ring and a Q tail. Source geometry is in `svg/mark-*.svg`.

| Folder | Contents | Use |
|---|---|---|
| `svg/` | `mark-{blue,navy,white}.svg` (transparent), `app-icon-{blue,navy}.svg` | Source files, print, anything that scales |
| `png/transparent/` | `mark-{blue,navy,white}-{16..1024}.png` | Logo on any background. Blue on light, white on dark, navy on light grey |
| `png/app-icon/` | `app-icon-{blue,navy}-{64..1024}.png` | White mark on a rounded tile. App stores, avatars, social |
| `favicon/` | `favicon.ico` (16/32/48), `favicon-{16,32,48}.png`, `favicon.svg`, `apple-touch-icon.png` | Browser tabs and home screen |

Colors: blue `#1A5BFF`, navy `#0D1117`, white `#FFFFFF`. Sizes of 48px and below use a heavier stroke so the rings stay open.
`apple-touch-icon.png` is opaque and square on purpose, since iOS rounds it and fills transparency with black.
The app inlines the favicon in `templates/core/base.html` and the in-app mark in `apps/core/icons.py` (`BRAND_MARK`).
