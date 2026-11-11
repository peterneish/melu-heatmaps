#!/usr/bin/env python3
"""
Collector x decade matrix, using the same name cleanup as clean_names.py
(keep build_matrix.py, clean_names.py and this file in one folder).

Writes matrix_years.json and heatmap_years.html.
Rows run from earliest to latest average collection year, so the page reads
like a timeline. Year lookups are cached in year_by_string.json.

Usage:  python collector_years.py
"""
import json
import os
import re
import time
from collections import defaultdict

from build_matrix import TEMPLATE, TOP_ROWS, ROW_FACET, DATA_RESOURCE, facet
from clean_names import all_collectors, people, key

BIN = 10                       # years per column
MIN_YEAR, MAX_YEAR = 1750, 2026
CACHE = "year_by_string.json"


def main():
    raw = all_collectors()
    rawc = dict(raw)
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
    top = sorted(count, key=count.get, reverse=True)[:TOP_ROWS]

    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = sorted({s for k in top for s in strings[k] if s not in cache})
    print(f"{len(todo)} year lookups needed")
    for i, label in enumerate(todo, 1):
        safe = label.replace("\\", "\\\\").replace('"', '\\"')
        _, rows = facet(extra_fq=[f'{ROW_FACET}:"{safe}"'],
                        field="year", limit=300)
        cache[label] = rows
        if i % 10 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)}")
            json.dump(cache, open(CACHE, "w"))
        time.sleep(0.2)

    cells = defaultdict(int)
    for k in top:
        for label in strings[k]:
            for y, c in cache[label]:
                try:
                    y = int(y)
                except ValueError:
                    continue
                if MIN_YEAR <= y <= MAX_YEAR:
                    cells[(k, y // BIN * BIN)] += c

    bins = sorted({b for (_, b) in cells})
    bins = list(range(bins[0], bins[-1] + 1, BIN))

    def mean_year(k):
        n = sum(cells.get((k, b), 0) for b in bins)
        return sum((b + BIN / 2) * cells.get((k, b), 0) for b in bins) / n if n else 9999

    order = sorted(top, key=mean_year)
    values = [[cells.get((k, b), 0) for b in bins] for k in order]

    print("\nCollector: first decade, mean year, last decade")
    for k, v in zip(order, values):
        active = [b for b, n in zip(bins, v) if n]
        if active:
            print(f"  {display[k]}: {active[0]}s, {mean_year(k):.0f}, {active[-1]}s")

    matrix = {
        "data_resource": DATA_RESOURCE,
        "row_facet": ROW_FACET,
        "col_facet": "decade",
        "title": "University of Melbourne Herbarium: top collectors by decade",
        "subtitle": (f"{len(order)} collectors by decade of collection ({DATA_RESOURCE}). "
                     "Rows run from earliest to latest average collection year. "
                     "Records without a collection year are left out (see \u201c% dated\u201d). "
                     "Joint collections count once for each collector."),
        "pct_label": "dated",
        "heading": "By decade",
        "rows": [{"name": display[k], "total": count[k], "shown": sum(v),
                  "strings": sorted(strings[k], key=lambda s: -rawc[s])}
                 for k, v in zip(order, values)],
        "cols": [{"name": f"{b}s", "total": sum(v[j] for v in values),
                  "fq": f"year:[{b} TO {b + BIN - 1}]"}
                 for j, b in enumerate(bins)],
        "values": values,
    }
    json.dump(matrix, open("matrix_years.json", "w"), indent=1)

    with open("heatmap_years.html", "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("__DATA__", json.dumps(matrix)))
    print("\nWrote matrix_years.json and heatmap_years.html")


if __name__ == "__main__":
    main()
