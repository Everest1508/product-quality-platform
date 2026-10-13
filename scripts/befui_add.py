#!/usr/bin/env python3
"""befui isn't on npm: components are copied from its registry (https://befui.vercel.app/r/<name>.json).
Usage: scripts/befui_add.py table tabs ...   (skips files that already exist; --force overwrites).
Prints the npm packages the components need."""
import json, os, sys, urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..", "frontend", "src")
seen, deps = set(), set()


def add(name, force):
    if name in seen:
        return
    seen.add(name)
    d = json.load(urllib.request.urlopen(f"https://befui.vercel.app/r/{name}.json"))
    for req in d.get("requires", []):
        add(req, force)
    deps.update(d.get("deps", []))
    for f in d["files"]:
        path = os.path.normpath(os.path.join(ROOT, f["path"]))
        if os.path.exists(path) and not force:
            print("exists ", f["path"])
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(f["content"])
        print("wrote  ", f["path"])


args = [a for a in sys.argv[1:] if not a.startswith("--")]
for n in args:
    add(n, "--force" in sys.argv)
print("npm install", " ".join(sorted(deps)) if deps else "(nothing)")
