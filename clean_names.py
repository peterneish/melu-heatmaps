#!/usr/bin/env python3
"""
Collector name cleanup on top of build_matrix.py (keep both files in one folder).

What it does
  1. Fetches the FULL list of collector strings for the data resource.
  2. Splits joint strings on ';' so "Meagher, D.A.; Scarlett, N.H." counts for
     both people. (Joint records are therefore counted once per collector.)
  3. Merges spelling variants: ignores spacing/punctuation/case, applies the
     manual ALIASES table below.
  4. Takes the top TOP_ROWS people, fetches genus counts for every raw string
     they appear in, and sums them per person.
  5. Writes matrix_clean.json and heatmap_clean.html.

Genus lookups are cached in genus_by_string.json, so editing ALIASES or the
column rule and re-running is fast.

Usage:  python clean_names.py
"""
import json
import os
import re
import time
from collections import defaultdict

import requests

from build_matrix import (BASE, DATA_RESOURCE, ROW_FACET, TOP_ROWS,
                          PER_ROW_LIMIT, PER_ROW_TOP, TEMPLATE, facet)

# Manual merges, applied to each name after whitespace tidying.
# Add entries as you spot them in the "possible duplicates" report.
ALIASES = {
    "Scarlett, N.": "Scarlett, N.H.",
    # Truncated forms of a name where only one full form exists
    "Ducker": "Ducker, S.C.",
    "Williamson": "Williamson, H.B.",
    "Semmens": "Semmens, E.J.",
    "Zimmer": "Zimmer, W.J.",
    "Ashton, D.": "Ashton, D.H.",
    "Stone, I.": "Stone, I.G.",
    "Stone": "Stone, I.G.",
    "Croll, R.": "Croll, R.D.",
    "Miller, R.": "Miller, R.E.",
    "Hallam, N.": "Hallam, N.D.",
    "Mueller, F.": "Mueller, F.J.H. von",
    "Marginson, J.": "Marginson, J.C.",
    "Kottek, M.": "Kottek, M.H.",
    "Newnham, M.": "Newnham, M.R.",
    "Fuhrer, B.": "Fuhrer, B.A.",
    # Missing trailing full stop
    "Perrie, L": "Perrie, L.R.",
    "Brownsey, P": "Brownsey, P.J.",
    "French, C.": "French, C.H.",
    "French, C.H": "French, C.H.",
    # Left alone on purpose (could be different people; check specimens):
    # Beaton (bare), Kraft C. vs C.U.C., O'Brien C./C.E., Lewis J./J.A.,
    # Millar A./A.J.K., Williams M.E./M.L., McLennan E.I./J.P., Turner, Brown,
    # Smith, Siotas, Archer.
}
# Placeholder values that are not people (compared case-insensitively).
DROP = {"", "unknown", "anon", "anon.", "et al", "et al.", "not supplied"}
CACHE = "genus_by_string.json"


def all_collectors(extra_fq=None):
    """Every collector string and its record count, paged."""
    out, seen, offset, page = [], set(), 0, 500
    fqs = [f"data_resource_uid:{DATA_RESOURCE}"] + (extra_fq or [])
    while True:
        params = [("q", "*:*"), ("pageSize", 0), ("facets", ROW_FACET),
                  ("flimit", page), ("foffset", offset), ("facet", "true")]
        params += [("fq", f) for f in fqs]
        r = requests.get(BASE, params=params, timeout=60)
        r.raise_for_status()
        res = r.json().get("facetResults", [])
        rows = res[0]["fieldResult"] if res else []
        new = [(x["label"], x["count"]) for x in rows if x["label"] not in seen]
        if not new:
            break
        out += new
        seen.update(l for l, _ in new)
        offset += page
    return out


def tidy(name):
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"\.\s+(?=[A-Z]\.)", ".", name)   # "D. A." -> "D.A."
    return ALIASES.get(name, name)


def key(name):
    """Identity key: letters only, lower case."""
    return re.sub(r"[^a-z]", "", name.lower())


def people(label):
    parts = [tidy(p) for p in label.split(";")]
    return [p for p in parts if p.lower() not in DROP]


def initials(name):
    return re.sub(r"[^A-Za-z]", "", name.split(",", 1)[1]) if "," in name else ""


def main():
    raw = all_collectors()
    rawc = dict(raw)
    print(f"{len(raw)} distinct collector strings")

    count = defaultdict(int)
    forms = defaultdict(lambda: defaultdict(int))
    strings = defaultdict(set)
    for label, c in raw:
        for p in people(label):
            k = key(p)
            count[k] += c
            forms[k][p] += c
            strings[k].add(label)
    display = {k: max(forms[k], key=forms[k].get) for k in count}
    print(f"{len(count)} distinct people after splitting and merging")

    # Possible duplicates: same surname, one set of initials is a prefix of another
    by_surname = defaultdict(list)
    for k in count:
        by_surname[display[k].split(",")[0].lower()].append(k)
    print("\nPossible duplicates (add to ALIASES if they are the same person):")
    found = False
    for ks in by_surname.values():
        for a in ks:
            for b in ks:
                ia, ib = initials(display[a]), initials(display[b])
                if a < b and ia != ib and (ia.startswith(ib) or ib.startswith(ia)) \
                        and max(count[a], count[b]) >= 20:
                    found = True
                    print(f"  {display[a]} ({count[a]})  <->  {display[b]} ({count[b]})")
    if not found:
        print("  none found")

    top = sorted(count, key=count.get, reverse=True)[:TOP_ROWS]
    print("\nTop people:")
    for k in top:
        extra = len(strings[k])
        print(f"  {display[k]}: {count[k]} records, {extra} source string(s)")

    # Genus counts per raw string (cached)
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = sorted({s for k in top for s in strings[k] if s not in cache})
    print(f"\n{len(todo)} genus lookups needed")
    for i, label in enumerate(todo, 1):
        safe = label.replace("\\", "\\\\").replace('"', '\\"')
        _, rows = facet(extra_fq=[f'{ROW_FACET}:"{safe}"'], limit=PER_ROW_LIMIT)
        cache[label] = rows
        if i % 10 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)}")
            json.dump(cache, open(CACHE, "w"))
        time.sleep(0.2)

    cells = defaultdict(int)
    for k in top:
        for label in strings[k]:
            for g, c in cache[label]:
                cells[(k, g)] += c

    # Column rule: union of each person's top PER_ROW_TOP genera
    skip = {"Not supplied", "", "Unknown"}
    chosen = set()
    for k in top:
        mine = sorted(((g, c) for (kk, g), c in cells.items()
                       if kk == k and g not in skip), key=lambda x: -x[1])
        chosen.update(g for g, _ in mine[:PER_ROW_TOP])

    row_index = {k: i for i, k in enumerate(top)}
    col_totals, best = defaultdict(int), {}
    for (k, g), c in cells.items():
        if g not in chosen:
            continue
        col_totals[g] += c
        if g not in best or c > best[g][1]:
            best[g] = (row_index[k], c)
    cols = sorted(chosen, key=lambda g: (best[g][0], -best[g][1]))

    values = [[cells.get((k, g), 0) for g in cols] for k in top]

    matrix = {
        "data_resource": DATA_RESOURCE,
        "row_facet": ROW_FACET,
        "col_facet": "genus",
        "title": "University of Melbourne Herbarium: top collectors by genus",
        "subtitle": (f"{len(top)} collectors, {len(cols)} genus columns ({DATA_RESOURCE}). "
                     "Rows sorted by total records; columns grouped under the collector who has most of each one. "
                     "\u201c% shown\u201d is the share of that collector\u2019s records that fall in the columns displayed. "
                     "Joint collections count once for each collector."),
        "pct_label": "shown",
        "heading": "By genus",
        "rows": [{"name": display[k], "total": count[k], "shown": sum(v),
                  "strings": sorted(strings[k], key=lambda s: -rawc[s])}
                 for k, v in zip(top, values)],
        "cols": [{"name": g, "total": col_totals[g], "fq": f'genus:"{g}"'} for g in cols],
        "values": values,
    }
    json.dump(matrix, open("matrix_clean.json", "w"), indent=1)

    with open("heatmap_clean.html", "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("__DATA__", json.dumps(matrix)))
    print(f"\n{len(cols)} columns. Wrote matrix_clean.json and heatmap_clean.html")


if __name__ == "__main__":
    main()
