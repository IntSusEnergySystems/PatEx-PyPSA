"""PatEx useful building heat → final-to-useful efficiencies for PyPSA-Eur (audit #4).

PyPSA-Eur turns the final-energy heat totals into heat demand with one efficiency per
country, sector and use (``heating_efficiencies.csv``: today's carrier mix, from
JRC-IDEES). PatEx's carrier mix and efficiencies change over time, so that conversion
drifts away from PatEx's useful heat in later horizons. PatEx outputs no useful heat:
its buildings module computes ``final = useful / energy-efficiency`` per technology
internally and reports final energy by carrier only. This module rebuilds PatEx's
useful heat from the final energy by carrier (run pickle) and PatEx's efficiencies
and technology mix (dataset, lever-dependent), and returns, per country, the
efficiency ``useful / final`` that makes PyPSA-Eur's heat demand equal PatEx's useful
heat (``final`` = the bundle's ``total {sector} {use}`` columns).

Carriers and technologies (PatEx ``energy-way-of-prod``):

- gas and oil: the fuel switch (biogas, hydrogen, synthetic gas; bio and synthetic
  liquids) only renames the carrier, so every gaseous carrier and hydrogen use the gas
  boiler's efficiency and every liquid carrier the oil boiler's;
- solid biomass and coal: their own boilers;
- ambient heat: from heat pumps or solar thermal, split by the technology mix;
- heat pumps: useful heat = electricity + ambient heat (PatEx's two carrier rows
  satisfy 1/eff_electricity + 1/eff_ambient = 1), with the electricity derived from
  the ambient heat; the rest of the electricity is direct electric heating;
- district heat: delivered heat, efficiency 1.

Efficiencies and mix are averaged over the building uses of each building type
(residential: sfh, mfh; services: the non-residential uses): PatEx's run pickle has no
building-use dimension. Only ``load_heat_technologies`` needs the ``patex`` package.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

FINAL = "bld_energy-demand[TWh]"
INCL_DH = "bld_energy-demand-incl-district-heating[TWh]"
EFFICIENCY = "energy-efficiency[%]"
MIX = "technology-mix[%]"

KEYS = ["Country", "building-type", "end-use"]
#: PatEx (building-type, end-use) → PyPSA-Eur heat column
COLUMNS = {
    ("residential", "heating"): "total residential space",
    ("residential", "hotwater"): "total residential water",
    ("non-residential", "heating"): "total services space",
    ("non-residential", "hotwater"): "total services water",
}
EFFICIENCY_COLUMNS = [f"{c} efficiency" for c in COLUMNS.values()]
RESIDENTIAL_USES = {"sfh", "mfh"}

#: fuel carrier → (technology, carrier of its efficiency row)
FUEL_TECHNOLOGY = {
    **{
        c: ("gaseous-ff-natural", "gaseous-ff-natural")
        for c in ("gaseous-ff-natural", "gaseous-bio", "gaseous-syn", "hydrogen")
    },
    **{c: ("liquid-ff-oil", "liquid-ff-oil") for c in ("liquid-ff-oil", "liquid-bio", "liquid-syn")},
    "solid-biomass": ("solid-biomass", "solid-biomass"),
    "solid-ff-coal": ("solid-ff-coal", "solid-ff-coal"),
}
HEAT_PUMP, SOLAR_THERMAL, DIRECT = "elec-hp", "solar-thermal", "elec-direct"
AMBIENT, ELECTRICITY = "ambiant", "electricity"


def load_heat_technologies(
    dataset: str,
    countries: list[str],
    levers_default: float,
    levers_file: str | Path | None = None,
    max_year: int = 2050,
) -> pd.DataFrame:
    """PatEx efficiencies and technology mix of building heating and hot water.

    Tidy table ``Country, Years, building-type, end-use, energy-way-of-prod,
    energy-carrier, energy-efficiency[%], technology-mix[%]`` (mean over the building
    uses of each type; the mix is per technology, repeated on its carrier rows).
    ``countries`` are PatEx codes; the levers must be those of the PatEx run (same
    meaning as ``patex run --levers-default / --levers-file``).
    """
    from patex.cli import lever_codes
    from patex.core.data import OTS_FTS
    from patex.core.dataset import Dataset

    levers = {code: levers_default for code in lever_codes(dataset)}
    dynamic = {}
    if levers_file:
        spec = json.loads(Path(levers_file).read_text())
        levers.update(spec.get("levers", {}))
        dynamic = spec.get("dynamic_levers", {})
    ds = Dataset(
        dataset,
        country_filter="|".join(countries),
        max_year=max_year,
        levers=levers,
        dynamic_levers=dynamic,
    )
    parts = {}
    for name, value in (("energy-efficiency", EFFICIENCY), ("technology-mix", MIX)):
        df = ds.load("bld", name, OTS_FTS)
        df = df[df["end-use"].isin(["heating", "hotwater"])].copy()
        df["building-type"] = df["building-use"].map(
            lambda u: "residential" if u in RESIDENTIAL_USES else "non-residential"
        )
        dims = ["Country", "Years", "building-type", "end-use", "energy-way-of-prod"]
        if "energy-carrier" in df:
            dims.append("energy-carrier")
        parts[name] = df.groupby(dims)[value].mean().reset_index()
    return parts["energy-efficiency"].merge(
        parts["technology-mix"],
        on=["Country", "Years", "building-type", "end-use", "energy-way-of-prod"],
        how="left",
    )


def _technology_frame(tech: pd.DataFrame, horizon: int, column: str) -> pd.DataFrame:
    """``(Country, building-type, end-use)`` × ``(technology, carrier)`` of ``column``."""
    sel = tech[tech["Years"] == horizon]
    if sel.empty:
        raise ValueError(f"no PatEx heating efficiencies for {horizon}")
    return sel.pivot_table(
        index=KEYS, columns=["energy-way-of-prod", "energy-carrier"], values=column, aggfunc="mean"
    )


def useful_heat(
    tables: dict[str, pd.DataFrame], tech: pd.DataFrame, horizon: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """PatEx final heat (the bundle's base) and useful heat [TWh/a] of ``horizon``.

    Both country (PatEx code) × ``total {residential,services} {space,water}``.
    Final = decentralised final energy + district heat − ambient heat (the extraction
    rules); useful = Σ fuel × efficiency + heat pumps (electricity + ambient) + solar
    thermal + direct electric × efficiency + district heat.
    """
    final_by_carrier = tables[FINAL]
    w = final_by_carrier[
        (final_by_carrier["Years"] == horizon)
        & final_by_carrier["end-use"].isin(["heating", "hotwater"])
    ].pivot_table(index=KEYS, columns="energy-carrier", values=FINAL, aggfunc="sum").fillna(0.0)
    incl = tables[INCL_DH]
    incl = incl[incl["Years"] == horizon].groupby(KEYS)[INCL_DH].sum().reindex(w.index).fillna(0.0)

    unknown = set(w.columns) - set(FUEL_TECHNOLOGY) - {AMBIENT, ELECTRICITY}
    if unknown and (w[sorted(unknown)].abs() > 1e-9).any().any():
        raise ValueError(f"building heat carriers without a PatEx technology: {sorted(unknown)}")

    district = incl - w.sum(axis=1)
    if (district < -1e-6 * incl.abs().clip(lower=1.0)).any():
        raise ValueError("PatEx heat incl. district heating below its decentralised energy")
    district = district.clip(lower=0.0)
    ambient = w.get(AMBIENT, 0.0)
    electricity = w.get(ELECTRICITY, 0.0)

    eff = _technology_frame(tech, horizon, EFFICIENCY).reindex(w.index)
    mix = _technology_frame(tech, horizon, MIX).reindex(w.index)

    def efficiency(technology: str, carrier: str) -> pd.Series:
        if (technology, carrier) not in eff:
            raise ValueError(f"no PatEx efficiency for {technology} / {carrier}")
        return eff[(technology, carrier)]

    useful = district.copy()
    for carrier, (technology, eff_carrier) in FUEL_TECHNOLOGY.items():
        if carrier not in w:
            continue
        e = efficiency(technology, eff_carrier)
        used = w[carrier] > 0
        if e[used].isna().any() or (e[used] <= 0).any():
            raise ValueError(f"no PatEx efficiency for {technology} where {carrier} is used")
        useful = useful + (w[carrier] * e).where(used, 0.0)

    # ambient heat: heat pumps vs solar thermal, by their ambient heat per unit of mix
    eta_hp_amb = efficiency(HEAT_PUMP, AMBIENT)
    eta_hp_el = efficiency(HEAT_PUMP, ELECTRICITY)
    hp = (mix.get((HEAT_PUMP, AMBIENT), 0.0) / eta_hp_amb).fillna(0.0)
    if (SOLAR_THERMAL, AMBIENT) in eff:
        eta_st = eff[(SOLAR_THERMAL, AMBIENT)].fillna(1.0)
        st = (mix.get((SOLAR_THERMAL, AMBIENT), 0.0) / eta_st).fillna(0.0)
    else:
        eta_st, st = 1.0, 0.0 * hp
    hp_share = (hp / (hp + st)).where(hp + st > 0, 1.0)
    ambient_hp = ambient * hp_share
    ambient_st = ambient - ambient_hp

    # heat-pump electricity from its ambient heat; the rest is direct electric heating
    electricity_hp = (ambient_hp * eta_hp_amb / eta_hp_el).fillna(0.0)
    over = electricity_hp > electricity * (1 + 1e-6) + 1e-9
    if over.any():
        # PatEx calibrates electricity and ambient heat separately on statistics, so
        # their ratio can leave the COP: all electricity is then heat-pump
        # electricity and the heat-pump output is electricity + ambient heat
        logger.warning(
            "PatEx ambient heat implies more heat-pump electricity than reported in %s "
            "%s: all of it counted as heat pump (useful = electricity + ambient)",
            horizon, list(electricity_hp.index[over])
        )
    electricity_hp = electricity_hp.clip(upper=electricity)
    direct = electricity - electricity_hp
    eta_direct = efficiency(DIRECT, ELECTRICITY)
    if (eta_direct[direct > 0].isna()).any():
        raise ValueError("no PatEx efficiency for direct electric heating where it is used")
    useful = (
        useful
        + electricity_hp
        + ambient_hp
        + ambient_st * eta_st
        + (direct * eta_direct).where(direct > 0, 0.0)
    )
    final = incl - ambient

    def to_columns(s: pd.Series) -> pd.DataFrame:
        out = s.reset_index(name="value")
        out["column"] = [COLUMNS[(b, u)] for b, u in zip(out["building-type"], out["end-use"])]
        return out.pivot_table(index="Country", columns="column", values="value", aggfunc="sum").reindex(
            columns=list(COLUMNS.values()), fill_value=0.0
        ).fillna(0.0)

    return to_columns(final), to_columns(useful)


def heating_efficiencies(final: pd.DataFrame, useful: pd.DataFrame) -> pd.DataFrame:
    """``total {sector} {use} efficiency`` = useful / final (1 where there is no heat)."""
    eff = (useful / final.where(final > 0)).fillna(1.0)
    eff.columns = [f"{c} efficiency" for c in eff.columns]
    return eff


def patex_heating_efficiencies(
    efficiencies: pd.DataFrame, parameters: pd.DataFrame
) -> pd.DataFrame:
    """PyPSA-Eur's ``heating_efficiencies`` (country rows) with PatEx's where the bundle
    has them (PatEx countries; fallback countries keep PyPSA-Eur's)."""
    missing = [c for c in EFFICIENCY_COLUMNS if c not in parameters]
    if missing:
        raise ValueError(
            f"PatEx parameters without {missing}: re-export the bundle with the PatEx "
            "dataset and levers (patex-pypsa export-coupling --dataset ... --levers-default ...)"
        )
    patex = parameters[EFFICIENCY_COLUMNS].dropna(how="any")
    countries = efficiencies.index.intersection(patex.index)
    out = efficiencies.copy()
    out.loc[countries, EFFICIENCY_COLUMNS] = patex.loc[countries, EFFICIENCY_COLUMNS].to_numpy()
    logger.info("heating efficiencies from PatEx for %s", sorted(countries))
    return out
