#!/usr/bin/env python3
"""
Put the genus and decade heatmaps on one page for GitHub Pages.
Reads matrix_clean.json and matrix_years.json, writes docs/index.html.
Usage:  python combine.py
"""
import json
import os
import re
from datetime import date

from build_matrix import TEMPLATE

REPO = "https://github.com/peterneish/melu-heatmaps"   # linked from the page footer


def load(path, heading):
    m = json.load(open(path, encoding="utf-8"))
    keep = [i for i, r in enumerate(m["rows"]) if not r.get("other")]  # drop any old "everyone else" row
    m["rows"] = [m["rows"][i] for i in keep]
    m["values"] = [m["values"][i] for i in keep]
    m["subtitle"] = re.sub(r" The grey bottom row.*$", "", m.get("subtitle", ""))
    m.setdefault("heading", heading)
    return m


mats = [load("matrix_clean.json", "By genus"), load("matrix_years.json", "By decade")]
mats[0]["generated"] = date.today().isoformat()
mats[0]["repo"] = REPO
os.makedirs("docs", exist_ok=True)
with open(os.path.join("docs", "index.html"), "w", encoding="utf-8") as f:
    f.write(TEMPLATE.replace("__DATA__", json.dumps(mats)))
print("Wrote docs/index.html")
