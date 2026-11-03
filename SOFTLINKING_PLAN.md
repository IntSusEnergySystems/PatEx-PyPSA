# PatEx → PyPSA-Eur soft-linking plan

**Status (2026-11-03):** steps 1, 2 (levers = 2 placeholder), 4 and 6 done. The hooks are
applied on `develop` of the fork `IntSusEnergySystems/PyPSA-Eur-CANEU`; what is passed
and changed per model is listed in [MODEL_CHANGES.md](MODEL_CHANGES.md). A BE test run
passes the ledger check.

## 1. What we reuse from TIMES2PYPSA and what changes

| TIMES_PyPSA (Wallonia) | PATEX_PyPSA (EU) | Why |
|---|---|---|
| Library + thin Snakemake wrapper (D1) | same | Keeps model-specific parsing out of PyPSA-Eur |
| Canonical mappings in `data/` (D2) | same: `extraction_rules.csv` | Single source of truth, versioned |
| `<coupling_dir>` + `manifest.json` + `run_coupled.sh` | same | Reproducible, frozen inputs per scenario |
| Separate envs (D4) | PatEx (py3.11, pandas 2.2) and pypsa-eur (pandas 3) exchange CSV | PatEx pins numpy/pandas for parity |
| Input = `.vd` file, PJ, timeslices | Input = `patex run -o` pickle, TWh, annual, 5-year steps | Different model output |
| One node (BEWAL) overwritten | **every country** rescaled, nodal distribution kept (`override_country_totals`) | PatEx is national, multi-country |
| Hard-coded hooks in pypsa-wal scripts | config section `patex:` via PyPSA-Eur `ConfigUpdater`, hooks behind `patex.enable` | Easier to rebase on upstream PyPSA-Eur |
| Sankey/QA pages | `coverage.csv` + `patex_demands_long.csv` (Sankey later if needed: `elc_energy-sankey-detailed`) | Start small |

## 2. Data flow

```
PatEx (uv env)                      PATEX_PyPSA                         PyPSA-Eur (pixi env)
patex run "BE|FR|..."  ── run.pkl ─▶ export-coupling ── pypsa_inputs/ ─▶ build_patex_demands
  levers.json (PAC2)                  rules + checks                      │ resources/patex_*_{h}.csv
                                                                          ▼
                                       build_industrial_energy_demand_per_node  (industry override)
                                       prepare_sector_network.main             (energy totals override,
                                                                               base-load rescale)
                                                                          ▼
                                                               solve → capacities, flexibility,
                                                               gas use, system costs
                                                                          │
                       compare with PatEx supply outputs (elc_*) ◀────────┘
```

## 3. Steps

1. **Set up the soft-link package** — done.
   `patex-pypsa inspect` / `export-coupling`, draft rules, coverage + sign + horizon checks,
   tests in both envs.
2. **Run PatEx on the real dataset** (`47.x.4` on S3, AWS credentials in `~/.aws`).
   One run covers every country PyPSA-Eur models that PatEx has: the EU27 minus CY and
   MT, which PyPSA-Eur does not model (Greece is `EL` in PatEx, mapped to `GR`):

   ```bash
   cd patex
   uv run patex run "AT|BE|BG|CZ|DE|DK|EE|ES|FI|FR|EL|HR|HU|IE|IT|LT|LU|LV|NL|PL|PT|RO|SE|SI|SK" \
       --dataset "s3://climact-dataset/patex/47.x.4?region=eu-central-1" \
       --levers-default 2 -o ../PATEX2PYPSA/runs/levers2/patex/run.pkl
   ```

   `--levers-default 2` is a placeholder scenario. For PAC 2.0, add
   `--levers-file runs/pac2/patex/levers.json` (lever settings to get from Climact).
   **Countries without PatEx data** (checked on 47.x.4: GB, CH, NO and RS are missing,
   so the Balkans are assumed missing too): AL, BA, CH, GB, ME, MK, NO, RS, XK keep the
   demands from PyPSA-Eur's own preprocessing (`energy_totals.csv`, industry). They are
   listed in `patex.fallback_countries`. Any *other* modelled country missing from the
   bundle stops the workflow, so a failed PatEx country cannot silently fall back.
3. **Validate the mapping with Climact** (`data/extraction_rules.csv`, open questions
   below). Compare `patex_energy_totals_2025.csv` with PyPSA-Eur's own
   `energy_totals.csv` for the latest year: the gaps show definition mismatches (final vs
   useful energy, ambient heat, district heat, bunkers).
4. **Apply the PyPSA-Eur hooks** — done on `develop` of PyPSA-Eur-CANEU
   (`pypsa_eur_integration/README.md`): energy totals, base load, industry, plus two hooks
   found while applying them (land transport, international shipping, see below).
5. **Pass the scenario parameters that are not demands**, one at a time, each with an
   explicit meaning:
   - land-transport shares per horizon — done, per node and in driven distance, not as
     the energy ratio `electricity road / total road` (see "Land transport" below),
   - `reduce_space_heat_exogenously: false` (PatEx demand already includes renovation),
   - CO₂ target (EU or national, 2040 net zero), nuclear phase-out, CCS, import limits:
     PyPSA-Eur config, decided with CAN (see "Remarks kick-off").
6. **Test run** on a small setup — done for BE, 2030, one week
   (`config/test/config.patex.yaml`, `scripts/check_network_ledger.py`). To redo on
   several countries once a larger cutout is available.
7. **Full runs and sensitivities**: PAC2 vs variants (renovation rate, direct
   electrification, demand reduction, import levels), outputs: installed capacities,
   flexibility needs, gas use, system costs, grid investments (AC, H₂).
8. **Compare back with PatEx** supply outputs (`elc_net-energy-production-…`,
   `elc_elec-energy-imported`, …) and report differences. Iterating PyPSA results back
   into PatEx (two-way coupling) is out of scope for now.

## 4. Open questions (with Climact / CAN)

- **Q1 Accounting boundary.** PyPSA-Eur heat columns are *final* energy, converted with
  `heating_efficiencies.csv`. Rules use `incl-district-heating − ambient`. To check: is
  that PatEx's final-energy boundary? Should the PatEx efficiencies be used instead?
- **Q2 Non-electric appliances / others** in buildings: closed, PatEx has none (these
  end uses only exist for electricity, checked on `levers2`).
- **Q3 Industry.** Mostly settled (2026-11-03, see "CO2 accounting" below): `ammonia`
  and `methanol` set to 0, feedstock gas apart, process emissions and solid-waste CO2
  from PatEx. Left for Climact: is `naphtha` = all liquids incl. feedstock the right
  reading (PyPSA-Eur emits all naphtha carbon, as process share or at end of life)?
- **Q4 Agriculture split.** Solved with JRC-IDEES base-year shares per country. These
  shares stay fixed over the horizons (PatEx has no use dimension in agriculture).
- **Q5 Navigation.** Where is domestic maritime in PatEx (IWW or bunkers-marine)?
  PyPSA-Eur uses `shipping_demand.csv` (port-based) for international navigation.
- **Q6 Years.** PatEx gives 2025, 2030, … Pick PyPSA horizons among them (no interpolation).
- **Q7 Weather year.** PatEx demands are for an average climate, PyPSA-Eur heat profiles
  depend on the weather year. Only the hourly *shape* is taken from the weather year.
- **Q8 Fallback countries.** The 9 countries in `patex.fallback_countries` keep
  PyPSA-Eur demands for the `energy_totals_year` (2023), which do not change between
  horizons. With `reduce_space_heat_exogenously: false`, which applies to all countries,
  their heat demand stays at today's level up to 2050. Options: keep it like this (it
  is simple and conservative), or apply PyPSA-Eur's reduction to them only (a small
  extra hook). GB and CH weigh the most (interconnections with FR, BE, DE, IT).

> **Figures.** PatEx outputs and Climact dataset values are not public: the numbers
> behind the findings below are kept in `../private_notes/FINDINGS.md` (outside git).
> Only PyPSA-Eur and JRC-IDEES values are quoted here.

### First check on real data (2026-11-02, 25 countries, placeholder levers)

Export clean: no negative demand, `coverage.csv` empty. BE 2021, PatEx vs PyPSA-Eur
`energy_totals.csv`: within 1 % for residential electricity and space heat, services
electricity, road and international navigation. Gaps: domestic aviation (none in PatEx,
1.55 TWh in PyPSA-Eur: definition gap, Q5), international aviation (higher in PatEx, same
issue), the split of residential space vs water heating (see below), services space and
water (a few % lower in PatEx), and agriculture by use (wrong carrier mapping, fixed below).

**Residential hot water: the sources split space and water differently, the totals agree.**
PatEx space + water matches JRC-IDEES (its calibration source); PyPSA-Eur is 2 % higher. PyPSA-Eur overwrites IDEES with Eurostat `nrg_d_hhq`
(`update_residential_from_eurostat`), which puts 11.7 TWh in water against 8.9 in IDEES;
PatEx is in between. Impact on PyPSA: small, both go to the same heat buses; only the
profile differs (flat for water, weather-dependent for space). To ask Climact: which source
is PatEx's water heating calibrated on? Also: the PyPSA-Eur BE value for 2023 (the
default `energy_totals_year`) drops to 6.6 TWh against 11.9 in 2022, which matters for the
fallback countries.

**Agriculture: the totals per carrier agree, the mapping from carrier to use was wrong (fixed).**
PyPSA-Eur needs agriculture by *use*, because it optimises how each use is supplied:
`electricity` is a fixed load, `heat` sits on the rural heat bus (any heat technology) and
`machinery` is an oil load, partly electrified through `agriculture_machinery_*_share`.
Each carrier serves several uses (JRC-IDEES BE 2021: diesel is 1.12 TWh of heat and 2.49
of machinery; electricity is 0.28 heat, 0.26 motor drives and 1.19 other uses).

Now: the `agriculture` rules extract PatEx by carrier group, and
`patex_pypsa/agriculture.py` splits each group with the country's JRC-IDEES 2021 shares
(`data/agriculture_use_shares.csv`, rebuilt by `patex-pypsa build-agriculture-shares`, with
EU27 as fallback). PatEx `gasoline` is grouped with fuel oil: it matches IDEES "Fuel oil
and other liquids" exactly, which IDEES uses for heat only.

Machinery electrification: PatEx has no lever for it (the agriculture fuel mix is
historical then held constant; only irrigation electricity and fossil → bio switches
change). Electric machinery (IDEES motor drives, per country) is therefore exported
inside `total agriculture electricity`, `total agriculture machinery` holds liquid fuels
only, and the config sets `agriculture_machinery_electric_share: 0` and `oil_share: 1`.
The share PatEx implies, in PyPSA terms, is far below PyPSA-Eur's default of 50 %.

Check (`scripts/check_agriculture_split.py`, 25 countries, 2021): the split conserves
PatEx's total. Against IDEES by use, electricity and machinery agree; heat is lower. Every
remaining gap comes from carriers PatEx has no base-year value for: **farm bioenergy**
(solid biomass, biogas and biodiesel in agriculture). Consistent with PatEx's spec:
agriculture energy is calibrated on 6 fossil/electric carriers, and bio carriers only
appear through the fuel switch. → **Q9 for Climact**: is farm bioenergy intentionally out
of PatEx agriculture (counted elsewhere, e.g. in the bioenergy balance), or missing? If
missing, add the IDEES base-year bio energy, held constant.

### Applying the hooks (2026-11-03): two demands the energy totals do not reach

**Land transport.** `transport_demand.csv` is built once, without horizon, by
`build_transport_demand` from today's energy totals, as a driven distance (final energy /
ICE-based fleet efficiency). EVs, fuel-cell vehicles and ICEs serve it with one EU-wide
share each. So the planned override of `pop_weighted_energy_totals` would have left road
and rail at 2023 levels. Feeding PatEx's electrified energy through the ICE efficiency
would also be wrong: less distance, then less EV electricity, i.e. the EV efficiency gain
counted twice. The planned share `electricity road / total road` is an energy ratio and
has the same bias (an EV needs ~3.3× less energy per km: 53.2 vs 16.1 (100 km)/MWh).

First version: each PatEx carrier → distance with PyPSA-Eur's own drivetrain efficiency,
shares per node = distance shares. Replaced (2026-11-03) by a direct hook
(`patex_pypsa/transport.py`): the EV, fuel-cell and oil loads keep PyPSA-Eur's hourly
profile (traffic × temperature) and are scaled to PatEx's energy per fuel, so no
distance or vehicle efficiency enters the totals. The EV fleet that sizes chargers,
smart charging and V2G comes from PatEx (`number evs` = cars and vans BEV + PHEV); PyPSA-Eur's
share × today's cars gives a quite different fleet. New export column `hydrogen road`. Gas
road vehicles stay in the ICE part and are served as oil: PyPSA-Eur has no gas vehicles.
`tra_final-transport-demand-total[vkm]` exists in PatEx but is not needed: the energy is
what the power system sees.

**International shipping.** `shipping_demand.csv` is also built from the 2023 energy
totals (port-based split). It is now rescaled per country to PatEx `total international
navigation`, keeping the port split.

**YAML pitfall.** `fallback_countries: [..., NO, ...]` reads Norway as `false`. Quoted;
found by `pixi run validate-config`.

### CO2 accounting and the remaining PatEx outputs (2026-11-03)

Decisions (user): PyPSA-Eur keeps its CO2 accounting and decides CCS; PatEx numbers are
used wherever they exist; CO2 factors are computed from PatEx, not written in the config.

**CO2 factors.** PyPSA-Eur uses one CO2 intensity per carrier (gas 0.198, oil 0.2571,
coal 0.3361 tCO2/MWh); PatEx has one factor per sector and fuel (diesel, gasoline,
kerosene, marine fuel oil, ...), a few % higher. The export weights PatEx's factors by
PatEx fossil final energy over the bundle countries, per horizon
(`patex_co2_intensity_{h}.csv`). Bio and synthetic fuels are 0 in PatEx and carbon-neutral
in PyPSA-Eur. Lignite (power only) keeps PyPSA-Eur's value: PatEx has no lignite carrier.

**Process emissions.** PyPSA-Eur derives them from its own industrial production (today's
volumes), so PatEx's activity changes per material would not reach it. Now: PatEx process
emissions, before capture. They are CO2e, with a small non-CO2 share (CH4 of olefins
mostly), kept as is.

**Feedstock gas would have been counted twice.** PatEx counts the CO2 of ammonia and
olefin feedstock gas in its *process* emissions; PyPSA-Eur burns all industry `methane`
with combustion CO2. Feedstock gas is therefore exported apart (`methane feedstock`) and is
a gas load without CO2 in PyPSA-Eur. PatEx olefin process emissions go to `process emission
from feedstock`, which PyPSA-Eur uses to split the naphtha carbon (not extra CO2).

**Ammonia and methanol.** With `industry: ammonia: true`, PyPSA-Eur takes the energy of
ammonia making out of `hydrogen`/`methane` and asks for ammonia as a product instead.
PatEx keeps it in its carriers, so PyPSA-Eur's `ammonia` and `methanol` columns are set to
0. PyPSA-Eur then no longer optimises the ammonia route.

**Solid waste in industry** (cement kilns, ceramics, chemicals, lime, paper): no such fuel
in PyPSA-Eur (its `municipal solid waste` is for waste-to-energy plants). Not supplied by
the network; its CO2 (PatEx factor) is added to the process emissions. PyPSA-Eur's own
data books IDEES "biomass and waste" as biomass; not done here, it would make the waste
carbon-neutral.

**District heating share.** PatEx district heat / building heat (final, without ambient),
consistent with PatEx's `bld_district-heating-share-by-end-use`. Replaces today's share +
progress. To check with Climact: the share falls sharply in some Nordic and Baltic
countries (T17).

**Electric aviation and shipping** go to the base load. Hydrogen rail and gas road stay in
the oil part (T15).

**District heating losses (checked 2026-11-03).** PatEx `bld_district-energy-demand` is
delivered heat (`dh = E × district-heating-share`); network losses are added in the supply
module (`heat_demand = heat + heat × network-losses[%]`, per country) and reported in
`elc_energy-sankey-detailed` (heat → distribution-losses), for buildings and industry heat
together. PyPSA-Eur multiplies the building urban central heat demand by
`1 + district_heating_loss` (0.15) and puts industry low-temperature heat on the same bus
without loss. Same base, no double count; the rates differ (T19).

**Lignite.** PatEx has no lignite carrier (one `elec-plant-with-solid-coal`). PatEx's power
emissions are not passed (PyPSA-Eur computes the power sector itself), but PyPSA-Eur's
lignite plants do count in its CO2 constraint, with 0.407 tCO2/MWh, kept: PatEx has no
lignite value to align with.

**Non-electric cooking is lost (found with the Sankey).** Exported, but PyPSA-Eur has no
load for the cooking columns (T18).

## 5. Pitfalls already handled

| Pitfall | Handling |
|---|---|
| Stacked legacy frames | `split_stacked` keeps each variable's own rows and dimensions |
| Typos in filters → silent 0 | unknown dimension fails, unknown value warns, `coverage.csv` |
| Double counting the electricity load | heat/industry stay explicit components; residual base load rescaled to `electricity base load` at the end |
| Coke counted twice (PatEx coal includes it) | `coke` forced to 0 when industry is soft-linked |
| Missing horizon | export fails, no interpolation |
| Greece EL/GR | `mapping_countries.csv` |
| Land transport and shipping built from 2023 totals | own hooks (`add_land_transport`, `add_shipping`) |
| Feedstock gas CO2 in both PatEx process emissions and PyPSA combustion | `methane feedstock` load without CO2 |
| Ammonia made twice (PatEx carriers + PyPSA `ammonia`) | `ammonia`, `methanol` = 0 |
| Value column holding TWh, Mt and vehicles | `unit` column, a category mixing units fails |
| `NO` read as `false` in YAML | quoted, `validate-config` |
| Reproducibility | rules copied per run, `manifest.json` with checksums |
