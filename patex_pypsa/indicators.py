"""PatEx output indicators: tidy series per country and year (``data/indicators.csv``).

Each row of ``indicators.csv`` is one chart: a PatEx variable, optional filters, the
dimension(s) its stack is split by, a unit factor. The result feeds the indicator
pages (``pages.py``): one stacked bar per year, and a catalogue of every series.
These are PatEx outputs, i.e. the input side of the soft-link, not PyPSA-Eur results.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .extraction import Rule, parse_filters, rule_mask

INDICATORS_FILE = "indicators.csv"

PAGES = {
    "energy": "Final energy",
    "buildings": "Buildings",
    "transport": "Transport",
    "industry": "Industry",
    "agriculture": "Agriculture",
    "emissions": "Emissions",
    "power": "Power",
    "heat": "District heat",
}

#: PatEx codes shown with a readable name
LABELS = {
    "agr": "Agriculture",
    "bld": "Buildings",
    "elc": "Energy supply",
    "ind": "Industry",
    "lus": "Land use",
    "tra": "Transport",
    "was": "Waste",
    "total": "",
}


def label(values: list[str]) -> str:
    parts = [LABELS.get(v, v) for v in values]
    return " · ".join(p for p in parts if p)


def indicator_series(
    tables: dict[str, pd.DataFrame],
    definitions: pd.DataFrame,
    years: list[int],
    country_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``page, chart, title, unit, note, series, country, year, value`` for every chart."""
    parts = []
    for d in definitions.itertuples(index=False):
        table = tables[d.variable]
        rows = table[rule_mask(table, Rule(d.chart, "", 1.0, d.variable, parse_filters(d.filters)))]
        rows = rows[rows["Years"].isin(years)]
        by = [b.strip() for b in d.by.split(";")]
        series = rows[by].astype(str).apply(lambda r: label(list(r)), axis=1)
        values = rows.assign(series=series).groupby(["series", "Country", "Years"])[d.variable].sum()
        out = (values * float(d.scale)).rename("value").reset_index()
        out = out.rename(columns={"Country": "country", "Years": "year"})
        out = out.assign(page=d.page, chart=d.chart, title=d.title, unit=d.unit, note=d.note)
        parts.append(out)
    out = pd.concat(parts, ignore_index=True)
    out["year"] = out["year"].astype(int)
    if country_map:
        out["country"] = out["country"].replace(country_map)
    columns = ["page", "chart", "title", "unit", "note", "series", "country", "year", "value"]
    return out[columns]


def load_definitions(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)
