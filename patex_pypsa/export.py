"""Write the PatEx → PyPSA-Eur coupling bundle.

Layout (mirrors TIMES_PyPSA's ``<coupling_dir>``)::

    <coupling_dir>/
    ├── patex/run.pkl                      # output of `patex run ... -o`
    ├── mappings/                          # copy of the rules used (frozen per run)
    └── pypsa_inputs/
        ├── patex_energy_totals_{h}.csv    # country × energy_totals columns [TWh/a]
        ├── patex_industry_{h}.csv         # country × industrial demand columns [TWh/a, MtCO2/a]
        ├── patex_parameters_{h}.csv       # country × district heat share [-], district heating loss [-], number bev, number phev, co2 stored [Mt/a], waste to energy fuel [TWh/a] / co2 [Mt/a], total {sector} {use} efficiency [-]
        ├── patex_heat_technologies.csv    # PatEx heating efficiencies and technology mix used (dataset, levers of the run)
        ├── patex_supply_{h}.csv           # country × fuel gross imports, domestic production [TWh/a]
        ├── patex_co2_intensity_{h}.csv    # PyPSA-Eur carrier → CO2 intensity [tCO2/MWh], + oil refining
        ├── patex_co2_factors.csv          # PatEx factors used (sector, fuel) [tCO2/MWh]
        ├── patex_demands_long.csv         # every horizon, long format, for QA
        ├── sankey_flows.csv               # fuel → sector → PyPSA-Eur input [TWh], for the report
        ├── patex_indicators.csv           # PatEx output series, for the report
        ├── coverage.csv                   # PatEx energy picked by no rule
        └── manifest.json                  # provenance
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import __version__
from .agriculture import split_agriculture
from .emissions import (
    co2_intensity,
    fossil_energy,
    industry_factor,
    refinery_co2_intensity,
    waste_to_energy,
)
from .heat import heating_efficiencies, useful_heat
from .indicators import INDICATORS_FILE, indicator_series, load_definitions
from .sankey import SANKEY_FLOWS_FILE, SANKEY_NODES_FILE, load_flow_rules, sankey_flows
from .extraction import coverage, extract, load_rules
from .io import load_patex_tables, sha256

logger = logging.getLogger(__name__)

RULES_FILE = "extraction_rules.csv"
COUNTRIES_FILE = "mapping_countries.csv"
AGRICULTURE_SHARES_FILE = "agriculture_use_shares.csv"
MAPPING_FILES = (
    RULES_FILE,
    COUNTRIES_FILE,
    AGRICULTURE_SHARES_FILE,
    SANKEY_FLOWS_FILE,
    SANKEY_NODES_FILE,
    INDICATORS_FILE,
)
#: years of the report (base year and PatEx 5-year steps), horizons are added
REPORT_YEARS = [2021, 2025, 2030, 2035, 2040, 2045, 2050]

#: target in extraction_rules.csv → output file stem
TARGET_FILES = {
    "energy_totals": "patex_energy_totals",
    "industry": "patex_industry",
    "parameters": "patex_parameters",
    "supply": "patex_supply",
}

#: PyPSA-Eur columns with no PatEx counterpart, set to 0 so PyPSA's own value
#: is not added on top of the PatEx one: PatEx `solid-ff-coal` includes coke, and
#: PatEx makes ammonia and methanol from the carriers already exported (hydrogen,
#: methane, ...), where PyPSA-Eur asks the network for the product itself.
ZERO_COLUMNS = {
    "industry": ["coke", "methanol"],
    # fuels PyPSA-Eur can import that PatEx never imports: cap 0
    "supply": ["methanol", "NH3"],
}

#: NH3 energy per tonne (LHV), PyPSA-Eur's ``industry.MWh_NH3_per_tNH3``: PatEx's ammonia
#: production becomes an NH3 demand, PyPSA-Eur optimises the route (2026-11-12).
MWH_NH3_PER_T = 5.166
#: routes taken out of the industry carriers (target ``routes`` of the long table:
#: ``<product>|<industry column>`` energy / CO2 and ``<product> production`` [kt])
ROUTE_PRODUCTS = {"ammonia": MWH_NH3_PER_T}

#: building heat columns (final energy incl. district heat, without ambient heat: the
#: base of the PyPSA-Eur heat totals); the district heat share is taken on their useful
#: heat (× PatEx efficiency, audit #4) when the efficiencies are known
HEAT_COLUMNS = [
    "total residential space",
    "total residential water",
    "total services space",
    "total services water",
]


def default_mappings_dir() -> Path:
    """Canonical mapping tables shipped with the repository (``data/``)."""
    return Path(__file__).resolve().parent.parent / "data"


def load_country_map(mappings_dir: Path) -> dict[str, str]:
    df = pd.read_csv(mappings_dir / COUNTRIES_FILE, dtype=str)
    return dict(zip(df["patex"], df["pypsa"]))


def horizon_tables(
    long: pd.DataFrame,
    horizon: int,
    waste_factor: pd.Series | None = None,
    heat_efficiency: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """``{target: country × category}`` wide tables for one planning horizon.

    ``waste_factor`` (country → MtCO2/TWh) turns the industry ``solid waste`` energy,
    which PyPSA-Eur has no carrier for, into CO2 added to ``process emission``.
    ``heat_efficiency`` (country × ``total {sector} {use} efficiency``, PatEx useful /
    final heat, ``heat.heating_efficiencies``) goes to the parameters, and the district
    heat share is then taken on the useful heat, the base PyPSA-Eur applies it to
    (audit #4); without it, on the final heat.
    """
    available = sorted(long["year"].unique())
    if horizon not in available:
        # PatEx reports 5-year steps from 2025: never interpolate silently.
        raise ValueError(f"horizon {horizon} not in PatEx years {available}")
    sel = long[long["year"] == horizon]
    out = {}
    for target in TARGET_FILES:
        wide = sel[sel["target"] == target].pivot_table(
            index="country", columns="category", values="value", aggfunc="sum"
        )
        wide.columns.name = None
        for column in ZERO_COLUMNS.get(target, []):
            wide[column] = 0.0
        out[target] = wide.sort_index()

    industry = out["industry"]
    routes = sel[sel["target"] == "routes"].pivot_table(
        index="country", columns="category", values="value", aggfunc="sum"
    )
    for product, mwh_per_t in ROUTE_PRODUCTS.items():
        # PatEx production [kt] x MWh/t / 1e3 = TWh of the product (PyPSA-Eur load)
        column = f"{product} production"
        industry[product] = (
            routes[column].reindex(industry.index).fillna(0.0) * mwh_per_t / 1e3
            if column in routes
            else 0.0
        )
    if "solid waste" in industry:
        if waste_factor is None:
            raise ValueError("industry solid waste needs the PatEx CO2 factors (--dataset)")
        waste_co2 = industry.pop("solid waste") * waste_factor.reindex(industry.index)
        if waste_co2.isna().any():
            raise ValueError(f"no solid-waste CO2 factor for {list(waste_co2.index[waste_co2.isna()])}")
        industry["process emission"] = industry.get("process emission", 0.0) + waste_co2

    parameters = out["parameters"]
    if heat_efficiency is not None or "district heat" in parameters:
        heat_totals = out["energy_totals"][HEAT_COLUMNS]
        if heat_efficiency is not None:
            eff = heat_efficiency.reindex(heat_totals.index)
            if eff.isna().any().any():
                raise ValueError(
                    f"no heating efficiencies for {list(eff.index[eff.isna().any(axis=1)])}"
                )
            for column in HEAT_COLUMNS:
                parameters[f"{column} efficiency"] = eff[f"{column} efficiency"]
            heat = sum(heat_totals[c] * eff[f"{c} efficiency"] for c in HEAT_COLUMNS)
        else:
            heat = heat_totals.sum(axis=1)
        if "district heat" in parameters:
            parameters["district heat share"] = parameters.pop("district heat") / heat
    if "district heat losses" in parameters:
        # PatEx network-losses[%]: losses / heat delivered (0 without heat networks)
        delivered = parameters.pop("district heat delivered")
        losses = parameters.pop("district heat losses")
        parameters["district heating loss"] = (losses / delivered.where(delivered > 0)).fillna(0.0)
    return out


#: (target, category) set to 0 where PatEx is negative instead of failing: PatEx
#: books a CO2 deficit (CO2 use above capture + DAC) as negative storage, and a
#: country cannot take CO2 back out of the ground (T32).
CLIP_AT_ZERO = {("parameters", "co2 stored")}


#: PatEx totals the industry extraction must preserve: energy over all carriers and
#: process emissions, each = industry columns + routes (``check_industry_balance``)
INDUSTRY_TOTALS = {
    "energy": "ind_energy-demand-by-carrier-feedstock[TWh]",
    "process": "ind_emissions-by-material-by-type[MtCO2e]",
}
PROCESS_COLUMNS = ["process emission", "process emission from feedstock"]


def check_industry_balance(
    long: pd.DataFrame, tables: dict[str, pd.DataFrame], country_map=None, rtol=1e-6
) -> None:
    """Raise if industry columns + routes differ from PatEx's industry totals, per
    country and year: energy (all carriers) and process emissions. Guards the ammonia
    route against being lost or counted twice."""
    ind = long[long["target"].isin(["industry", "routes"])]
    is_process = ind["category"].str.split("|").str[-1].isin(PROCESS_COLUMNS)
    is_prod = ind["category"].str.endswith(" production")
    sums = {
        "energy": ind[~is_process & ~is_prod].groupby(["country", "year"])["value"].sum(),
        "process": ind[is_process].groupby(["country", "year"])["value"].sum(),
    }
    for kind, variable in INDUSTRY_TOTALS.items():
        if variable not in tables:
            continue
        t = tables[variable]
        if kind == "process":
            t = t[t["emission-type"] == "process"]
        ref = t.groupby(["Country", "Years"])[variable].sum()
        ref.index = ref.index.set_names(["country", "year"])
        if country_map:
            ref = ref.rename(index=country_map, level="country")
        ref.index = ref.index.set_levels(ref.index.levels[1].astype(int), level="year")
        got = sums[kind].reindex(ref.index).fillna(0.0)
        bad = (got - ref).abs() > rtol * ref.abs().clip(lower=1.0)
        if bad.any():
            raise ValueError(
                f"industry {kind} balance broken (extraction rules) for "
                f"{sorted(set(ref.index[bad].get_level_values(0)))[:5]}…"
            )


def clip_at_zero(long: pd.DataFrame) -> pd.DataFrame:
    """Negative values of the ``CLIP_AT_ZERO`` categories set to 0 (logged)."""
    keys = pd.MultiIndex.from_frame(long[["target", "category"]])
    neg = keys.isin(list(CLIP_AT_ZERO)) & (long["value"] < 0)
    if neg.any():
        logger.warning(
            f"{int(neg.sum())} negative values set to 0 "
            f"({', '.join(c for _, c in sorted(CLIP_AT_ZERO))}):\n"
            f"{long.loc[neg, ['category', 'country', 'year', 'value']].to_string()}"
        )
        long = long.copy()
        long.loc[neg, "value"] = 0.0
    return long


def check_values(long: pd.DataFrame, allow_negative: bool = False) -> None:
    if not long["value"].notna().all():
        raise ValueError(f"non-finite demands:\n{long[long['value'].isna()].head(20)}")
    bad = long[long["value"] < -1e-6]
    if bad.empty:
        return
    msg = f"{len(bad)} negative demands:\n{bad.head(20)}"
    if not allow_negative:
        raise ValueError(msg)
    logger.warning(msg)


def export_coupling_dir(
    coupling_dir: str | Path,
    patex_pkl: str | Path,
    horizons: list[int],
    mappings_dir: str | Path | None = None,
    scenario_id: str | None = None,
    strict: bool = False,
    allow_negative: bool = False,
    co2_factors: pd.DataFrame | None = None,
    dataset: str | None = None,
    heat_technologies: pd.DataFrame | None = None,
    levers_default: float | None = None,
    levers_file: str | Path | None = None,
) -> Path:
    """Write ``<coupling_dir>/pypsa_inputs`` for ``horizons``.

    The CO2 factors are PatEx dataset inputs, not in the run pickle: pass them as
    ``co2_factors`` (``emissions.load_co2_factors``) or give the ``dataset`` to read
    them from (PatEx environment). Without either, no CO2 intensity file is written
    and industry solid waste fails.

    The heating efficiencies and technology mix (audit #4) are dataset inputs too, and
    depend on the levers: pass ``heat_technologies`` (``heat.load_heat_technologies``)
    or the ``dataset`` with the levers of the PatEx run (``levers_default`` and / or
    ``levers_file``, as for ``patex run``). Without them, no heating efficiencies are
    written and the district heat share stays on the final-energy base.
    """
    coupling_dir = Path(coupling_dir)
    mappings_dir = Path(mappings_dir) if mappings_dir else default_mappings_dir()
    out_dir = coupling_dir / "pypsa_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Freeze the mappings used for this run next to its outputs.
    frozen = coupling_dir / "mappings"
    frozen.mkdir(exist_ok=True)
    for name in MAPPING_FILES:
        if (mappings_dir / name).resolve() != (frozen / name).resolve():
            shutil.copy2(mappings_dir / name, frozen / name)

    tables = load_patex_tables(patex_pkl)
    rules = load_rules(mappings_dir / RULES_FILE)
    country_map = load_country_map(mappings_dir)
    long = extract(tables, rules, country_map)
    check_industry_balance(long, tables, country_map)
    # Agriculture is extracted by carrier group, then split into PyPSA-Eur uses.
    shares = pd.read_csv(mappings_dir / AGRICULTURE_SHARES_FILE)
    long = pd.concat([long, split_agriculture(long, shares)], ignore_index=True)
    long = clip_at_zero(long)
    check_values(long, allow_negative)
    long.to_csv(out_dir / "patex_demands_long.csv", index=False)

    # report data: every TWh of PatEx demand on its way to PyPSA-Eur, and PatEx indicators
    report_years = sorted(set(REPORT_YEARS) | set(horizons))
    flows = sankey_flows(
        tables,
        load_flow_rules(mappings_dir / SANKEY_FLOWS_FILE),
        rules,
        shares,
        country_map,
    )
    flows[flows["year"].isin(report_years)].to_csv(
        out_dir / "sankey_flows.csv", index=False, float_format="%.6f"
    )
    indicator_series(
        tables, load_definitions(mappings_dir / INDICATORS_FILE), report_years, country_map
    ).to_csv(out_dir / "patex_indicators.csv", index=False, float_format="%.6f")

    gaps = coverage(tables, rules)
    gaps.to_csv(out_dir / "coverage.csv", index=False)
    if not gaps.empty:
        msg = f"{len(gaps)} PatEx slices picked by no rule, see {out_dir / 'coverage.csv'}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)

    patex_countries = sorted(tables[rules[0].variable]["Country"].unique())
    if co2_factors is None and dataset:
        from .emissions import load_co2_factors

        co2_factors = load_co2_factors(dataset, patex_countries)
    if heat_technologies is None and dataset:
        if levers_default is None and levers_file is None:
            raise ValueError(
                "the PatEx heating efficiencies depend on the levers: give the levers of "
                "the PatEx run (--levers-default and / or --levers-file)"
            )
        from .heat import load_heat_technologies

        heat_technologies = load_heat_technologies(
            dataset,
            patex_countries,
            1.0 if levers_default is None else levers_default,  # patex run's default
            levers_file,
        )
    if heat_technologies is not None:
        heat_technologies.to_csv(
            out_dir / "patex_heat_technologies.csv", index=False, float_format="%.6f"
        )
    else:
        logger.warning("no PatEx heating efficiencies: district heat share on final energy")
    waste_factor = None
    if co2_factors is not None:
        co2_factors.to_csv(out_dir / "patex_co2_factors.csv", index=False, float_format="%.6f")
        waste_factor = industry_factor(co2_factors, "solid-waste").rename(country_map)
        energy = fossil_energy(tables)

    for h in horizons:
        if co2_factors is not None:
            intensity = co2_intensity(energy, co2_factors, h)
            intensity["oil refining"] = refinery_co2_intensity(tables, h)
            intensity.to_csv(out_dir / f"patex_co2_intensity_{h}.csv", float_format="%.6f")
        heat_eff = None
        if heat_technologies is not None:
            # PatEx useful / final heat per country (audit #4); the final heat must be
            # the bundle's heat columns
            final, useful = useful_heat(tables, heat_technologies, h)
            final, useful = final.rename(index=country_map), useful.rename(index=country_map)
            bundle = horizon_tables(long, h, waste_factor)["energy_totals"][HEAT_COLUMNS]
            gap = (final - bundle.reindex(final.index)).abs().max().max()
            if not gap < 1e-4:
                raise ValueError(f"PatEx final heat ≠ bundle heat columns in {h} (max {gap} TWh)")
            heat_eff = heating_efficiencies(final, useful)
        wides = horizon_tables(long, h, waste_factor, heat_eff)
        if co2_factors is not None:
            # non-renewable waste burned in power and heat plants (audit #2)
            wte = waste_to_energy(tables, co2_factors, h).rename(index=country_map)
            par = wides["parameters"]
            par["waste to energy fuel"] = wte["fuel"].reindex(par.index).fillna(0.0)
            par["waste to energy co2"] = wte["co2"].reindex(par.index).fillna(0.0)
        for target, wide in wides.items():
            wide.to_csv(out_dir / f"{TARGET_FILES[target]}_{h}.csv", float_format="%.6f")

    manifest = {
        "patex_pypsa_version": __version__,
        "scenario_id": scenario_id or Path(patex_pkl).stem,
        "patex_run": str(Path(patex_pkl).resolve()),
        "patex_run_sha256": sha256(patex_pkl),
        "rules_sha256": sha256(mappings_dir / RULES_FILE),
        "agriculture_shares_sha256": sha256(mappings_dir / AGRICULTURE_SHARES_FILE),
        "countries": sorted(long["country"].unique()),
        "horizons": horizons,
        "units": "TWh/a; process emissions MtCO2e/a; number bev / phev; district heat share, district heating loss [-]; co2 stored MtCO2/a; waste to energy fuel TWh/a, co2 MtCO2/a; heating efficiencies [-] (useful / final)",
        "co2_factors": dataset or ("given" if co2_factors is not None else None),
        "heating_efficiencies": (
            {"dataset": dataset, "levers_default": levers_default,
             "levers_file": str(levers_file) if levers_file else None}
            if dataset and heat_technologies is not None
            else ("given" if heat_technologies is not None else None)
        ),
        "uncovered_slices": len(gaps),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.info("wrote coupling bundle %s", out_dir)
    return out_dir
