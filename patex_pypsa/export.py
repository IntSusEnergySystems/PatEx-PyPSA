"""Write the PatEx → PyPSA-Eur coupling bundle.

Layout (mirrors TIMES_PyPSA's ``<coupling_dir>``)::

    <coupling_dir>/
    ├── patex/run.pkl                      # output of `patex run ... -o`
    ├── mappings/                          # copy of the rules used (frozen per run)
    └── pypsa_inputs/
        ├── patex_energy_totals_{h}.csv    # country × energy_totals columns [TWh/a]
        ├── patex_industry_{h}.csv         # country × industrial demand columns [TWh/a, MtCO2/a]
        ├── patex_parameters_{h}.csv       # country × district heat share [-], district heating loss [-], number evs
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
)
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
}

#: PyPSA-Eur columns with no PatEx counterpart, set to 0 so PyPSA's own value
#: is not added on top of the PatEx one: PatEx `solid-ff-coal` includes coke, and
#: PatEx makes ammonia and methanol from the carriers already exported (hydrogen,
#: methane, ...), where PyPSA-Eur asks the network for the product itself.
ZERO_COLUMNS = {
    "industry": ["coke", "ammonia", "methanol"],
}

#: building heat columns the district heat share is taken on (final energy incl.
#: district heat, without ambient heat: the base of the PyPSA-Eur heat totals)
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
    long: pd.DataFrame, horizon: int, waste_factor: pd.Series | None = None
) -> dict[str, pd.DataFrame]:
    """``{target: country × category}`` wide tables for one planning horizon.

    ``waste_factor`` (country → MtCO2/TWh) turns the industry ``solid waste`` energy,
    which PyPSA-Eur has no carrier for, into CO2 added to ``process emission``.
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
    if "solid waste" in industry:
        if waste_factor is None:
            raise ValueError("industry solid waste needs the PatEx CO2 factors (--dataset)")
        waste_co2 = industry.pop("solid waste") * waste_factor.reindex(industry.index)
        if waste_co2.isna().any():
            raise ValueError(f"no solid-waste CO2 factor for {list(waste_co2.index[waste_co2.isna()])}")
        industry["process emission"] = industry.get("process emission", 0.0) + waste_co2

    parameters = out["parameters"]
    if "district heat" in parameters:
        heat = out["energy_totals"][HEAT_COLUMNS].sum(axis=1)
        parameters["district heat share"] = parameters.pop("district heat") / heat
    if "district heat losses" in parameters:
        # PatEx network-losses[%]: losses / heat delivered (0 without heat networks)
        delivered = parameters.pop("district heat delivered")
        losses = parameters.pop("district heat losses")
        parameters["district heating loss"] = (losses / delivered.where(delivered > 0)).fillna(0.0)
    return out


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
) -> Path:
    """Write ``<coupling_dir>/pypsa_inputs`` for ``horizons``.

    The CO2 factors are PatEx dataset inputs, not in the run pickle: pass them as
    ``co2_factors`` (``emissions.load_co2_factors``) or give the ``dataset`` to read
    them from (PatEx environment). Without either, no CO2 intensity file is written
    and industry solid waste fails.
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
    # Agriculture is extracted by carrier group, then split into PyPSA-Eur uses.
    shares = pd.read_csv(mappings_dir / AGRICULTURE_SHARES_FILE)
    long = pd.concat([long, split_agriculture(long, shares)], ignore_index=True)
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

    if co2_factors is None and dataset:
        from .emissions import load_co2_factors

        co2_factors = load_co2_factors(dataset, sorted(tables[rules[0].variable]["Country"].unique()))
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
        for target, wide in horizon_tables(long, h, waste_factor).items():
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
        "units": "TWh/a; process emissions MtCO2e/a; number evs; district heat share, district heating loss [-]",
        "co2_factors": dataset or ("given" if co2_factors is not None else None),
        "uncovered_slices": len(gaps),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.info("wrote coupling bundle %s", out_dir)
    return out_dir
