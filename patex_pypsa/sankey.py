"""PatEx final energy → PyPSA-Eur inputs, as Sankey flows (fuel → sector → PyPSA-Eur input).

The extraction rules build PyPSA-Eur columns, some of which nest (``electricity
residential`` holds ``electricity residential space``), so they cannot be drawn as
flows. ``data/sankey_flows.csv`` instead assigns **every row** of the PatEx demand
variables to exactly one path:

* fuel: the row's ``energy-carrier``, grouped (``FUEL_GROUPS``), or the rule's fixed
  ``carrier``;
* sector: the rule's label, where ``{dim}`` is replaced by the row's value;
* PyPSA-Eur input: a node of ``data/sankey_nodes.csv``, or a grey "not passed" node
  (ambient heat, non-electric cooking, solid waste).

Agriculture rows go to ``agriculture split`` and are spread over the three PyPSA-Eur
agriculture uses with the same JRC-IDEES shares as the export. A row matched by no rule,
or by two, fails: the diagram must account for every TWh once. ``reconcile`` compares
each PyPSA-Eur node with the bundle file it should equal.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .agriculture import USES
from .extraction import Rule, parse_filters, rule_mask
from .io import KEY_COLUMNS

SANKEY_FLOWS_FILE = "sankey_flows.csv"
SANKEY_NODES_FILE = "sankey_nodes.csv"
AGRICULTURE_SPLIT = "agriculture split"
AGRICULTURE_NODES = {
    "electricity": "Agriculture electricity",
    "heat": "Agriculture heat",
    "machinery": "Agriculture machinery",
}

#: PatEx energy-carrier prefix → fuel node (first match wins)
FUEL_GROUPS = [
    ("electricity", "Electricity"),
    ("hydrogen", "Hydrogen"),
    ("gaseous-ff", "Natural gas"),
    ("gaseous-bio", "Biogas"),
    ("gaseous-syn", "Synthetic gas"),
    ("liquid-ff", "Oil products"),
    ("liquid-bio", "Liquid biofuels"),
    ("liquid-syn", "Synthetic liquids"),
    ("solid-ff", "Coal"),
    ("solid-biomass", "Solid biomass"),
    ("solid-waste", "Solid waste"),
    ("heat", "District heat"),
    ("ambiant", "Ambient heat"),
]


def fuel_group(carrier: str) -> str:
    for prefix, label in FUEL_GROUPS:
        if carrier.startswith(prefix):
            return label
    raise ValueError(f"PatEx carrier {carrier!r} has no Sankey fuel group")


def load_flow_rules(path: str | Path) -> list[tuple[Rule, str, str]]:
    """``(rule, fixed carrier, sector template)`` per row; ``rule.category`` = PyPSA node."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return [
        (
            Rule(r.pypsa, "sankey", 1.0, r.patex_variable, parse_filters(r.filters), r.note),
            r.carrier,
            r.sector,
        )
        for r in df.itertuples(index=False)
    ]


def _agriculture_groups(
    table: pd.DataFrame, extraction_rules: list[Rule], variable: str
) -> pd.Series:
    """Agriculture carrier group of each row, from the export's ``agriculture`` rules."""
    group = pd.Series(pd.NA, index=table.index, dtype=object)
    for rule in extraction_rules:
        if rule.target == "agriculture" and rule.variable == variable:
            group[rule_mask(table, rule)] = rule.category
    return group


def sankey_flows(
    tables: dict[str, pd.DataFrame],
    flow_rules: list[tuple[Rule, str, str]],
    extraction_rules: list[Rule],
    agriculture_shares: pd.DataFrame,
    country_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Long table ``country, year, fuel, sector, pypsa, TWh`` (PyPSA country codes)."""
    parts = []
    by_variable: dict[str, list[tuple[Rule, str, str]]] = {}
    for item in flow_rules:
        by_variable.setdefault(item[0].variable, []).append(item)

    for variable, items in by_variable.items():
        table = tables[variable]
        matched = pd.Series(0, index=table.index)
        for rule, carrier, sector in items:
            mask = rule_mask(table, rule)
            matched += mask
            rows = table[mask & (table[variable] != 0)]
            if rows.empty:
                continue
            fuel = (
                pd.Series(fuel_group(carrier), index=rows.index)
                if carrier
                else rows["energy-carrier"].map(fuel_group)
            )
            dims = re.findall(r"\{([^}]+)\}", sector)
            labels = rows.apply(lambda r: sector.format(**{d: r[d] for d in dims}), axis=1) if dims else sector
            flows = pd.DataFrame(
                {
                    "country": rows["Country"],
                    "year": rows["Years"].astype(int),
                    "fuel": fuel,
                    "sector": labels,
                    "pypsa": rule.category,
                    "TWh": rows[variable],
                }
            )
            if rule.category == AGRICULTURE_SPLIT:
                flows = _split_agriculture_flows(
                    flows,
                    _agriculture_groups(table, extraction_rules, variable)[rows.index],
                    agriculture_shares,
                    country_map or {},
                )
            parts.append(flows)
        bad = table[(matched != 1) & (table[variable].abs() > 1e-9)]
        if not bad.empty:
            dims = [c for c in bad.columns if c not in (*KEY_COLUMNS, variable)]
            counts = matched[bad.index].rename("rules matching")
            raise ValueError(
                f"{variable}: rows matched by no or several Sankey rules "
                f"(data/{SANKEY_FLOWS_FILE}):\n"
                f"{pd.concat([bad[dims], counts], axis=1).drop_duplicates().head(20)}"
            )

    out = pd.concat(parts, ignore_index=True)
    if country_map:
        out["country"] = out["country"].replace(country_map)
    return out.groupby(["country", "year", "fuel", "sector", "pypsa"], as_index=False)["TWh"].sum()


def _split_agriculture_flows(
    flows: pd.DataFrame, groups: pd.Series, shares: pd.DataFrame, country_map: dict[str, str]
) -> pd.DataFrame:
    """One agriculture flow per use, with the export's JRC-IDEES shares (EU27 fallback)."""
    if groups.isna().any():
        raise ValueError("agriculture rows without carrier group in extraction_rules.csv")
    table = shares.set_index(["country", "group"])[USES]
    eu = table.loc["EU27"]
    keys = list(zip(flows["country"].replace(country_map), groups))
    s = pd.DataFrame(
        [table.loc[k] if k in table.index else eu.loc[k[1]] for k in keys], index=flows.index
    )
    parts = []
    for use, node in AGRICULTURE_NODES.items():
        parts.append(flows.assign(pypsa=node, TWh=flows["TWh"] * s[use]))
    # electric machinery stays electricity (as in agriculture.split_agriculture)
    out = pd.concat(parts, ignore_index=True)
    is_elec = (out["fuel"] == "Electricity") & (out["pypsa"] == AGRICULTURE_NODES["machinery"])
    out.loc[is_elec, "pypsa"] = AGRICULTURE_NODES["electricity"]
    return out


def reconcile(
    flows: pd.DataFrame, nodes: pd.DataFrame, bundles: dict[str, pd.DataFrame], year: int
) -> pd.DataFrame:
    """``country, pypsa, sankey, bundle`` [TWh/a] for the nodes that have a bundle value."""
    from .extraction import signed_sum

    sel = flows[flows["year"] == year]
    sankey = sel.pivot_table(
        index="country", columns="pypsa", values="TWh", aggfunc="sum", fill_value=0.0
    )
    rows = []
    for node in nodes[nodes["bundle"] != ""].itertuples(index=False):
        bundle = signed_sum(bundles[node.bundle], node.expression)
        for ct in bundle.index:
            value = sankey[node.pypsa].get(ct, 0.0) if node.pypsa in sankey else 0.0
            rows.append((ct, node.pypsa, float(value), float(bundle[ct])))
    return pd.DataFrame(rows, columns=["country", "pypsa", "sankey", "bundle"])
