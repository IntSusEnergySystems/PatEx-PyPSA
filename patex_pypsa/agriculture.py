"""Split PatEx agriculture energy by carrier into PyPSA-Eur's three uses.

PatEx reports agriculture energy by carrier only (``agr_energy-demand-by-vector``).
PyPSA-Eur needs it by use, because it optimises the supply of each use:

- ``total agriculture electricity``: fixed electricity load,
- ``total agriculture heat``: load on the rural heat bus, any heat technology,
- ``total agriculture machinery``: oil load (diesel-equivalent).

Each carrier can serve several uses (diesel for machinery *and* greenhouse heating,
electricity for lighting, heating and motors). The split uses the country's
JRC-IDEES base-year shares (``AGR_fec`` sheet), which is also what PatEx is
calibrated on. The trajectory of each carrier stays PatEx's.

Machinery electrification: PatEx has no lever for it (its agriculture fuel mix is
historical, then held constant; only irrigation electricity and fossil → bio fuel
switches change), so the electric machinery of the base year (IDEES "Motor
drives") is exported as part of ``total agriculture electricity`` and the
``machinery`` column holds liquid fuels only. In PyPSA-Eur this goes with
``agriculture_machinery_electric_share: 0`` and ``agriculture_machinery_oil_share: 1``:
each country then gets exactly its PatEx electricity and liquid-fuel demand, which a
single EU-wide share could not do.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

USES = ["electricity", "heat", "machinery"]

#: carrier groups, as named in the ``agriculture`` rules of extraction_rules.csv
GROUPS = ["electricity", "diesel", "fuel oil", "gas", "solids", "biomass"]

KTOE_TO_TWH = 0.01163

#: IDEES use rows holding a single carrier: row → (group, use)
_SINGLE_CARRIER_ROWS = {
    "Lighting": ("electricity", "electricity"),
    "Ventilation": ("electricity", "electricity"),
    "Specific electricity uses": ("electricity", "electricity"),
    "Pumping devices (electricity)": ("electricity", "electricity"),
    "Motor drives": ("electricity", "machinery"),
    "Farming machine drives (diesel oil and liquid biofuels)": ("diesel", "machinery"),
    "Pumping devices (diesel oil and liquid biofuels)": ("diesel", "machinery"),
}
#: IDEES use rows broken down by carrier in the rows that follow them
_HEAT_ROWS = {"Low enthalpy heat", "Specific heat uses"}
#: IDEES carrier rows under the heat uses → group (None: no PatEx carrier)
_IDEES_CARRIERS = {
    "Electricity": "electricity",
    "Diesel oil and liquid biofuels": "diesel",
    "Fuel oil and other liquids": "fuel oil",
    "Natural gas and biogas": "gas",
    "LPG": "gas",  # PatEx renames LPG to gaseous-ff-natural
    "Solids": "solids",
    "Biomass and waste": "biomass",
    "Solar and geothermal": None,
    "Ambient heat": None,
    "Distributed heat": None,
}


def idees_by_use(path: str | Path, year: int) -> pd.DataFrame:
    """Agriculture final energy of one IDEES Tertiary file: group × use [TWh]."""
    sheet = pd.read_excel(path, "AGR_fec", index_col=0)
    start = "Detailed split of energy consumption (ktoe)"
    end = "Market shares of energy uses (%)"
    block = sheet.loc[start:end, year]
    out = pd.DataFrame(0.0, index=GROUPS, columns=USES)
    in_heat = False
    for row, value in block.items():
        if not isinstance(row, str) or pd.isna(value):
            continue
        if row in _SINGLE_CARRIER_ROWS:
            in_heat = False
            group, use = _SINGLE_CARRIER_ROWS[row]
            out.loc[group, use] += value
        elif row in _HEAT_ROWS:
            in_heat = True
        elif in_heat and row in _IDEES_CARRIERS:
            group = _IDEES_CARRIERS[row]
            if group:
                out.loc[group, "heat"] += value
    return out * KTOE_TO_TWH


def shares_from_idees(
    idees_dir: str | Path, countries: list[str], year: int, country_map: dict[str, str]
) -> pd.DataFrame:
    """Long table ``country, group, electricity, heat, machinery`` (rows sum to 1).

    ``countries`` are IDEES codes (``EL`` for Greece); output uses PyPSA codes.
    Groups with no energy in a country take the EU27 shares, then 100 % heat (the
    only use of every fuel but diesel and electricity in IDEES).
    """
    idees_dir = Path(idees_dir)

    def read(ct: str) -> pd.DataFrame:
        return idees_by_use(idees_dir / ct / f"JRC-IDEES-2023_Tertiary_{ct}.xlsx", year)

    def normalise(df: pd.DataFrame) -> pd.DataFrame:
        return df.div(df.sum(axis=1).where(lambda s: s > 0), axis=0)

    eu = normalise(read("EU27"))
    for group in GROUPS:
        if eu.loc[group].isna().all():
            eu.loc[group] = [float(u == "heat") for u in USES]
    rows = []
    for ct in countries:
        shares = normalise(read(ct)).fillna(eu)
        shares.insert(0, "country", country_map.get(ct, ct))
        rows.append(shares.rename_axis("group").reset_index())
    eu = eu.rename_axis("group").reset_index()
    eu.insert(0, "country", "EU27")
    out = pd.concat(rows + [eu], ignore_index=True)
    out["base_year"] = year
    return out[["country", "group", *USES, "base_year"]]


def split_agriculture(long: pd.DataFrame, shares: pd.DataFrame) -> pd.DataFrame:
    """Turn ``target == "agriculture"`` rows (category = carrier group) into
    ``energy_totals`` rows for the three PyPSA-Eur columns, plus the informative
    ``agriculture machinery electric`` (already inside ``total agriculture electricity``).

    Countries without shares take the EU27 ones.
    """
    agr = long[long["target"] == "agriculture"]
    unknown = set(agr["category"]) - set(GROUPS)
    if unknown:
        raise ValueError(f"agriculture rules with unknown carrier groups: {sorted(unknown)}")
    table = shares.set_index(["country", "group"])[USES]
    eu = table.loc["EU27"]

    def lookup(row) -> pd.Series:
        key = (row.country, row.category)
        return table.loc[key] if key in table.index else eu.loc[row.category]

    s = agr.apply(lookup, axis=1)
    parts = agr[["country", "year"]].copy()
    for use in USES:
        parts[use] = agr["value"] * s[use]
    is_elec = agr["category"] == "electricity"
    parts["machinery electric"] = parts["machinery"].where(is_elec, 0.0)
    parts["machinery"] = parts["machinery"].where(~is_elec, 0.0)
    parts["electricity"] += parts["machinery electric"]
    summed = parts.groupby(["country", "year"]).sum()
    names = {
        "electricity": "total agriculture electricity",
        "heat": "total agriculture heat",
        "machinery": "total agriculture machinery",
        "machinery electric": "agriculture machinery electric",
    }
    out = summed.rename(columns=names).stack().rename("value").reset_index()
    out = out.rename(columns={"level_2": "category"})
    out.insert(0, "target", "energy_totals")
    out["unit"] = "TWh"
    return out[["target", "category", "country", "year", "unit", "value"]]
