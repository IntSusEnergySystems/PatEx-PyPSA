"""Check that a composed PyPSA-Eur network holds the PatEx demands (plan step 6).

    python scripts/check_network_ledger.py <composed_{h}.nc> <coupling_dir> --horizon 2030 \
        [--heating-efficiencies resources/<run>/heating_efficiencies.csv --year 2023]

Run in the pixi env of PyPSA-Eur (needs pypsa). For each PatEx country of the network,
compares the annual exogenous loads [TWh/a, process emissions MtCO2/a] with the bundle.
Loads that PyPSA-Eur aggregates at EU level (``regional_oil_demand: false``) are
compared with the sum over the PatEx countries of the network. ``ratio`` should be 1
except where noted. Then: CO2 intensities of the fuel links, EV fleet (charger
capacity / charge rate), district heating share of the building heat loads and district
heating loss rate.
"""

import argparse
import re
from pathlib import Path

import pandas as pd
import pypsa

LAND_ICE = (
    "total road + total rail - electricity rail - hydrogen rail"
    " - electricity road - hydrogen road - gas road"
)
NAVIGATION = "total domestic navigation + total international navigation"

# PyPSA-Eur load carrier(s) -> (bundle, PatEx expression, note)
CHECKS = {
    "base load": (["electricity"], "energy_totals", "electricity base load", ""),
    "agriculture electricity": (
        ["agriculture electricity"],
        "energy_totals",
        "total agriculture electricity",
        "",
    ),
    "agriculture heat": (["agriculture heat"], "energy_totals", "total agriculture heat", ""),
    "agriculture machinery": (
        ["agriculture machinery oil"],
        "energy_totals",
        "total agriculture machinery",
        "oil share 1",
    ),
    "land transport EV": (["land transport EV"], "energy_totals", "electricity road", ""),
    "land transport fuel cell": (
        ["land transport fuel cell"],
        "energy_totals",
        "hydrogen road",
        "",
    ),
    "land transport oil": (["land transport oil"], "energy_totals", LAND_ICE, ""),
    "land transport gas": (["land transport gas"], "energy_totals", "gas road", ""),
    "rail electricity": (["rail electricity"], "energy_totals", "electricity rail", ""),
    "rail hydrogen": (["H2 for rail"], "energy_totals", "hydrogen rail", ""),
    "aviation electricity": (
        ["aviation electricity"],
        "energy_totals",
        "electricity aviation",
        "",
    ),
    "aviation": (
        ["kerosene for aviation"],
        "energy_totals",
        "total domestic aviation + total international aviation",
        "",
    ),
    "shipping oil": (
        ["shipping oil"],
        "energy_totals",
        f"{NAVIGATION} - hydrogen navigation",
        "PatEx has no methanol ships",
    ),
    "shipping hydrogen": (["H2 for shipping"], "energy_totals", "hydrogen navigation", ""),
    "shipping electricity": (
        ["shipping electricity"],
        "energy_totals",
        "electricity navigation",
        "",
    ),
    "cooking gas": (["gas for cooking"], "energy_totals", "gas cooking", "flat"),
    "cooking oil": (["oil for cooking"], "energy_totals", "oil cooking", "flat"),
    "cooking solid biomass": (
        ["solid biomass for cooking"],
        "energy_totals",
        "solid biomass cooking",
        "flat",
    ),
    "cooking coal": (["coal for cooking"], "energy_totals", "coal cooking", "flat"),
    "cooking hydrogen": (["H2 for cooking"], "energy_totals", "hydrogen cooking", "flat"),
    "industry electricity": (["industry electricity"], "industry", "electricity", ""),
    "industry hydrogen": (["H2 for industry"], "industry", "hydrogen", ""),
    "industry methane": (["gas for industry"], "industry", "methane", ""),
    "industry feedstock methane": (
        ["gas feedstock for industry"],
        "industry",
        "methane feedstock",
        "no CO2",
    ),
    "process emissions": (
        ["process emissions"],
        "industry",
        "process emission",
        "MtCO2/a, incl. solid waste CO2",
    ),
    "industry oil": (["oil for industry"], "industry", "oil for industry", "burnt, with CO2"),
    "industry solid biomass": (["solid biomass for industry"], "industry", "solid biomass", ""),
    "industry coal": (["coal for industry"], "industry", "coal + coke", ""),
    "industry low-temperature heat": (
        ["low-temperature heat for industry"],
        "industry",
        "low-temperature heat",
        "",
    ),
    "industry naphtha": (
        ["naphtha for industry"],
        "industry",
        "naphtha",
        "PyPSA-Eur adjusts naphtha for plastics recycling / HVC",
    ),
}


def annual_loads(n: pypsa.Network) -> pd.DataFrame:
    """carrier × location annual load [TWh/a]."""
    weights = n.snapshot_weightings.generators
    p = n.get_switchable_as_dense("Load", "p_set").multiply(weights, axis=0).sum()
    nyears = weights.sum() / 8760
    loads = n.loads.assign(energy=p / nyears / 1e6)
    location = loads.bus.map(n.buses.location).where(lambda s: s.fillna("") != "", loads.bus)
    loads["country"] = location.str[:2]
    return loads.groupby(["carrier", "country"]).energy.sum().unstack(fill_value=0.0)


def signed_sum(frame: pd.DataFrame, expression: str) -> pd.Series:
    """``"a + b - c"`` over columns whose names contain spaces."""
    total, sign = 0.0, 1
    for term in re.split(r" ([+-]) ", expression):
        if term in "+-":
            sign = 1 if term == "+" else -1
        else:
            total = total + sign * frame[term]
    return total


def building_heat(patex: pd.DataFrame, efficiencies: pd.DataFrame) -> pd.Series:
    """Useful heat PyPSA-Eur should put on the building heat buses [TWh/a]."""
    total = 0.0
    for sector in ("residential", "services"):
        for use in ("space", "water"):
            eff = efficiencies[f"total {sector} {use} efficiency"].reindex(patex.index)
            total = total + patex[f"total {sector} {use}"] * eff
    return total


p = argparse.ArgumentParser()
p.add_argument("network", type=Path)
p.add_argument("coupling_dir", type=Path)
p.add_argument("--horizon", type=int, required=True)
p.add_argument("--heating-efficiencies", type=Path)
p.add_argument("--year", type=int, default=2023, help="energy_totals_year")
p.add_argument("--bev-charge-rate", type=float, default=0.011, help="sector.bev_charge_rate [MW]")
args = p.parse_args()

inputs = args.coupling_dir / "pypsa_inputs"
bundles = {
    "energy_totals": pd.read_csv(inputs / f"patex_energy_totals_{args.horizon}.csv", index_col=0),
    "industry": pd.read_csv(inputs / f"patex_industry_{args.horizon}.csv", index_col=0),
    "parameters": pd.read_csv(inputs / f"patex_parameters_{args.horizon}.csv", index_col=0),
}
n = pypsa.Network(args.network)
loads = annual_loads(n)
countries = sorted(set(loads.columns) & set(bundles["energy_totals"].index))

rows = []
for name, (carriers, bundle, expression, note) in CHECKS.items():
    present = [c for c in carriers if c in loads.index]
    if not present:
        continue
    network = loads.loc[present].sum()
    if name == "process emissions":  # a negative load on the process emissions bus
        network = -network
    patex = signed_sum(bundles[bundle], expression)
    eu_level = network.drop(countries, errors="ignore").sum() > 0
    if eu_level:  # aggregated at EU level: compare the sums
        rows.append((name, "EU", network.sum(), patex.reindex(countries).sum(), note))
    else:
        for ct in countries:
            rows.append((name, ct, network.get(ct, 0.0), patex.get(ct, 0.0), note))

heat = [c for c in loads.index if c.endswith(" heat") and not c.startswith("agriculture")]
if args.heating_efficiencies and heat:
    efficiencies = pd.read_csv(args.heating_efficiencies, index_col=[1, 0]).loc[args.year]
    expected = building_heat(bundles["energy_totals"], efficiencies)
    network = loads.loc[heat].sum()
    for ct in countries:
        rows.append(("building heat (useful)", ct, network.get(ct, 0.0), expected.get(ct), ""))

# CO2 released by the naphtha link (steam cracker share of the naphtha carbon)
naphtha = n.links.index[n.links.carrier == "naphtha for industry"]
if len(naphtha) and "naphtha for industry" in loads.index:
    feedstock_co2 = (n.links.loc[naphtha, "efficiency2"].mean() * loads.loc["naphtha for industry"]).sum()
    rows.append(
        (
            "process emission from feedstock",
            "EU",
            feedstock_co2,
            bundles["industry"]["process emission from feedstock"].reindex(countries).sum(),
            "MtCO2/a, via the naphtha link",
        )
    )

# EV fleet
chargers = n.links[n.links.carrier == "BEV charger"]
if len(chargers):
    fleet = (chargers.p_nom / args.bev_charge_rate).groupby(chargers.bus0.str[:2]).sum()
    for ct in countries:
        rows.append(
            ("number EVs [M]", ct, fleet.get(ct, 0.0) / 1e6,
             bundles["parameters"]["number evs"].get(ct, 0.0) / 1e6, "")
        )

# district heating share of the building heat loads (useful heat, PatEx: final)
central = [c for c in heat if c.startswith("urban central")]
if heat and central:
    share = loads.loc[central].sum() / loads.loc[heat].sum()
    for ct in countries:
        rows.append(
            ("district heat share", ct, share.get(ct, 0.0),
             bundles["parameters"]["district heat share"].get(ct), "network, losses in their own load")
        )

# district heating losses: PatEx rate × heat delivered on the urban central buses
if "urban central heat losses" in loads.index:
    weights = n.snapshot_weightings.generators
    nyears = weights.sum() / 8760
    on_central = n.loads[
        n.loads.bus.str.endswith(" urban central heat")
        & n.loads.carrier.isin(["urban central heat", "low-temperature heat for industry"])
    ]
    delivered = (
        n.get_switchable_as_dense("Load", "p_set")[on_central.index]
        .multiply(weights, axis=0)
        .sum()
        .groupby(on_central.bus.map(n.buses.location).str[:2])
        .sum()
        / nyears
        / 1e6
    )
    rate = loads.loc["urban central heat losses"] / delivered.where(delivered > 0)
    for ct in countries:
        rows.append(
            ("district heating loss [-]", ct, rate.get(ct, 0.0),
             bundles["parameters"]["district heating loss"].get(ct), "losses / heat on urban central buses")
        )

table = pd.DataFrame(rows, columns=["check", "country", "network", "patex", "note"])
table["ratio"] = table.network / table.patex.where(table.patex != 0)
pd.set_option("display.width", 200, "display.max_colwidth", 60)
print(f"{args.network} vs {inputs} ({args.horizon}), TWh/a")
print(table.round({"network": 3, "patex": 3, "ratio": 4}).to_string(index=False))

# CO2 intensity of the links burning each fuel
co2 = pd.read_csv(inputs / f"patex_co2_intensity_{args.horizon}.csv", index_col=0)["CO2 intensity"]
fuel_links = {
    "gas": ["gas for industry", "land transport gas", "gas for cooking"],
    "oil": ["oil for industry", "land transport oil", "oil for cooking"],
    "coal": ["coal for industry", "coal for cooking"],
    "oil refining": ["oil refining"],
}
print("\nCO2 intensity [tCO2/MWh]: carrier, link checked, network, PatEx")
for carrier, links in fuel_links.items():
    for link in links:
        eff = n.links.loc[n.links.carrier == link, "efficiency2"]
        if len(eff) and carrier in co2:
            print(f"  {carrier:12s} {link:20s} {eff.mean():.6f} {co2[carrier]:.6f}")
