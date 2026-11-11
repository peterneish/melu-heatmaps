#!/usr/bin/env python3
"""
Build a collector x genus matrix for one ALA data resource and write:
  matrix.json   - the raw matrix (re-usable for other visualisations)
  heatmap.html  - self-contained heatmap page with the data embedded

Usage:  pip install requests && python build_matrix.py
Change FACET to "family", "species", "year" etc. for other matrices.
"""
import json
import time
import requests

BASE = "https://biocache-ws.ala.org.au/ws/occurrences/search"
DATA_RESOURCE = "dr13282"      # University of Melbourne Herbarium (MELU)
ROW_FACET = "collector"
FACET = "genus"
TOP_ROWS = 30                  # number of collectors
PER_ROW_LIMIT = 100            # genera fetched per collector
PER_ROW_TOP = 4                # each collector contributes their top N genera as columns


def facet(extra_fq=None, field=FACET, limit=100):
    """Return [(label, count), ...] for a facet, within the data resource."""
    fqs = [f"data_resource_uid:{DATA_RESOURCE}"] + (extra_fq or [])
    params = [("q", "*:*"), ("pageSize", 0), ("facets", field),
              ("flimit", limit), ("facet", "true")]
    params += [("fq", f) for f in fqs]
    r = requests.get(BASE, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    results = data.get("facetResults", [])
    if not results:
        return data.get("totalRecords", 0), []
    return data.get("totalRecords", 0), [
        (x["label"], x["count"]) for x in results[0]["fieldResult"]
    ]


def main():
    total, _ = facet(limit=1)
    print(f"Total MELU records: {total}")

    _, collectors = facet(field=ROW_FACET, limit=TOP_ROWS + 5)
    collectors = [(n, c) for n, c in collectors if n and n.strip()][:TOP_ROWS]
    print(f"Top collectors: {len(collectors)}")

    cells = {}  # (collector, genus) -> count
    for i, (name, total_n) in enumerate(collectors, 1):
        safe = name.replace("\\", "\\\\").replace('"', '\\"')
        _, rows = facet(extra_fq=[f'{ROW_FACET}:"{safe}"'],
                        limit=PER_ROW_LIMIT)
        for g, c in rows:
            cells[(name, g)] = c
        print(f"  {i:2d}/{len(collectors)} {name}: {total_n} records, "
              f"{len(rows)} {FACET} values")
        time.sleep(0.2)

    # Keep the raw per-collector counts so later iterations (name cleanup,
    # different column rules) don't need to hit the API again.
    with open("raw_cells.json", "w") as f:
        json.dump([[n, g, c] for (n, g), c in cells.items()], f)

    # Column rule: union of each collector's top PER_ROW_TOP genera,
    # ignoring placeholder values.
    skip = {"Not supplied", "", "Unknown"}
    chosen = set()
    for name, _ in collectors:
        mine = sorted(((g, c) for (n, g), c in cells.items()
                       if n == name and g not in skip),
                      key=lambda x: -x[1])
        chosen.update(g for g, _ in mine[:PER_ROW_TOP])

    # Order columns in blocks: each genus goes under the collector who has
    # the most of it, so specialisms form a diagonal band down the page.
    row_index = {n: i for i, (n, _) in enumerate(collectors)}
    col_totals = {}
    best_row = {}
    for (n, g), c in cells.items():
        if g not in chosen:
            continue
        col_totals[g] = col_totals.get(g, 0) + c
        if g not in best_row or c > best_row[g][1]:
            best_row[g] = (row_index[n], c)
    cols = sorted(chosen, key=lambda g: (best_row[g][0], -best_row[g][1]))

    values = [[cells.get((n, g), 0) for g in cols] for n, _ in collectors]
    matrix = {
        "data_resource": DATA_RESOURCE,
        "row_facet": ROW_FACET,
        "col_facet": FACET,
        "rows": [{"name": n, "total": t, "shown": sum(v)}
                 for (n, t), v in zip(collectors, values)],
        "cols": [{"name": g, "total": col_totals[g]} for g in cols],
        "values": values,
    }
    print(f"Columns: {len(cols)} (union of each collector's top {PER_ROW_TOP})")
    with open("matrix.json", "w") as f:
        json.dump(matrix, f, indent=1)

    html = TEMPLATE.replace("__DATA__", json.dumps(matrix))
    with open("heatmap.html", "w") as f:
        f.write(html)
    print("Wrote matrix.json and heatmap.html")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Collector heatmaps</title>
<style>
:root { --bg:#fff; --fg:#1d1d1b; --muted:#6b6b66; --line:#e3e1da; --hue:30,120,90; box-sizing:border-box; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --bg:#161614; --fg:#ecebe6; --muted:#9a9990; --line:#2d2d2a; --hue:90,200,150; }
}
:root[data-theme="dark"] { --bg:#161614; --fg:#ecebe6; --muted:#9a9990; --line:#2d2d2a; --hue:90,200,150; }
body { margin:0; background:var(--bg); color:var(--fg);
       padding:max(24px, env(safe-area-inset-top, 0px)) 24px max(24px, env(safe-area-inset-bottom, 0px));
       font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif; }
h1 { font-size:22px; margin:0 0 20px; }
h2 { font-size:18px; margin:0 0 4px; }
section { margin-bottom:40px; }
p.sub { margin:0 0 16px; color:var(--muted); max-width:900px; }
.wrap { overflow:auto; max-height:78vh; border:1px solid var(--line); border-radius:8px; }
table { border-collapse:separate; border-spacing:0; }
th, td { padding:0; }
a { color:inherit; text-decoration:none; }
a:hover { text-decoration:underline; }
thead th { position:sticky; top:0; background:var(--bg); z-index:2; height:var(--hh, 130px); vertical-align:bottom; }
thead th div { writing-mode:vertical-rl; transform:rotate(180deg); font-weight:400; padding:4px 0; margin:0 auto; }
thead th div.it { font-style:italic; }
tbody th { position:sticky; left:0; background:var(--bg); z-index:1; text-align:right;
           font-weight:400; padding:0 10px; white-space:nowrap; border-right:1px solid var(--line); }
thead th.corner { left:0; z-index:3; }
td { width:26px; min-width:26px; height:24px; border:1px solid var(--bg); }
td a { display:block; height:24px; }
td a:hover { outline:2px solid var(--fg); outline-offset:-2px; }
.tot { color:var(--muted); font-size:12px; margin-left:6px; }
.legend { margin-top:12px; color:var(--muted); font-size:12px; max-width:900px; }
</style>
</head>
<body>
<h1 id="h1"></h1>
<main id="app"></main>
<p class="legend">Colour intensity is proportional to the square root of the record count. Click a collector, a column heading or a cell to run that search on the Atlas of Living Australia, limited to this data resource (opens in a new tab). Hover for counts.</p>
<p class="legend" id="credit"></p>
<script>
const DS = [].concat(__DATA__);
const BASE = "https://biocache.ala.org.au/occurrence/search";
const enc = encodeURIComponent;
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const fmt = n => n.toLocaleString("en-AU");
function rowFq(D, r) {
  if (r.fq) return r.fq;
  const parts = [];
  let len = 0;
  for (const s of (r.strings && r.strings.length ? r.strings : [r.name])) {
    const p = '"' + s.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
    len += enc(p).length + 12;
    if (len > 5000 && parts.length) { r.partial = true; break; }
    parts.push(p);
  }
  r.fq = D.row_facet + ":(" + parts.join(" OR ") + ")";
  return r.fq;
}
const colFq = (D, c) => c.fq || (D.col_facet + ':"' + c.name + '"');
const link = (D, fqs) => BASE + "?q=" + enc("data_resource_uid:" + D.data_resource) + fqs.map(f => "&fq=" + enc(f)).join("");

function table(D) {
  const max = Math.max(...D.values.flat());
  let h = "<thead><tr><th class='corner'></th>";
  D.cols.forEach(c => {
    h += "<th><div" + (D.col_facet === "genus" ? " class='it'" : "") + "><a href='" + esc(link(D, [colFq(D, c)])) +
         "' target='_blank' rel='noopener' title='" + esc("Search all " + c.name + " records") + "'>" + esc(c.name) + "</a></div></th>";
  });
  h += "</tr></thead><tbody>";
  D.rows.forEach((r, i) => {
    const pct = Math.round(100 * r.shown / r.total);
    const tip = "Search all " + r.name + " records" + (r.partial ? " (link covers the most frequent name variants only)" : "");
    h += "<tr><th><a href='" + esc(link(D, [rowFq(D, r)])) + "' target='_blank' rel='noopener' title='" + esc(tip) + "'>" + esc(r.name) +
         "</a><span class='tot'>" + fmt(r.total) + " &middot; " + pct + "% " + esc(D.pct_label) + "</span></th>";
    D.values[i].forEach((v, j) => {
      if (!v) { h += "<td class='z'></td>"; return; }
      const c = D.cols[j];
      const a = (0.08 + 0.92 * Math.sqrt(v / max)).toFixed(3);
      h += "<td style='background:rgba(var(--hue)," + a + ")'><a href='" + esc(link(D, [rowFq(D, r), colFq(D, c)])) +
           "' target='_blank' rel='noopener' title='" + esc(r.name + " / " + c.name + ": " + fmt(v)) + "'></a></td>";
    });
    h += "</tr>";
  });
  return h + "</tbody>";
}

const multi = DS.length > 1;
document.title = multi ? "MELU collectors" : DS[0].title;
document.getElementById("h1").textContent = multi ? "University of Melbourne Herbarium: top collectors" : DS[0].title;
document.getElementById("app").innerHTML = DS.map(D =>
  "<section" + (D.col_facet === "genus" ? "" : " style='--hh:70px'") + ">" +
  (multi ? "<h2>" + esc(D.heading || D.title) + "</h2>" : "") +
  "<p class='sub'>" + esc(D.subtitle) + "</p><div class='wrap'><table>" + table(D) + "</table></div></section>").join("");
const gen = DS.map(D => D.generated).filter(Boolean)[0];
document.getElementById("credit").innerHTML = "Data: University of Melbourne Herbarium (MELU) via the <a href='https://collections.ala.org.au/public/show/" +
  esc(DS[0].data_resource) + "' target='_blank' rel='noopener'>Atlas of Living Australia</a> (" + esc(DS[0].data_resource) + ")." +
  (gen ? " Page generated " + esc(gen) + "." : "");
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
