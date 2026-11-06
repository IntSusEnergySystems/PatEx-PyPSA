"""CO2 to the atmosphere per country and sector of a solved PyPSA-Eur network (T35).

    python scripts/co2_by_sector.py <solved_{h}.nc> [--csv out.csv]

Run in the pixi env of PyPSA-Eur (needs pypsa). Gas, oil and methanol are pooled in
PyPSA-Eur: a consumer burning them shows the fossil CO2 of all it burns, and the carbon of
the bio fuels entering the pool is credited on the entry link (``biogas to gas``,
``unsustainable bioliquids``, ``biomass to liquid``, ...). Here that credit (pool input of
the entry link × the pool's CO2 intensity) is moved to the pool's consumers in proportion
to their annual use (mass balance), as the inventory counts no CO2 for burnt biomass. The
rest of an entry link's atmosphere flow (e.g. capture) stays on it. Synthetic fuels are not
moved: their carbon comes from captured CO2, credited where it was captured. The total is
unchanged and checked against the atmosphere.

Columns: ``gross`` (CO2 of the links of the sector), ``bio credit`` (its share of the pool
credits; for the entry links, minus the credit they hand over), ``net``. Mt CO2/a.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import pypsa

ATMOSPHERE = "co2 atmosphere"
POOLS = ("gas", "oil", "methanol")

#: link / load carrier → sector (first match of the prefix, in this order)
SECTORS = [
    ("process emissions", "industry"),
    ("gas for industry", "industry"),
    ("oil for industry", "industry"),
    ("coal for industry", "industry"),
    ("solid biomass for industry", "industry"),
    ("industry methanol", "industry"),
    ("naphtha for industry", "industry"),
    ("gas feedstock for industry", "industry"),
    ("HVC to air", "plastics end of life"),
    ("waste CHP", "plastics end of life"),
    ("rural", "buildings"),
    ("urban decentral", "buildings"),
    ("gas for cooking", "buildings"),
    ("oil for cooking", "buildings"),
    ("coal for cooking", "buildings"),
    ("solid biomass for cooking", "buildings"),
    ("land transport", "transport"),
    ("kerosene for aviation", "aviation"),
    ("shipping", "shipping"),
    ("agriculture", "agriculture"),
    ("urban central", "power and district heat"),
    ("CCGT", "power and district heat"),
    ("OCGT", "power and district heat"),
    ("coal", "power and district heat"),
    ("lignite", "power and district heat"),
    ("oil", "power and district heat"),
    ("nuclear", "power and district heat"),
    ("oil refining", "fuel supply"),
    ("SMR", "fuel supply"),
    ("biogas to gas", "fuel supply"),
    ("unsustainable bioliquids", "fuel supply"),
    ("biomass to liquid", "fuel supply"),
    ("electrobiofuels", "fuel supply"),
    ("biomass-to-methanol", "fuel supply"),
    ("DAC", "removals"),
]


def sector_of(carrier: str) -> str:
    for prefix, sector in SECTORS:
        if carrier.startswith(prefix):
            return sector
    return f"other: {carrier}"


def annual(n: pypsa.Network, frame: pd.DataFrame) -> pd.Series:
    """Annual sum [unit·h/a] of a time series frame."""
    w = n.snapshot_weightings.generators
    return frame.mul(w, axis=0).sum() / (w.sum() / 8760)


def country_of(n: pypsa.Network, buses: pd.Series) -> pd.Series:
    location = buses.map(n.buses.location).fillna("")
    return location.where(location != "", buses).str[:2]


def link_country(n: pypsa.Network) -> pd.Series:
    """Country of the output bus, else of the input bus (links into the atmosphere or
    onto an EU-level bus, e.g. process emissions); ``EU`` when both are EU-level."""
    out = country_of(n, n.links.bus1)
    fallback = country_of(n, n.links.bus0)
    eu = out.isin(["EU", "co"])
    return out.where(~eu, fallback.where(~fallback.isin(["EU", "co"]), "EU"))


def link_atmosphere(n: pypsa.Network) -> pd.Series:
    """Link → annual CO2 to the atmosphere [t/a] (sum over its ports on the atmosphere)."""
    out = pd.Series(0.0, index=n.links.index)
    for k in range(1, 10):
        if f"bus{k}" not in n.links or f"p{k}" not in n.links_t:
            continue
        on_atm = n.links.index[n.links[f"bus{k}"] == ATMOSPHERE]
        if len(on_atm):
            out[on_atm] -= annual(n, n.links_t[f"p{k}"].reindex(columns=on_atm, fill_value=0.0))
    return out


def pool_intensity(n: pypsa.Network, pool_buses: pd.Index) -> float:
    """CO2 per MWh burnt from the pool: the combustion links' atmosphere efficiency."""
    values = []
    for k in range(2, 5):
        if f"bus{k}" not in n.links:
            continue
        m = n.links.bus0.isin(pool_buses) & (n.links[f"bus{k}"] == ATMOSPHERE)
        values.append(n.links.loc[m, f"efficiency{k}"])
    values = pd.concat(values)
    values = values[values > 0]
    return float(values.median()) if len(values) else float("nan")


def co2_by_sector(n: pypsa.Network) -> tuple[pd.DataFrame, float]:
    atm = link_atmosphere(n)
    links = n.links.assign(
        co2=atm,
        country=link_country(n),
        sector=n.links.carrier.map(sector_of),
        credit=0.0,
    )
    loads = n.loads.assign(co2=0.0, credit=0.0, country=country_of(n, n.loads.bus))
    loads["sector"] = loads.carrier.map(sector_of)

    bus_carrier = n.buses.carrier
    for pool in POOLS:
        pool_buses = bus_carrier.index[bus_carrier == pool]
        if pool_buses.empty:
            continue
        into = links.bus1.isin(pool_buses) & ~links.bus0.isin(pool_buses)
        # entry links that draw their carbon from the atmosphere (negative CO2 port)
        entries = links.index[into & (links.co2 < 0)]
        if entries.empty:
            continue
        intensity = pool_intensity(n, pool_buses)
        delivered = -annual(n, n.links_t.p1.reindex(columns=entries, fill_value=0.0))
        credit = (delivered * intensity).clip(lower=0.0)
        links.loc[entries, "credit"] += credit  # handed over: the entry keeps the rest

        users = links.index[links.bus0.isin(pool_buses) & ~links.bus1.isin(pool_buses)]
        use = annual(n, n.links_t.p0.reindex(columns=users, fill_value=0.0)).clip(lower=0.0)
        pool_loads = loads.index[loads.bus.isin(pool_buses)]
        load_use = annual(n, n.loads_t.p.reindex(columns=pool_loads, fill_value=0.0)).clip(lower=0.0)
        total = use.sum() + load_use.sum()
        if total <= 0:
            continue
        links.loc[users, "credit"] -= credit.sum() * use / total
        loads.loc[pool_loads, "credit"] -= credit.sum() * load_use / total

    parts = pd.concat(
        [links[["country", "sector", "co2", "credit"]], loads[["country", "sector", "co2", "credit"]]]
    )
    table = parts.groupby(["country", "sector"])[["co2", "credit"]].sum() / 1e6
    table = table.rename(columns={"co2": "gross", "credit": "bio credit"})
    table["net"] = table["gross"] + table["bio credit"]
    table = table[(table.abs() > 1e-6).any(axis=1)]
    return table, atm.sum() / 1e6


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("network", type=Path)
    p.add_argument("--csv", type=Path)
    a = p.parse_args()

    n = pypsa.Network(a.network)
    table, atmosphere = co2_by_sector(n)
    pd.set_option("display.width", 200)
    print(f"{a.network}: CO2 to the atmosphere [Mt/a], bio credits on their consumers")
    print(table.round(3).to_string())
    totals = table.groupby(level="sector").sum()
    print("\nAll countries:\n" + totals.round(3).to_string())
    net = table["net"].sum()
    print(f"\nnet total {net:.3f} Mt/a, atmosphere {atmosphere:.3f} Mt/a, gap {net - atmosphere:.2e}")
    if a.csv:
        table.to_csv(a.csv, float_format="%.6f")
    if abs(net - atmosphere) > 1e-3:
        sys.exit("the net total does not match the CO2 to the atmosphere")


if __name__ == "__main__":
    main()
