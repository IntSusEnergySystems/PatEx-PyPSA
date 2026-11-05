"""PatEx CO2 factors of fossil fuels → PyPSA-Eur ``CO2 intensity`` per carrier.

PyPSA-Eur computes combustion CO2 itself, from the fuel it supplies and one CO2
intensity per carrier (``costs.at[carrier, "CO2 intensity"]``, tCO2/MWh). PatEx has
one factor per sector and fuel (diesel, gasoline, kerosene, ...), read from its
dataset (they are inputs, not in the run pickle). For each PyPSA-Eur carrier the
PatEx factors are averaged, weighted by the fossil final energy PatEx uses in the
countries and horizon of the bundle.

Only ``load_co2_factors`` needs the ``patex`` package (PatEx environment and access to
the dataset); the rest needs pandas only.
"""

from __future__ import annotations

import pandas as pd

#: (sector, PatEx dataset module, variable, unit factor to tCO2/MWh)
FACTOR_SOURCES = [
    ("ind", "ind", "ind-combustion-emission-factor", 1.0),  # Mt/TWh
    ("tra", "tra", "tra-combustion-emission-factor", 1.0),  # Mt/TWh
    ("agr", "agr", "agr-combustion-emission-factor", 1.0),  # Mt/TWh
    ("bld", "bld", "bld-emission-factor", 1e-3),  # g/kWh
]

#: PyPSA-Eur carrier → PatEx fossil carriers it stands for
PYPSA_CARRIERS = {
    "gas": ["gaseous-ff-natural"],
    "oil": [
        "liquid-ff-oil",
        "liquid-ff-diesel",
        "liquid-ff-gasoline",
        "liquid-ff-kerosene",
        "liquid-ff-marinefueloil",
    ],
    "coal": ["solid-ff-coal"],
}

#: sector → PatEx run variables holding its final energy by ``energy-carrier``
ENERGY_VARIABLES = {
    "ind": ["ind_energy-demand-by-carrier-feedstock[TWh]"],
    "tra": [
        "tra_energy-demand-domestic-by-carrier-user-vehicule[TWh]",
        "tra_energy-demand-bunkers-by-type-carrier[TWh]",
    ],
    "agr": ["agr_energy-demand-by-vector[TWh]"],
    "bld": ["bld_energy-demand[TWh]"],
}

FACTOR = "tCO2/MWh"


def load_co2_factors(dataset: str, countries: list[str]) -> pd.DataFrame:
    """CO2 factors ``Country, sector, energy-carrier, tCO2/MWh`` from a PatEx dataset.

    ``countries`` are PatEx codes (``EL`` for Greece). Factors that depend on another
    dimension (building type) are averaged over it.
    """
    from patex.core.data import RCP
    from patex.core.dataset import Dataset

    ds = Dataset(dataset, country_filter="|".join(countries), max_year=2050, levers={})
    parts = []
    for sector, module, name, unit in FACTOR_SOURCES:
        df = ds.load(module, name, RCP)
        value = next(c for c in df.columns if c.startswith(name + "["))
        co2 = df[df["gaes"] == "CO2"]
        f = co2.groupby(["Country", "energy-carrier"])[value].mean().mul(unit)
        parts.append(f.rename(FACTOR).reset_index().assign(sector=sector))
    return pd.concat(parts, ignore_index=True)[["Country", "sector", "energy-carrier", FACTOR]]


def fossil_energy(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """PatEx final energy ``Country, Years, sector, energy-carrier, TWh`` of fossil fuels."""
    fossil = {c for cs in PYPSA_CARRIERS.values() for c in cs}
    parts = []
    for sector, variables in ENERGY_VARIABLES.items():
        for variable in variables:
            t = tables[variable]
            t = t[t["energy-carrier"].isin(fossil)]
            e = t.groupby(["Country", "Years", "energy-carrier"])[variable].sum()
            parts.append(e.rename("TWh").reset_index().assign(sector=sector))
    out = pd.concat(parts, ignore_index=True)
    return out.groupby(["Country", "Years", "sector", "energy-carrier"], as_index=False)["TWh"].sum()


def co2_intensity(energy: pd.DataFrame, factors: pd.DataFrame, horizon: int) -> pd.Series:
    """PyPSA-Eur carrier → CO2 intensity [tCO2/MWh], PatEx factors weighted by energy.

    A (sector, fuel) used in the run without a factor fails, so that no fossil
    energy is silently counted as CO2-free.
    """
    e = energy[energy["Years"] == horizon]
    merged = e.merge(factors, on=["Country", "sector", "energy-carrier"], how="left")
    missing = merged[merged[FACTOR].isna() & (merged["TWh"] > 0)]
    if not missing.empty:
        raise ValueError(f"no PatEx CO2 factor for:\n{missing.drop_duplicates(['sector', 'energy-carrier'])}")
    out = {}
    for carrier, fuels in PYPSA_CARRIERS.items():
        sel = merged[merged["energy-carrier"].isin(fuels)]
        total = sel["TWh"].sum()
        if total > 0:
            out[carrier] = (sel["TWh"] * sel[FACTOR]).sum() / total
        else:  # no use of this fuel left: plain mean of the factors
            out[carrier] = factors.loc[factors["energy-carrier"].isin(fuels), FACTOR].mean()
    return pd.Series(out, name="CO2 intensity").rename_axis("carrier")


def industry_factor(factors: pd.DataFrame, carrier: str) -> pd.Series:
    """Country → PatEx industry CO2 factor of ``carrier`` [tCO2/MWh = MtCO2/TWh]."""
    f = factors[(factors["sector"] == "ind") & (factors["energy-carrier"] == carrier)]
    return f.set_index("Country")[FACTOR]


REFINERY_EMISSIONS = "clm_emissions-by-em-or-capt-module-sector[MtCO2e]"
REFINERY_OUTPUT = "elc_net-energy-production-by-carrier-way-of-prod[TWh]"


def refinery_co2_intensity(tables: dict[str, pd.DataFrame], horizon: int) -> float:
    """PatEx refinery CO2 per MWh of oil products [tCO2/MWh], over every country of the run.

    Emissions before capture over refinery output, like PyPSA-Eur's
    ``oil_refining_emissions`` (CO2 per MWh of fossil oil delivered by refining).
    """
    em = tables[REFINERY_EMISSIONS]
    em = em[
        (em["Years"] == horizon)
        & (em["emissions-or-capture"] == "emissions")
        & (em["module"] == "elc")
        & (em["sector"] == "refineries")
    ][REFINERY_EMISSIONS].sum()
    out = tables[REFINERY_OUTPUT]
    out = out[
        (out["Years"] == horizon)
        & (out["way-of-production"] == "refineries-oil")
        & (out["energy-carrier"] == "liquid")
    ][REFINERY_OUTPUT].sum()
    if out <= 0:
        raise ValueError(f"no PatEx refinery output in {horizon}")
    return em / out
