"""Demand of countries outside PatEx: their own 2023 data on PatEx's EU trend.

A modelled country without PatEx data (GB, NO, CH…) gets rows in the PatEx tables
(``energy_totals``, ``industry``, ``parameters``) so that every soft-link hook treats
it like a PatEx country. Rules (user, 2026-11-12):

- **Sector totals** follow the *relative* change of the sum over the PatEx countries
  ("EU"): ``total_c(h) = total_c(base) × EU(h) / EU(base)``.
- **Fuel shares** within a sector follow the EU's relative change: a share the EU
  *reduces* is scaled like the EU's (``s_c × s_EU(h) / s_EU(base)``); a share the EU
  *raises* keeps the country's relative position in what is left to switch
  (``1 − s = (1 − s_c) × (1 − s_EU(h)) / (1 − s_EU(base))``), so a country starting
  low (GB electric road 0.1 %) catches up as the EU approaches full adoption. A
  country without a base value takes the EU share. Shares of one total are capped so
  that their sum stays ≤ 1 (energy totals: the rest is the unlisted fuels) or
  renormalised to 1 (industry, where the carriers make up the whole).
- **District heat share**: proportional to the EU's change (≤ 1): full district
  heating is no end state, so the catch-up rule would overshoot.
- **Electricity base load**: no absolute value (PyPSA-Eur's electric heating can
  exceed building electricity, NO): ``electricity base load factor`` in the parameters
  = EU(h) / EU(base), applied to the measured residual load. **Electric cooling** stays
  in that residual (no national data on today's cooling, e.g. GB, NO): no own load
  (``electricity {residential,services} space cooling`` NaN), and the factor is that
  of base load + cooling.
- **Waste-to-energy** (non-renewable waste in power and heat plants): the
  country's share of the EU in Eurostat's input to electricity and heat generation,
  applied to PatEx's EU fuel; CO2 at PatEx's EU factor.
- **Industry** places the country relative to the EU in one source (Eurostat energy
  balances, UNFCCC inventory), same year on both sides, and applies that to PatEx's
  EU values: ``x_c(h) = x_EU,PatEx(h) × src_c / src_EU``. This keeps PatEx's carrier
  definitions (coke in coal, waste CO2 in process emissions…).

Pure pandas: the fork's ``build_patex_demands`` feeds the base data.
"""

from __future__ import annotations

import pandas as pd

from .export import HEAT_COLUMNS, ROUTE_PRODUCTS, horizon_tables

#: energy-totals fuel columns → the total(s) they are a share of
ENERGY_SHARES: dict[str, list[str]] = {
    "electricity passenger cars": ["total passenger cars"],
    "electricity other road passenger": ["total other road passenger"],
    "electricity light duty road freight": ["total light duty road freight"],
    "electricity road": ["total road"],
    "hydrogen road": ["total road"],
    "gas road": ["total road"],
    "electricity rail": ["total rail"],
    "hydrogen rail": ["total rail"],
    "electricity aviation": ["total domestic aviation", "total international aviation"],
    "electricity navigation": ["total domestic navigation", "total international navigation"],
    "hydrogen navigation": ["total domestic navigation", "total international navigation"],
    "electricity residential space": ["total residential space"],
    "electricity residential water": ["total residential water"],
    "electricity residential cooking": ["total residential cooking"],
    "electricity services space": ["total services space"],
    "electricity services water": ["total services water"],
    "electricity services cooking": ["total services cooking"],
    **{
        f"{fuel} cooking": ["total residential cooking", "total services cooking"]
        for fuel in ("gas", "oil", "coal", "solid biomass", "hydrogen")
    },
    "agriculture machinery electric": ["total agriculture electricity"],
}

BASE_LOAD = "electricity base load"
#: electric space cooling (own load with patex.cooling)
COOLING = ("electricity residential space cooling", "electricity services space cooling")
#: energy-totals columns with no national value (set in the network)
NO_VALUE = (BASE_LOAD, *COOLING)

#: industry carriers making up the whole of one group (shares renormalised to 1)
INDUSTRY_GROUPS: dict[str, list[str]] = {
    "energy": [
        "coal",
        "electricity",
        "hydrogen",
        "low-temperature heat",
        "methane",
        "oil for industry",
        "solid biomass",
    ],
    "feedstock": ["methane feedstock", "naphtha"],
}
#: industry columns scaled as a whole, by the source column named here
INDUSTRY_SCALED = {
    "process emission": "process emission",
    "process emission from feedstock": "naphtha",
}
#: industry columns PatEx sets to 0 (their energy is in other carriers)
INDUSTRY_ZERO = ["coke", "ammonia", "methanol"]


def eu_tables(long: pd.DataFrame, year: int, waste_factor=None) -> dict[str, pd.Series]:
    """PatEx tables of ``year`` summed over all bundle countries (the "EU")."""
    out = {}
    for target, wide in horizon_tables(long, year, waste_factor).items():
        if target == "parameters":
            continue
        out[target] = wide.sum()
    # district heat share and loss of the EU (ratios of sums, not sums of ratios)
    sel = long[(long["year"] == year) & (long["target"] == "parameters")]
    p = sel.groupby("category")["value"].sum()
    heat = out["energy_totals"][HEAT_COLUMNS].sum()
    params = {}
    if "district heat" in p:
        params["district heat share"] = p["district heat"] / heat if heat > 0 else 0.0
    if "district heat delivered" in p and p["district heat delivered"] > 0:
        params["district heating loss"] = p["district heat losses"] / p["district heat delivered"]
    for k in ("number bev", "number phev"):
        if k in p:
            params[k] = p[k]
    out["parameters"] = pd.Series(params)
    routes = long[(long["year"] == year) & (long["target"] == "routes")]
    out["routes"] = routes.groupby("category")["value"].sum()
    return out


def with_routes(industry: pd.Series, routes: pd.Series) -> pd.Series:
    """EU industry columns with the routes added back (PatEx's industry as a whole, the
    scope of Eurostat's industry balances)."""
    out = industry.copy()
    for product in ROUTE_PRODUCTS:
        for key, value in routes.items():
            if key.startswith(f"{product}|") and key.split("|", 1)[1] in out.index:
                out[key.split("|", 1)[1]] += value
    return out


def split_routes(
    industry: pd.DataFrame,
    production_base: pd.DataFrame,
    eu_routes_base: pd.Series,
    eu_routes_h: pd.Series,
) -> pd.DataFrame:
    """Take the product routes out of the countries' industry (as for PatEx countries).

    ``production_base``: country × product base-year production [kt] (PyPSA-Eur data).
    Production follows the EU production trend; its energy and process CO2 per tonne
    are the EU's (PatEx) at the horizon and are subtracted from the carriers (≥ 0);
    the product demand [TWh] = production × MWh/t."""
    out = industry.copy()
    for product, mwh_per_t in ROUTE_PRODUCTS.items():
        col = f"{product} production"
        eu_b, eu_n = eu_routes_base.get(col, 0.0), eu_routes_h.get(col, 0.0)
        base = production_base.get(product, pd.Series(0.0, index=out.index))
        prod = base.reindex(out.index).fillna(0.0) * (eu_n / eu_b if eu_b > 0 else 0.0)
        for key, value in eu_routes_h.items():
            if not key.startswith(f"{product}|"):
                continue
            column = key.split("|", 1)[1]
            if column in out and eu_n > 0:
                out[column] = (out[column] - prod * value / eu_n).clip(lower=0.0)
        out[product] = prod * mwh_per_t / 1e3
    return out


def base_load_factor(eu_base: pd.Series, eu_h: pd.Series) -> float:
    """EU(h) / EU(base) of the residual electricity load of a fallback country:
    base load + electric cooling (cooling stays in its measured load)."""
    def total(s: pd.Series) -> float:
        return s[BASE_LOAD] + sum(s[c] for c in COOLING if c in s)

    return total(eu_h) / total(eu_base)


def _ratio(num, den):
    return num / den if den > 0 else float("nan")


def relative_share(
    c_base: float | None, eu_base: float, eu_h: float, proportional: bool = False
) -> float:
    """Country share at the horizon on the EU's relative change (see module doc):
    proportional where the EU share falls, on the remainder where it rises; the EU
    share where the country has no base value."""
    if c_base is None or pd.isna(c_base):
        return eu_h
    c_base = min(max(c_base, 0.0), 1.0)
    if proportional or eu_h < eu_base:
        if not eu_base > 0:
            return eu_h
        return c_base * eu_h / eu_base
    if eu_base >= 1.0:
        return c_base
    return 1.0 - (1.0 - c_base) * (1.0 - eu_h) / (1.0 - eu_base)


def trend_energy_totals(
    base: pd.DataFrame, eu_base: pd.Series, eu_h: pd.Series, columns: list[str]
) -> pd.DataFrame:
    """Energy totals of countries ``base.index`` at the horizon.

    ``base`` holds the countries' base-year values in PatEx column names (fuel
    columns missing or NaN: no national value, EU share used). ``columns`` are the
    PatEx table's columns.
    """
    out = pd.DataFrame(index=base.index, columns=columns, dtype=float)
    totals = [c for c in columns if c not in ENERGY_SHARES and c not in NO_VALUE]
    for col in NO_VALUE:
        if col in columns:
            out[col] = float("nan")  # scaled in the network (base load factor)
    for col in totals:
        if col not in base:
            raise ValueError(f"no base-year value for '{col}'")
        out[col] = base[col] * _ratio(eu_h.get(col, 0.0), eu_base.get(col, 0.0))
        if not eu_base.get(col, 0.0) > 0:  # EU had none in the base year
            out[col] = 0.0
    shares = {}
    for col, parents in ENERGY_SHARES.items():
        if col not in columns:
            continue
        eu_b = _ratio(eu_base.get(col, 0.0), eu_base[parents].sum())
        eu_n = _ratio(eu_h.get(col, 0.0), eu_h[parents].sum())
        eu_b = 0.0 if pd.isna(eu_b) else eu_b
        eu_n = 0.0 if pd.isna(eu_n) else eu_n
        c_tot = base[parents].sum(axis=1)
        c_share = (base[col] / c_tot.where(c_tot > 0)) if col in base else None
        shares[col] = pd.Series(
            [relative_share(None if c_share is None else c_share[c], eu_b, eu_n)
             for c in base.index],
            index=base.index,
        ).clip(0.0, 1.0)
    # shares of the same total(s) stay ≤ 1 together
    groups: dict[tuple, list[str]] = {}
    for col in shares:
        groups.setdefault(tuple(ENERGY_SHARES[col]), []).append(col)
    for parents, cols in groups.items():
        s = pd.DataFrame({c: shares[c] for c in cols})
        excess = s.sum(axis=1).clip(lower=1.0)
        s = s.div(excess, axis=0)
        parent_total = out[list(parents)].sum(axis=1)
        for c in cols:
            out[c] = s[c] * parent_total
    return out


def trend_industry(
    src_c: pd.DataFrame,
    src_eu: pd.DataFrame,
    eu_base: pd.Series,
    eu_h: pd.Series,
    columns: list[str],
) -> pd.DataFrame:
    """Industry of countries ``src_c.index`` at the horizon.

    ``src_c`` / ``src_eu``: source values (Eurostat, UNFCCC) per country and per
    country's matching EU sum (same year, rows = countries) in PatEx carrier names;
    NaN = no source for that carrier (EU share used).
    """
    out = pd.DataFrame(0.0, index=src_c.index, columns=columns)
    # carriers without a source column (hydrogen…): NaN, i.e. the EU share
    needed = [k for g in INDUSTRY_GROUPS.values() for k in g] + list(INDUSTRY_SCALED.values())
    extra = [k for k in needed if k not in src_c.columns]
    src_c = src_c.reindex(columns=[*src_c.columns, *extra])
    src_eu = src_eu.reindex(columns=[*src_eu.columns, *[k for k in needed if k not in src_eu.columns]])
    for group, carriers in INDUSTRY_GROUPS.items():
        carriers = [k for k in carriers if k in columns]
        eu_tot = eu_h[carriers].sum()
        src_tot_c = src_c[carriers].sum(axis=1, min_count=1)
        src_tot_eu = src_eu[carriers].sum(axis=1, min_count=1)
        total = eu_tot * src_tot_c / src_tot_eu
        eu_share = eu_h[carriers] / eu_tot if eu_tot > 0 else eu_h[carriers] * 0.0
        eu_b_tot = eu_base[carriers].sum()
        eu_b_share = eu_base[carriers] / eu_b_tot if eu_b_tot > 0 else eu_share * 0.0
        for c in src_c.index:
            rel = {}
            for k in carriers:
                # base share in PatEx terms = EU PatEx base share × the country's
                # share relative to the EU's in the same source; then the EU's
                # relative change; no source value: the EU share
                sc = _ratio(src_c.at[c, k], src_tot_c[c])
                se = _ratio(src_eu.at[c, k], src_tot_eu[c])
                ok = pd.notna(sc) and pd.notna(se) and se > 0
                c_base = min(eu_b_share[k] * sc / se, 1.0) if ok else None
                rel[k] = relative_share(c_base, eu_b_share[k], eu_share[k])
            s = pd.Series(rel)
            s = s / s.sum() if s.sum() > 0 else s
            out.loc[c, carriers] = (s * total[c]).values
    for col, source in INDUSTRY_SCALED.items():
        if col in columns:
            out[col] = eu_h.get(col, 0.0) * src_c[source] / src_eu[source]
    for col in INDUSTRY_ZERO:
        if col in columns:
            out[col] = 0.0
    return out.fillna(0.0)


def trend_waste_to_energy(
    src_c: pd.Series, src_eu: pd.Series, eu_fuel: float, eu_co2: float
) -> pd.DataFrame:
    """Non-renewable waste burned in power and heat plants of the countries of
    ``src_c`` at the horizon: ``fuel`` [TWh] = PatEx EU fuel × the country's share of
    the EU in the source (Eurostat input of non-renewable waste to electricity and heat
    generation, same year on both sides; ``src_eu`` per country), ``co2`` at the PatEx
    EU factor (``eu_co2 / eu_fuel``)."""
    fuel = eu_fuel * src_c / src_eu.reindex(src_c.index)
    fuel = fuel.where(src_eu.reindex(src_c.index) > 0, 0.0).fillna(0.0)
    factor = eu_co2 / eu_fuel if eu_fuel > 0 else 0.0
    return pd.DataFrame({"fuel": fuel, "co2": fuel * factor})


def trend_parameters(
    dh_share_base: pd.Series,
    eu_base: pd.Series,
    eu_h: pd.Series,
    ev_energy_c: pd.Series,
    ev_energy_eu: float,
    columns: list[str],
    base_load_factor: float | None = None,
) -> pd.DataFrame:
    """Parameters of the countries of ``dh_share_base``: district heat share on the
    EU relative trend (≤ 1), EU network loss rate, EV fleet proportional to the
    country's electric passenger-car energy (EU fleet per unit of EV energy);
    ``co2 stored``: none (fallback countries are outside the PatEx total)."""
    out = pd.DataFrame(index=dh_share_base.index, columns=columns, dtype=float)
    # proportional: 100 % district heating is no end state to converge to
    out["district heat share"] = [
        min(relative_share(dh_share_base[c], eu_base.get("district heat share", 0.0),
                           eu_h.get("district heat share", 0.0), proportional=True), 1.0)
        for c in dh_share_base.index
    ]
    out["district heating loss"] = eu_h.get("district heating loss", 0.0)
    for k in ("number bev", "number phev"):
        per_twh = _ratio(eu_h.get(k, 0.0), ev_energy_eu)
        out[k] = ev_energy_c * (0.0 if pd.isna(per_twh) else per_twh)
    if "co2 stored" in out:
        out["co2 stored"] = float("nan")
    if base_load_factor is not None:
        out["electricity base load factor"] = base_load_factor
    return out
