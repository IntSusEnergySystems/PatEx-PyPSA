"""HTML report of a coupling bundle: Sankey pages and PatEx indicator pages.

Built after TIMES_PyPSA (``sankey_pages`` / ``indicator_pages``), for PatEx:

* ``sankey_{year}.html``: PatEx final energy, fuel → sector → PyPSA-Eur input, with a
  country selector (EU = sum of the bundle countries). Links are coloured by the
  PyPSA-Eur sector they feed, grey where PatEx energy is not passed on purpose. Below,
  each PyPSA-Eur node is reconciled with the bundle file (horizons only).
* ``indicators_{page}.html``: stacked PatEx trajectories with the table behind them.
* ``indicators_catalogue.html``: every series, filterable, with sparkline and Δ%.

Pages are self-contained apart from the Plotly CDN script. Input: the CSVs written by
``export-coupling`` (``sankey_flows.csv``, ``patex_indicators.csv``), so no PatEx run
is read here.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import __version__
from .indicators import PAGES
from .sankey import SANKEY_NODES_FILE, reconcile

logger = logging.getLogger(__name__)

PLOTLY = "https://cdn.plot.ly/plotly-2.35.2.min.js"
EU = "EU"
TOTAL_COLOR = "#FF0000"

GROUP_COLORS = {
    "electricity": "rgba(31, 119, 180, 0.6)",
    "heat": "rgba(214, 39, 40, 0.55)",
    "transport": "rgba(44, 160, 44, 0.55)",
    "industry": "rgba(140, 86, 75, 0.6)",
    "agriculture": "rgba(188, 189, 34, 0.6)",
    "not passed": "rgba(160, 160, 160, 0.45)",
}
FUEL_COLORS = {
    "Electricity": "#1f77b4",
    "Hydrogen": "#17becf",
    "Natural gas": "#e6550d",
    "Biogas": "#74c476",
    "Synthetic gas": "#9e9ac8",
    "Oil products": "#636363",
    "Liquid biofuels": "#31a354",
    "Synthetic liquids": "#756bb1",
    "Coal": "#3d2b1f",
    "Solid biomass": "#8c6d31",
    "Solid waste": "#bdbdbd",
    "District heat": "#d62728",
    "Ambient heat": "#fdae6b",
}
PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2",
    "#7f7f7f", "#bcbd22", "#17becf", "#393b79", "#637939", "#8c6d31", "#843c39",
    "#7b4173", "#3182bd", "#e6550d", "#31a354", "#756bb1", "#636363",
]

STYLE = """
    body { font-family: system-ui, sans-serif; margin: 24px; max-width: 1500px; color: #222; }
    h2 { margin-top: 36px; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }
    .meta { color: #555; }
    .controls { margin: 12px 0; }
    .controls select { font: inherit; padding: 4px 8px; }
    .block { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }
    .block > .plot { flex: 1 1 620px; min-width: 480px; }
    .block > .grid { flex: 1 1 420px; overflow-x: auto; }
    table.t { border-collapse: collapse; font-size: 13px; }
    table.t th, table.t td { border: 1px solid #ccc; padding: 3px 8px; text-align: right; }
    table.t th:first-child, table.t td:first-child { text-align: left; }
    table.t tr:first-child th { background: #f0f0f0; text-align: center; }
    table.t tr.total-row { background: #f7f7f7; font-weight: 600; }
    td.bad { background: #fde2e1; }
    .caveat { padding: 12px 16px; background: #fff8e8; border-left: 4px solid #d68910; margin: 16px 0; }
    table.nav { border-collapse: collapse; margin: 16px 0; }
    table.nav th, table.nav td { border: 1px solid #ccc; padding: 6px 12px; }
"""

CATALOGUE_STYLE = """
    .filters { display: flex; flex-wrap: wrap; gap: 18px 32px; padding: 14px 16px;
      background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px; margin: 12px 0; }
    .facet { flex: 1 1 260px; min-width: 240px; }
    .facet-head { font-size: 13px; margin-bottom: 6px; }
    .facet-head a { color: #0b57d0; text-decoration: none; font-size: 12px; }
    .chips { display: flex; flex-wrap: wrap; gap: 4px; }
    .chip { font: inherit; font-size: 12px; cursor: pointer; border: 1px solid #bbb;
      background: #fff; color: #666; border-radius: 12px; padding: 2px 10px; }
    .chip.on { background: #16a37f; border-color: #16a37f; color: #fff; }
    .search input { font: inherit; padding: 6px 10px; width: min(420px, 100%);
      border: 1px solid #bbb; border-radius: 4px; }
    .count { color: #555; font-size: 13px; margin-left: 12px; }
    .wrap { overflow-x: auto; }
    table.catalogue { border-collapse: collapse; font-size: 12.5px; width: 100%; }
    table.catalogue th, table.catalogue td { border: 1px solid #ddd; padding: 3px 8px; }
    table.catalogue thead th { background: #f0f0f0; position: sticky; top: 0;
      text-align: left; white-space: nowrap; }
    table.catalogue thead th[data-sort] { cursor: pointer; user-select: none; }
    table.catalogue thead th.asc::after { content: " \\2191"; }
    table.catalogue thead th.desc::after { content: " \\2193"; }
    table.catalogue td.num { text-align: right; white-space: nowrap; }
    table.catalogue td.delta { font-weight: 600; }
    svg.spark { display: block; }
"""

COMMON_JS = r"""
function pxFormat(v) {
  if (v === null || v === undefined || isNaN(v)) return "";
  const a = Math.abs(v);
  const digits = a >= 1000 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3;
  return v.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
function pxCountrySelect(id, countries, onChange) {
  const sel = document.getElementById(id);
  countries.forEach(function (c) {
    const o = document.createElement("option");
    o.value = c; o.textContent = c === "EU" ? "EU (sum of the bundle countries)" : c;
    sel.appendChild(o);
  });
  sel.addEventListener("change", function () { onChange(sel.value); });
  return sel;
}
"""

SANKEY_JS = r"""
function pxSankey(data) {
  const el = document.getElementById("sankey");
  function flowsOf(country) {
    const acc = {};
    data.flows.forEach(function (f) {
      if (country !== "EU" && f[0] !== country) return;
      const k = f[1] + "\u0000" + f[2] + "\u0000" + f[3];
      acc[k] = (acc[k] || 0) + f[4];
    });
    return acc;
  }
  function draw(country) {
    const acc = flowsOf(country);
    const nodes = [], index = {}, colors = [];
    function node(name, color) {
      if (!(name in index)) { index[name] = nodes.length; nodes.push(name); colors.push(color); }
      return index[name];
    }
    const left = {}, mid = {};
    Object.keys(acc).forEach(function (k) {
      const p = k.split("\u0000");
      left[p[0] + "\u0000" + p[1]] = (left[p[0] + "\u0000" + p[1]] || 0) + acc[k];
      mid[p[1] + "\u0000" + p[2]] = (mid[p[1] + "\u0000" + p[2]] || 0) + acc[k];
    });
    const src = [], tgt = [], val = [], col = [], hov = [];
    Object.keys(left).forEach(function (k) {
      if (left[k] < data.threshold) return;
      const p = k.split("\u0000");
      const fc = data.fuelColors[p[0]] || "#999999";
      src.push(node(p[0], fc));
      tgt.push(node(p[1], "#888"));
      val.push(left[k]);
      col.push("rgba(" + parseInt(fc.slice(1, 3), 16) + "," + parseInt(fc.slice(3, 5), 16) + "," +
               parseInt(fc.slice(5, 7), 16) + ",0.3)");
      hov.push(p[0] + " → " + p[1]);
    });
    Object.keys(mid).forEach(function (k) {
      if (mid[k] < data.threshold) return;
      const p = k.split("\u0000");
      const group = data.nodeGroups[p[1]] || "not passed";
      src.push(node(p[0], "#888"));
      tgt.push(node(p[1], data.groupColors[group].replace(/0\.\d+\)$/, "1)")));
      val.push(mid[k]); col.push(data.groupColors[group]);
      hov.push(p[0] + " → " + p[1] + " (" + group + ")");
    });
    Plotly.react(el, [{
      type: "sankey", arrangement: "snap", valueformat: ",.1f", valuesuffix: " TWh",
      node: { label: nodes, color: colors, pad: 12, thickness: 16,
              hovertemplate: "%{label}<br>%{value:,.1f} TWh<extra></extra>" },
      link: { source: src, target: tgt, value: val, color: col, customdata: hov,
              hovertemplate: "%{customdata}<br>%{value:,.1f} TWh<extra></extra>" },
    }], { height: 900, margin: { l: 10, r: 10, t: 10, b: 10 }, font: { size: 12 } },
       { responsive: true, displaylogo: false });
    // totals and reconciliation
    let total = 0, notPassed = 0;
    Object.keys(acc).forEach(function (k) {
      const target = k.split("\u0000")[2];
      total += acc[k];
      if ((data.nodeGroups[target] || "not passed") === "not passed") notPassed += acc[k];
    });
    document.getElementById("totals").textContent =
      "PatEx final energy drawn: " + pxFormat(total) + " TWh, of which not passed to PyPSA-Eur: " +
      pxFormat(notPassed) + " TWh (" + (100 * notPassed / total).toFixed(1) + " %).";
    const rec = document.getElementById("reconcile");
    if (!data.reconcile.length) {
      rec.innerHTML = "<p class='meta'>No bundle for this year: no reconciliation.</p>";
      return;
    }
    const sum = {};
    data.reconcile.forEach(function (r) {
      if (country !== "EU" && r[0] !== country) return;
      if (!sum[r[1]]) sum[r[1]] = [0, 0];
      sum[r[1]][0] += r[2]; sum[r[1]][1] += r[3];
    });
    let rows = "<tr><th>PyPSA-Eur input</th><th>Sankey [TWh]</th><th>bundle [TWh]</th><th>ratio</th></tr>";
    Object.keys(sum).forEach(function (k) {
      const s = sum[k][0], b = sum[k][1];
      const ratio = b !== 0 ? s / b : (s === 0 ? 1 : NaN);
      const bad = isNaN(ratio) || Math.abs(ratio - 1) > 1e-3 ? " class='bad'" : "";
      rows += "<tr><td>" + k + "</td><td>" + pxFormat(s) + "</td><td>" + pxFormat(b) +
              "</td><td" + bad + ">" + (isNaN(ratio) ? "—" : ratio.toFixed(4)) + "</td></tr>";
    });
    rec.innerHTML = "<table class='t'>" + rows + "</table>";
  }
  pxCountrySelect("country", data.countries, draw);
  draw("EU");
}
"""

INDICATOR_JS = r"""
function pxIndicators(data) {
  function draw(country) {
    data.charts.forEach(function (chart) {
      const series = chart.series.map(function (s) {
        return { name: s.name, color: s.color,
                 values: chart.years.map(function (y) { const v = (s.values[country] || {})[y]; return v === undefined ? 0 : v; }) };
      }).filter(function (s) { return s.values.some(function (v) { return Math.abs(v) > 1e-9; }); });
      const total = chart.years.map(function (_, i) {
        return series.reduce(function (a, s) { return a + s.values[i]; }, 0);
      });
      const traces = series.map(function (s) {
        return { type: "bar", name: s.name, x: chart.years, y: s.values, marker: { color: s.color },
                 hovertemplate: s.name + "<br>%{x}: %{y:,.2f} " + chart.unit + "<extra></extra>" };
      });
      traces.push({ type: "scatter", mode: "lines+markers", name: "Total", x: chart.years, y: total,
                    line: { color: PX_TOTAL_COLOR, width: 2 }, marker: { size: 6 },
                    hovertemplate: "Total<br>%{x}: %{y:,.2f} " + chart.unit + "<extra></extra>" });
      Plotly.react(document.getElementById("plot-" + chart.id), traces, {
        barmode: "relative", height: 460, margin: { l: 70, r: 20, t: 10, b: 60 },
        xaxis: { type: "category", title: "Year" }, yaxis: { title: chart.unit, zeroline: true },
        legend: { orientation: "h", x: 0, y: -0.18, yanchor: "top" }, hovermode: "closest",
      }, { responsive: true, displaylogo: false });
      let rows = "<tr><th>" + chart.unit + "</th>" + chart.years.map(function (y) { return "<th>" + y + "</th>"; }).join("") + "</tr>";
      rows += "<tr class='total-row'><td>Total</td>" + total.map(function (v) { return "<td>" + pxFormat(v) + "</td>"; }).join("") + "</tr>";
      series.forEach(function (s) {
        rows += "<tr><td>" + s.name + "</td>" + s.values.map(function (v) { return "<td>" + pxFormat(v) + "</td>"; }).join("") + "</tr>";
      });
      document.getElementById("table-" + chart.id).innerHTML = "<table class='t'>" + rows + "</table>";
    });
  }
  pxCountrySelect("country", data.countries, draw);
  draw("EU");
}
"""

CATALOGUE_JS = r"""
function pxSpark(values, w, h) {
  const pts = values.filter(function (v) { return v !== null; });
  if (pts.length < 2) return "";
  let lo = Math.min.apply(null, pts), hi = Math.max.apply(null, pts);
  if (lo > 0) lo = 0;
  if (hi === lo) hi = lo + 1;
  const n = values.length;
  const x = function (i) { return (i / (n - 1)) * (w - 2) + 1; };
  const y = function (v) { return h - 1 - ((v - lo) / (hi - lo)) * (h - 2); };
  let d = "", started = false;
  values.forEach(function (v, i) {
    if (v === null) return;
    d += (started ? " L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1); started = true;
  });
  return "<svg class='spark' width='" + w + "' height='" + h + "'><path d='" + d +
         "' fill='none' stroke='" + PX_TOTAL_COLOR + "' stroke-width='1.5'/></svg>";
}
function pxDelta(values) {
  const first = values.find(function (v) { return v !== null; });
  let last = null;
  for (let i = values.length - 1; i >= 0; i--) { if (values[i] !== null) { last = values[i]; break; } }
  if (first === undefined || last === null) return { text: "—", value: null };
  if (first === 0) return last === 0 ? { text: "—", value: null } : { text: "∞", value: Infinity };
  const pct = ((last - first) / Math.abs(first)) * 100;
  return { text: (pct >= 0 ? "+" : "") + pct.toFixed(1) + "%", value: pct };
}
function pxCatalogue(payload) {
  const root = document.getElementById("catalogue");
  const years = payload.years, series = payload.series, facets = payload.facets;
  const selected = {};
  facets.forEach(function (f) { selected[f.key] = new Set(f.initial || f.values); });
  let search = "", sortCol = null, sortDir = 1;
  const box = root.querySelector(".filters");
  facets.forEach(function (f) {
    const g = document.createElement("div"); g.className = "facet";
    g.innerHTML = "<div class='facet-head'><strong>" + f.label + "</strong> " +
      "<a href='#' data-all='1'>all</a> · <a href='#' data-none='1'>none</a></div>";
    const list = document.createElement("div"); list.className = "chips";
    f.values.forEach(function (v) {
      const c = document.createElement("button");
      c.type = "button"; c.className = "chip" + (selected[f.key].has(v) ? " on" : ""); c.textContent = v;
      c.addEventListener("click", function () {
        if (selected[f.key].has(v)) { selected[f.key].delete(v); c.classList.remove("on"); }
        else { selected[f.key].add(v); c.classList.add("on"); }
        render();
      });
      list.appendChild(c);
    });
    g.querySelector("[data-all]").addEventListener("click", function (e) {
      e.preventDefault(); f.values.forEach(function (v) { selected[f.key].add(v); });
      list.querySelectorAll(".chip").forEach(function (c) { c.classList.add("on"); }); render();
    });
    g.querySelector("[data-none]").addEventListener("click", function (e) {
      e.preventDefault(); selected[f.key].clear();
      list.querySelectorAll(".chip").forEach(function (c) { c.classList.remove("on"); }); render();
    });
    g.appendChild(list); box.appendChild(g);
  });
  const input = root.querySelector(".search input");
  input.addEventListener("input", function () { search = input.value.trim().toLowerCase(); render(); });
  function matches(s) {
    for (let i = 0; i < facets.length; i++) { if (!selected[facets[i].key].has(s[facets[i].key])) return false; }
    if (!search) return true;
    return ["country", "page", "indicator", "series"].some(function (k) {
      return String(s[k]).toLowerCase().indexOf(search) >= 0;
    });
  }
  function render() {
    const rows = series.filter(matches);
    if (sortCol !== null) {
      rows.sort(function (a, b) {
        let av, bv;
        if (typeof sortCol === "number") { av = a.values[sortCol]; bv = b.values[sortCol]; }
        else if (sortCol === "delta") { av = pxDelta(a.values).value; bv = pxDelta(b.values).value; }
        else { av = a[sortCol]; bv = b[sortCol]; }
        if (av === null || av === undefined) av = -Infinity;
        if (bv === null || bv === undefined) bv = -Infinity;
        if (typeof av === "string") return sortDir * av.localeCompare(bv);
        return sortDir * (av - bv);
      });
    }
    root.querySelector("tbody").innerHTML = rows.slice(0, 3000).map(function (s) {
      const d = pxDelta(s.values);
      return "<tr><td>" + s.country + "</td><td>" + s.page + "</td><td>" + s.indicator + "</td><td>" +
        s.series + "</td><td>" + s.unit + "</td><td>" + pxSpark(s.values, 130, 26) + "</td>" +
        s.values.map(function (v) { return "<td class='num'>" + pxFormat(v) + "</td>"; }).join("") +
        "<td class='num delta'>" + d.text + "</td></tr>";
    }).join("") || "<tr><td colspan='" + (7 + years.length) + "'>No series match the filters.</td></tr>";
    root.querySelector(".count").textContent = rows.length + " / " + series.length + " series" +
      (rows.length > 3000 ? " (first 3000 shown)" : "");
  }
  root.querySelectorAll("thead th[data-sort]").forEach(function (th) {
    th.addEventListener("click", function () {
      const k = th.dataset.sort, col = /^\d+$/.test(k) ? parseInt(k, 10) : k;
      if (sortCol === col) sortDir = -sortDir; else { sortCol = col; sortDir = 1; }
      root.querySelectorAll("thead th[data-sort]").forEach(function (o) { o.classList.remove("asc", "desc"); });
      th.classList.add(sortDir > 0 ? "asc" : "desc"); render();
    });
  });
  render();
}
"""


def _with_eu(frame: pd.DataFrame, keys: list[str], value: str) -> pd.DataFrame:
    eu = frame.groupby([k for k in keys if k != "country"], as_index=False)[value].sum()
    return pd.concat([frame, eu.assign(country=EU)], ignore_index=True)


def _nav(current: str, years: list[int], pages: list[str]) -> str:
    sankeys = " · ".join(
        f"<strong>{y}</strong>" if current == f"sankey_{y}" else f"<a href='sankey_{y}.html'>{y}</a>"
        for y in years
    )
    ind = " · ".join(
        f"<strong>{PAGES[p]}</strong>" if current == p else f"<a href='indicators_{p}.html'>{PAGES[p]}</a>"
        for p in pages
    )
    cat = "<strong>Catalogue</strong>" if current == "catalogue" else "<a href='indicators_catalogue.html'>Catalogue</a>"
    return (
        "<p class='meta'><a href='index.html'>Report index</a> &nbsp;|&nbsp; Sankey: "
        f"{sankeys} &nbsp;|&nbsp; Indicators: {cat} · {ind}</p>"
    )


def _footer(manifest: dict) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        "<hr><p class='meta'>"
        f"PatEx run <code>{html.escape(str(manifest.get('patex_run', '')))}</code> "
        f"(sha256 {html.escape(str(manifest.get('patex_run_sha256', ''))[:12])}) · "
        f"scenario <code>{html.escape(str(manifest.get('scenario_id', '')))}</code> · "
        f"patex_pypsa {__version__} · generated {stamp}<br>"
        "These pages show the PatEx side of the soft-link, not PyPSA-Eur results. "
        "Mapping and reasons: MODEL_CHANGES.md in the PATEX_PyPSA repository.</p>"
    )


def _page(title: str, nav: str, body: str, footer: str, script: str, extra_style: str = "", plotly: bool = True) -> str:
    head_script = f'<script src="{PLOTLY}"></script>' if plotly else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
{head_script}
<style>{STYLE}{extra_style}</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
{nav}
{body}
{footer}
<script>
const PX_TOTAL_COLOR = {json.dumps(TOTAL_COLOR)};
{COMMON_JS}
{script}
</script>
</body>
</html>
"""


def sankey_page(
    flows: pd.DataFrame,
    nodes: pd.DataFrame,
    bundles: dict[str, pd.DataFrame] | None,
    year: int,
    nav: str,
    footer: str,
    threshold: float = 0.01,
) -> str:
    sel = flows[flows["year"] == year]
    rec = reconcile(flows, nodes, bundles, year) if bundles else pd.DataFrame()
    countries = [EU] + sorted(sel["country"].unique())
    data = {
        "flows": sel[["country", "fuel", "sector", "pypsa", "TWh"]].round(6).values.tolist(),
        "reconcile": rec.round(6).values.tolist() if not rec.empty else [],
        "countries": countries,
        "nodeGroups": dict(zip(nodes["pypsa"], nodes["group"])),
        "groupColors": GROUP_COLORS,
        "fuelColors": FUEL_COLORS,
        "threshold": threshold,
    }
    legend = " ".join(
        f"<span style='background:{c};padding:1px 8px;margin-right:6px'>{html.escape(g)}</span>"
        for g, c in GROUP_COLORS.items()
    )
    body = f"""
<p class="meta">PatEx final energy of {year} (and ambient heat), from fuel (left) through the
PatEx sector or end use (middle) to the PyPSA-Eur input it becomes (right). Link colour =
PyPSA-Eur sector of the input: {legend}. Grey right-hand nodes are PatEx energy that is not
passed on purpose (ambient heat: PyPSA-Eur uses heat-pump COPs; industrial solid waste:
only its CO2 is passed). Every row of the PatEx demand
variables is drawn exactly once (<code>data/sankey_flows.csv</code>). Flows below {threshold} TWh
are hidden.</p>
<div class="controls">Country: <select id="country"></select></div>
<p id="totals" class="meta"></p>
<div id="sankey"></div>
<h2>Reconciliation with the bundle</h2>
<p class="meta">Inflow of each PyPSA-Eur node in the diagram against the bundle column(s) it
should equal (<code>data/sankey_nodes.csv</code>). A ratio other than 1 is a mapping hole.</p>
<div id="reconcile"></div>
"""
    script = f"const PX_DATA = {json.dumps(data, ensure_ascii=False)};\n{SANKEY_JS}\npxSankey(PX_DATA);"
    return _page(f"PatEx → PyPSA-Eur flows {year}", nav, body, footer, script)


def _series_colors(names: list[str]) -> dict[str, str]:
    out, used = {}, set()
    for name in names:
        color = FUEL_COLORS.get(name)
        if color is None or color in used:
            color = next((c for c in PALETTE if c not in used), PALETTE[len(out) % len(PALETTE)])
        used.add(color)
        out[name] = color
    return out


def indicator_page(series: pd.DataFrame, page: str, nav: str, footer: str) -> str:
    sel = series[series["page"] == page]
    years = sorted(sel["year"].unique().tolist())
    charts, sections = [], []
    for chart, g in sel.groupby("chart", sort=False):
        names = g.groupby("series")["value"].apply(lambda v: v.abs().sum()).sort_values(ascending=False).index.tolist()
        colors = _series_colors(names)
        values = {
            name: {
                ct: dict(zip(h["year"].astype(str), h["value"].round(6)))
                for ct, h in s.groupby("country")
            }
            for name, s in g.groupby("series")
        }
        charts.append(
            {
                "id": chart,
                "unit": g["unit"].iloc[0],
                "years": [str(y) for y in years],
                "series": [{"name": n, "color": colors[n], "values": values[n]} for n in names],
            }
        )
        note = html.escape(g["note"].iloc[0])
        sections.append(
            f"<h2>{html.escape(g['title'].iloc[0])}</h2>"
            f"<p class='meta'>{note}</p>"
            f"<div class='block'><div class='plot'><div id='plot-{chart}'></div></div>"
            f"<div class='grid' id='table-{chart}'></div></div>"
        )
    countries = [EU] + sorted(c for c in sel["country"].unique() if c != EU)
    body = (
        "<p class='meta'>PatEx outputs (the input side of the soft-link). "
        "Country: <select id='country'></select></p>" + "\n".join(sections)
    )
    data = {"charts": charts, "countries": countries}
    script = f"const PX_DATA = {json.dumps(data, ensure_ascii=False)};\n{INDICATOR_JS}\npxIndicators(PX_DATA);"
    return _page(f"PatEx indicators: {PAGES[page]}", nav, body, footer, script)


def catalogue_page(series: pd.DataFrame, nav: str, footer: str) -> str:
    years = sorted(series["year"].unique().tolist())
    wide = series.pivot_table(
        index=["country", "page", "title", "series", "unit"], columns="year", values="value", aggfunc="sum"
    ).reindex(columns=years)
    rows = [
        {
            "country": ct,
            "page": PAGES[page],
            "indicator": title,
            "series": name,
            "unit": unit,
            "values": [None if pd.isna(v) else round(float(v), 6) for v in vals],
        }
        for (ct, page, title, name, unit), vals in zip(wide.index, wide.values)
    ]
    countries = [EU] + sorted(c for c in series["country"].unique() if c != EU)
    facets = [
        {"key": "country", "label": "Country", "values": countries, "initial": [EU]},
        {"key": "page", "label": "Category", "values": [PAGES[p] for p in PAGES if PAGES[p] in {r["page"] for r in rows}]},
        {"key": "indicator", "label": "Indicator", "values": sorted({r["indicator"] for r in rows})},
    ]
    head = "".join(f"<th data-sort='{i}'>{y}</th>" for i, y in enumerate(years))
    body = f"""
<p class="meta">Every PatEx series of the indicator pages, per country (EU = sum of the bundle
countries). Filter with the chips or a keyword; click a column to sort.</p>
<div id="catalogue">
  <div class="filters"></div>
  <div class="search"><input type="search" placeholder="Filter by keyword"><span class="count"></span></div>
  <div class="wrap"><table class="catalogue"><thead><tr>
    <th data-sort="country">Country</th><th data-sort="page">Category</th>
    <th data-sort="indicator">Indicator</th><th data-sort="series">Series</th>
    <th data-sort="unit">Unit</th><th>{years[0]}&rarr;{years[-1]}</th>{head}
    <th data-sort="delta">&Delta;%</th>
  </tr></thead><tbody></tbody></table></div>
</div>
"""
    payload = {"years": years, "series": rows, "facets": facets}
    script = f"const PX_DATA = {json.dumps(payload, ensure_ascii=False)};\n{CATALOGUE_JS}\npxCatalogue(PX_DATA);"
    return _page("PatEx indicators: catalogue", nav, body, footer, script, CATALOGUE_STYLE, plotly=False)


def write_report(
    coupling_dir: str | Path,
    out_dir: str | Path | None = None,
    mappings_dir: str | Path | None = None,
    sankey_years: list[int] | None = None,
) -> Path:
    """Write the HTML report of ``<coupling_dir>`` into ``out_dir`` (default ``<coupling_dir>/report``)."""
    coupling_dir = Path(coupling_dir)
    inputs = coupling_dir / "pypsa_inputs"
    out = Path(out_dir) if out_dir else coupling_dir / "report"
    out.mkdir(parents=True, exist_ok=True)
    mappings = Path(mappings_dir) if mappings_dir else coupling_dir / "mappings"
    manifest = json.loads((inputs / "manifest.json").read_text())
    flows = pd.read_csv(inputs / "sankey_flows.csv")
    series = _with_eu(
        pd.read_csv(inputs / "patex_indicators.csv", keep_default_na=False),
        ["page", "chart", "title", "unit", "note", "series", "country", "year"],
        "value",
    )
    nodes = pd.read_csv(mappings / SANKEY_NODES_FILE, dtype=str, keep_default_na=False)
    horizons = manifest["horizons"]
    years = sankey_years or sorted({min(flows["year"].unique(), key=lambda y: abs(y - 2021)), *horizons})
    pages = [p for p in PAGES if p in set(series["page"])]
    footer = _footer(manifest)

    for year in years:
        bundles = None
        if year in horizons:
            bundles = {
                "energy_totals": pd.read_csv(inputs / f"patex_energy_totals_{year}.csv", index_col=0),
                "industry": pd.read_csv(inputs / f"patex_industry_{year}.csv", index_col=0),
            }
        page = sankey_page(flows, nodes, bundles, year, _nav(f"sankey_{year}", years, pages), footer)
        (out / f"sankey_{year}.html").write_text(page, encoding="utf-8")
    for p in pages:
        page = indicator_page(series, p, _nav(p, years, pages), footer)
        (out / f"indicators_{p}.html").write_text(page, encoding="utf-8")
    (out / "indicators_catalogue.html").write_text(
        catalogue_page(series, _nav("catalogue", years, pages), footer), encoding="utf-8"
    )

    rows = "".join(
        f"<tr><td><a href='sankey_{y}.html'>Sankey {y}</a></td>"
        f"<td>{'reconciled with the bundle' if y in horizons else 'base year, no bundle'}</td></tr>"
        for y in years
    )
    rows += "<tr><td><a href='indicators_catalogue.html'>Indicator catalogue</a></td><td>every series, filterable</td></tr>"
    rows += "".join(
        f"<tr><td><a href='indicators_{p}.html'>{PAGES[p]}</a></td><td>stacked trajectories</td></tr>" for p in pages
    )
    body = (
        f"<p class='meta'>Scenario <code>{html.escape(str(manifest.get('scenario_id')))}</code>, "
        f"{len(manifest['countries'])} countries, horizons {', '.join(map(str, horizons))}.</p>"
        f"<table class='nav'><tr><th>Page</th><th>Content</th></tr>{rows}</table>"
    )
    (out / "index.html").write_text(
        _page("PatEx → PyPSA-Eur soft-link report", "", body, footer, "", plotly=False), encoding="utf-8"
    )
    logger.info("wrote report %s (%d Sankey pages, %d indicator pages)", out, len(years), len(pages) + 1)
    return out
