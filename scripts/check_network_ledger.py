"""Check that a composed PyPSA-Eur network holds the PatEx demands (plan step 6).

    python scripts/check_network_ledger.py <composed_{h}.nc> <coupling_dir> --horizon 2030 \
        [--heating-efficiencies resources/<run>/heating_efficiencies.csv --year 2023]

Run in the pixi env of PyPSA-Eur (needs pypsa). For each PatEx country of the network,
compares the annual exogenous loads [TWh/a, process emissions MtCO2/a] with the bundle.
Loads that PyPSA-Eur aggregates at EU level (``regional_oil_demand: false``) are
compared with the sum over the PatEx countries of the network. ``ratio`` should be 1
except where noted. Then: CO2 intensities of the fuel links, EV fleet (charger
capacity / charge rate), district heating share of the building heat loads, district
heat [TWh] against PatEx's (audit #4) and district heating loss rate. Building heat is
useful heat: bundle final heat × PatEx's efficiencies (``total ... efficiency`` in the
parameters) for the PatEx countries, × ``--heating-efficiencies`` (PyPSA-Eur) otherwise.
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
    "electric cooling": (
        ["electricity cooling"],
        "energy_totals",
        "electricity residential space cooling + electricity services space cooling",
        "own load, patex.cooling (audit #5b)",
    ),
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
    "industry ammonia": (["NH3"], "industry", "ammonia", "NH3 demand, route optimised"),
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


def building_heat(
    patex: pd.DataFrame, efficiencies: pd.DataFrame | None, parameters: pd.DataFrame
) -> pd.Series:
    """Useful heat PyPSA-Eur should put on the building heat buses [TWh/a]: PatEx's
    efficiencies where the bundle has them (audit #4), PyPSA-Eur's otherwise."""
    total = 0.0
    for sector in ("residential", "services"):
        for use in ("space", "water"):
            column = f"total {sector} {use} efficiency"
            eff = pd.Series(float("nan"), index=patex.index)
            if efficiencies is not None:
                eff = efficiencies[column].reindex(patex.index)
            if column in parameters:
                eff = parameters[column].reindex(patex.index).fillna(eff)
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

COOLING_COLUMNS = ["electricity residential space cooling", "electricity services space cooling"]
if "electricity cooling" not in loads.index and set(COOLING_COLUMNS) <= set(
    bundles["energy_totals"].columns
):
    # patex.cooling: false: cooling stays in the rescaled base load
    CHECKS["base load"] = (
        ["electricity"], "energy_totals", " + ".join(["electricity base load", *COOLING_COLUMNS]),
        "cooling included (patex.cooling: false)",
    )

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
has_patex_eff = "total residential space efficiency" in bundles["parameters"]
if (args.heating_efficiencies or has_patex_eff) and heat:
    efficiencies = (
        pd.read_csv(args.heating_efficiencies, index_col=[1, 0]).loc[args.year]
        if args.heating_efficiencies
        else None
    )
    expected = building_heat(bundles["energy_totals"], efficiencies, bundles["parameters"])
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

# EV electricity drawn from the grid: the load behind the BEV charger divided by its
# efficiency, plus (ev_flexibility, T16) the inflexible charging load on the grid
meta = getattr(n, "meta", None) or {}
ev_flex = (meta.get("ev_flexibility") or {}).get("enable", False)
chargers = n.links[n.links.carrier == "BEV charger"]
if "land transport EV" in loads.index:
    eta = chargers.efficiency.mean() if len(chargers) else 1.0
    behind = loads.loc["land transport EV"] / (eta if ev_flex else 1.0)
    inflexible = loads.loc["land transport EV inflexible"] if "land transport EV inflexible" in loads.index else 0.0
    network = behind + inflexible
    note = "grid draw (flexible / charger eff. + inflexible)" if ev_flex else "on the EV battery bus"
    for ct in countries:
        rows.append(("land transport EV", ct, network.get(ct, 0.0),
                     bundles["energy_totals"]["electricity road"].get(ct, 0.0), note))

# EV fleet behind the chargers: BEV + phev_fleet_factor × PHEV (× market share, T16)
if len(chargers):
    fleet = (chargers.p_nom / args.bev_charge_rate).groupby(chargers.bus0.str[:2]).sum()
    par = bundles["parameters"]
    factor = (meta.get("patex") or {}).get("phev_fleet_factor", 0.0)
    if "number bev" in par:
        expected = par["number bev"] + factor * par["number phev"]
    else:  # bundle older than T16
        expected = par["number evs"]
    note = ""
    if ev_flex:
        horizon = args.horizon
        shares = {int(k): v for k, v in meta["ev_flexibility"]["market_share"].items()}
        share = shares[max(y for y in shares if y <= horizon)]
        expected = expected * share
        note = f"flexible share {share}"
    for ct in countries:
        rows.append(("number EVs [M]", ct, fleet.get(ct, 0.0) / 1e6,
                     expected.get(ct, 0.0) / 1e6, note))

# district heating share of the building heat loads (useful heat on both sides once the
# bundle has PatEx's efficiencies; before audit #4 PatEx's share was on final energy)
central = [c for c in heat if c.startswith("urban central")]
if heat and central:
    share = loads.loc[central].sum() / loads.loc[heat].sum()
    for ct in countries:
        rows.append(
            ("district heat share", ct, share.get(ct, 0.0),
             bundles["parameters"]["district heat share"].get(ct), "network, losses in their own load")
        )

# district heat [TWh]: building load on the urban central buses vs PatEx's district
# heat (long table, independent of the share; audit #4)
long = pd.read_csv(inputs / "patex_demands_long.csv")
dh = long[
    (long["year"] == args.horizon)
    & (long["target"] == "parameters")
    & (long["category"] == "district heat")
].groupby("country")["value"].sum()
if "urban central heat" in loads.index and not dh.empty:
    for ct in countries:
        rows.append(
            ("district heat", ct, loads.loc["urban central heat"].get(ct, 0.0), dh.get(ct, 0.0),
             "buildings, without losses")
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

# supply caps (import_limits): network cap vs PatEx imports summed over the countries;
# above 1 by the PatEx production that today's production cannot supply (gap, logged
# by compose_network); domestic cap <= PatEx production
supply_file = inputs / f"patex_supply_{args.horizon}.csv"
caps = n.global_constraints[n.global_constraints.type.isin(["import_limit", "domestic_limit"])]
if len(caps) and supply_file.exists():
    supply_all = pd.read_csv(supply_file, index_col=0)
    nyears = n.snapshot_weightings.generators.sum() / 8760
    print("\nSupply caps [TWh/a]: constraint, network cap, PatEx (region: PatEx countries"
          " of the region; GB / NO / other fallback countries: Eurostat, not in PatEx)")
    for name, g in caps.iterrows():
        fuel, _, region = g.carrier_attribute.partition("|")
        region_countries = region.removeprefix("EU:").split(",") if region else countries
        supply = supply_all.reindex([c for c in region_countries if c in supply_all.index]).sum()
        column = fuel if g.type == "import_limit" else f"{fuel} production"
        print(f"  {name:28s} {g.constant / 1e6 / nyears:10.2f} {supply.get(column, float('nan')):10.2f}")

# CO2 sequestration (T32): total cap vs PatEx CO2 stored over the countries; per-country
# caps (co2_storage, IEA projects); solved network: CO2 sequestered per country
nyears = n.snapshot_weightings.generators.sum() / 8760
if "co2_sequestration_limit" in n.global_constraints.index:
    total = -n.global_constraints.at["co2_sequestration_limit", "constant"] / 1e6 / nyears
    stored = bundles["parameters"].get("co2 stored", pd.Series(dtype=float))
    print(f"\nCO2 sequestration cap [Mt/a]: network {total:.3f}, "
          f"PatEx {stored.reindex(countries).sum():.3f}")
seq = n.stores.index[n.stores.carrier == "co2 sequestered"]
caps = n.global_constraints[n.global_constraints.type == "co2_storage_limit"]
if len(caps):
    print("CO2 storage caps per country [Mt/a]: cap, sequestered (solved network)")
    loc = n.stores.loc[seq, "bus"].map(n.buses.location)
    ct = loc.map(n.buses.country).fillna(loc)
    solved = not n.stores_t.e.empty
    for name, g in caps.iterrows():
        used = (n.stores_t.e.iloc[-1].reindex(seq[ct == g.carrier_attribute]).sum() / 1e6 / nyears
                if solved else float("nan"))
        print(f"  {g.carrier_attribute:4s} {g.constant / 1e6 / nyears:10.3f} {used:10.3f}")

# Waste-to-energy (patex.waste_to_energy, audit #2): non-renewable waste the waste CHPs
# must burn (store contents) vs the bundle; solved network: burned and its CO2
wte_stores = n.stores.index[n.stores.carrier == "non-sequestered HVC"]
if "waste to energy fuel" in bundles["parameters"] and len(wte_stores):
    loc = n.stores.loc[wte_stores, "bus"].map(n.buses.location)
    ct = loc.str[:2]
    held = n.stores.loc[wte_stores, "e_initial"].groupby(ct).sum() / 1e6 / nyears
    chp = n.links.index[n.links.carrier.str.startswith("waste CHP")]
    solved = not n.links_t.p0.empty and len(chp)
    if solved:
        w = n.snapshot_weightings.generators
        p0 = n.links_t.p0[chp].multiply(w, axis=0).sum()
        chp_ct = n.links.loc[chp, "bus1"].map(n.buses.location).str[:2]
        burned = p0.groupby(chp_ct).sum() / 1e6 / nyears
        co2 = (p0 * n.links.loc[chp, "efficiency3"]).groupby(chp_ct).sum() / 1e6 / nyears
    par = bundles["parameters"]
    print("\nWaste-to-energy [TWh/a, MtCO2/a]: country, store (must burn), PatEx fuel, "
          "burned, CO2 network, PatEx CO2 (GB / NO: EU trend, not in the bundle)")
    for c in sorted(held.index):
        b = burned.get(c, float("nan")) if solved else float("nan")
        e = co2.get(c, float("nan")) if solved else float("nan")
        print(f"  {c:4s} {held[c]:8.3f} {par['waste to energy fuel'].get(c, float('nan')):8.3f}"
              f" {b:8.3f} {e:8.3f} {par['waste to energy co2'].get(c, float('nan')):8.3f}")
    hvc_air = n.links.index[n.links.carrier == "HVC to air"]
    print(f"  HVC to air links: {len(hvc_air)} (0 expected with patex.waste_to_energy)")

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
