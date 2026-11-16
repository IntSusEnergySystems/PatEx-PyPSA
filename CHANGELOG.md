# Changelog

What changed and why, in this repository **and in the linked models** (pypsa-eur fork,
PatEx). One entry per merge into `master`. Details: `git log`.

## pypsa-eur fork (branch `develop`)

Fork: `IntSusEnergySystems/PyPSA-Eur-CANEU`, cloned to `../../PyPSA-Eur-CANEU`.

- 2026-11-16 Merge of `develop` into `master` (both repos, pushed with the user's go):
  audit #1–#5b, cooling load (Hotmaps), temperature shift, GB load to DUKES, cleanup of
  docs and run overlays. Validated by run `...-24h-2023-shift` (2023 weather, 2030 and
  2040; ledger 1 for every PatEx country) and `...-24h-audit` (2013, 2030–2050).
- 2026-11-16 GB measured load scaled to DUKES "electricity available" (`patex.gb_load_dukes`,
  fork `149a9595`, user): upstream fills GB with NESO National Demand, which excludes
  embedded wind and solar (2013 → 2023: −25 % vs −13 % for UK demand); GB is a fallback
  country, so the bias went into its base load. GB's load of each weather year is scaled
  to DUKES 5.1.2 (UK consumption + losses), hourly shape kept.
- 2026-11-16 Climate of the horizon (`patex.temperature_shift`, fork `d42b3a40`, user):
  with one weather year, a growing cooling volume only raised the same peaks. A uniform
  shift per horizon is added to the weather year's outdoor temperature for the heat
  demand profile, the cooling profiles, heat-pump COPs (air, ground) and district
  heating forward temperatures (new rules `build_{daily,hourly}_heat_demand_horizon`,
  `build_patex_cooling_horizon`); annual totals stay PatEx's, the heating and cooling
  held by the measured load keep the weather year's profiles. Run config
  `24h-2023-shift`: weather year 2023 (cutout `europe-2023-sarah3-era5`), +0.3 °C in
  2030, +0.7 °C in 2040 (0.4 °C per decade, Copernicus ESOTC / C3S), 2030 and 2040 only.
- 2026-11-16 Audit #5b, electric cooling as its own load (`patex.cooling`, user) and
  negative base-load hours set to 0: bundle columns `electricity {residential,services}
  space cooling` (PatEx end use cooling by building type), taken out of `electricity base
  load` (levers2 re-exported, old bundle kept as `pypsa_inputs_before_cooling_2026-11-16`).
  New rule `build_patex_cooling`: Hotmaps generic cooling profiles (Fraunhofer ISI, H2020
  Hotmaps D2.3, CC BY 4.0: slope per country, sector, day type and local hour × daily
  mean temperature above 18 °C; table `data/hotmaps_cooling_profiles.csv` from
  `scripts/hotmaps_cooling_table.py`) on population-weighted daily cooling degree days
  per node, and today's electric cooling per country and sector from JRC-IDEES (weather
  year). In `prepare_sector_network`: today's cooling out of the measured load with those
  profiles, negative hours set to 0 (IE: JRC-IDEES electric heating above the load in 8
  cold hours, no bug), rescaling, then load `<node> electricity cooling` = PatEx cooling
  × profiles. A first version (hourly cooling degree hours above 21 °C) was far too
  peaky (run `...-24h-audit` 102269/102270: a year of cooling in a few hundred hours) and was
  replaced (user: official / most relevant methodology). Fallback countries keep cooling
  in their residual (EU-trend factor on base load + cooling). Ledger row `electric
  cooling`; pypsa2html maps the carrier to the residential/tertiary electricity demand.
- 2026-11-16 Audit #5, shape of the electricity base load (user): PyPSA-Eur removes from
  the measured load the electric heating it holds, but read it from
  `pop_weighted_energy_totals` after the PatEx override, i.e. the horizon's PatEx
  electric heating. The residual (rescaled to PatEx's base load) then changed shape with
  the horizon: winter-heavy where PatEx's electric heating is below today's (heating
  counted twice), negative in winter hours where it is above (NO 2030/2040). Now
  `main()` keeps PyPSA-Eur's `electricity {residential,services} {space,water}` before
  the override and `build_heat_demand` subtracts those (new optional argument
  `electric_heat_in_load`); heat demand stays PatEx's. Same logic as industry (today's
  `current electricity`). The residual is now the same in every horizon; the log gives
  per country its TWh, Jan/Aug ratio and minimum before rescaling and warns if negative.
  Unit test `test_patex_electric_heat_subtraction.py`. Cooling (PatEx's grows much
  faster than the rest of the base load) left in the base load for now: Q23 / audit #5b.
  Fork `367127cd`. Not yet run (batch with #3 + #4).
- 2026-11-16 No direct air capture (`sector.dac: false` in `config.patex.yaml`, user):
  removals only through BECCS. Run `...-24h-wte` relied on DAC in 2040 and 2050: the
  feasibility and cost of the cap without it are to be checked in the next batch rerun.
- 2026-11-16 Audit #4, building useful heat and district heat (fork `4ca89cac`,
  `patex.heating_efficiencies`, user): PatEx outputs building heat as final energy by
  carrier; PyPSA-Eur converted it with today's carrier mix, so heat demand fell below
  PatEx's useful heat more and more with the horizon, heat-pump heat was electricity ×
  efficiency instead of electricity + ambient heat, and the district heat share (taken
  on final heat) gave the urban central bus PatEx's district heat × efficiency. New
  `patex_pypsa.heat`: PatEx useful heat rebuilt from the final energy by carrier and
  PatEx's efficiencies and technology mix (dataset, levers of the run: new export options
  `--levers-default` / `--levers-file`, also in `run_coupled.sh`); bundle parameters
  `total {sector} {use} efficiency` = useful / final, used by PyPSA-Eur for the PatEx
  countries; district heat share on useful heat. Ledger: `building heat (useful)` with
  PatEx efficiencies, new `district heat` [TWh] row. Q1 answered (moved to the fork's
  `docs/buildings.md`); Q22 (heat-pump COP, ambient vs electricity) for Climact. levers2
  re-exported (old bundle kept as `pypsa_inputs_before_useful_2026-11-16`). Not yet run.
- 2026-11-16 Audit #3, offshore wind classes (fork `570f70c5`, user): PyPSA-Eur's
  per-class offshore potentials are kept; where a country's cap is above its potential
  (BE, DE, NL at the 2050 goal; BE in 2030) all its classes are scaled by cap /
  potential before existing capacity is subtracted per class. Before, `p_nom_max = inf`
  in every country with a goal put the whole goal in the best near-shore AC class (DE
  69 GW in a 0.94 GW class): offshore 10-20 % too cheap, capacity factor too high in
  FR/IE/GB. 2030 cap unchanged (TYNDP 2026 NT+). Norway: government goal 30 GW by 2040,
  all Norwegian waters (was ENTSO-E's 15 GW, North Sea only, buildable anywhere).
  Not yet run (batched with the next audit fixes).
- 2026-11-16 Audit #2, plastics end of life and waste-to-energy (`patex.waste_to_energy`,
  user): inventory / PatEx / 1990-baseline convention. Naphtha carbon emits only at the
  steam cracker and where PatEx burns non-renewable waste for power and heat; that waste
  (new bundle columns `waste to energy fuel` / `co2`, PatEx power factor) must be burned
  in waste CHPs within the year (HVC stores, no `HVC to air`); the rest stays in products.
  Fallback countries: Eurostat share of the EU (TI_EHG_E, W6100_6220). CRF 5.C left out
  of model and baseline. Before: `HVC to air` emitted nothing and was free, so waste
  CHPs never ran and the waste-to-energy CO2 of the baseline was missing. levers2
  re-exported (old bundle kept as `pypsa_inputs_before_wte_2026-11-16`). Ledger and
  `co2_by_sector` (sector "waste to energy") updated; pypsa2html carbon balance feeds
  the waste CHP node from the naphtha node.
  Validated on run `...-24h-wte` (nic6): per country waste burned and CO2 equal the
  bundle in every horizon, no `HVC to air`, CO2 cap closes.
- 2026-11-12 Ammonia route optimised by PyPSA-Eur (fork `1ffbdab0`, PATEX_PyPSA
  `5af6d72`, user): NH3 demand = PatEx ammonia production × 5.166 MWh/t; ammonia's
  energy and process CO2 leave the industry carriers (`routes` target); export stops if
  industry + routes ≠ PatEx totals. Same for fallback countries. Methanol unchanged: no
  methanol material in PatEx (Q20). Urea / ammonia CO2 factor: Q21. levers2 bundle
  re-exported; run `...-24h-nh3` on nic6 (95899/95900).
  Validated 2026-11-16: loads equal the bundle in every PatEx country, sector and
  horizon; CO2 cap closes; GB has industry. The fallback base-load factor lets the NO
  residual load grow with the horizon (audit #5, electric heating subtracted per horizon).
- 2026-11-12 Countries outside PatEx on PatEx's EU trend (fork `4226f072`,
  PATEX_PyPSA `d9d87ea`, `patex.fallback_demand: eu_trend`, user): GB/NO/CH start from
  their own 2023 data (industry: Eurostat / UNFCCC relative to the PatEx countries) and
  follow the relative change of the PatEx sum; fuel shares proportional when falling,
  catch-up on the remainder when rising; base load as a factor on the measured load.
  Validation run `...-24h-fb` on nic6 (95822/95823).
- 2026-11-12 Audit #1 (fork `d8b6c1b9`): GB had no industry (Eurostat zeros after Brexit
  with `industry.reference_year: 2023`) and no non-EU country had non-ferrous production
  (label mismatch with JRC-IDEES 2023). Fixed upstream behaviour: latest Eurostat year
  with data (GB 2019), labels matched; build stops if a country has no industry.
  Needs a full rerun (runs 95527–95530 predate it).
- 2026-11-12 Rooftop cap at 50 % of the technical potential (fork `850885ed`,
  `renewable_limits.rooftop_pv_share: 0.5`, user): 749 GW for the 9 countries.
  nic6: 2h run `...-2h-grid-pv` (91082) failed out of memory at 68.4 GB (solver
  ordering, 2030); 3h `...-3h-grid-pv` (91050) done, MaxRSS 41.3 GiB; both used the
  2026-11-10 caps.
- 2026-11-12 Rooftop PV potential (fork `8e8fa670`, `renewable_limits.rooftop_pv_file`,
  user: JRC 2026, 100 % of the technical potential): country totals spread by
  population instead of 2 kW per inhabitant. GW: BE 72, DE 429, DK 48, FR 386, GB 369
  (ENSPRESO × 4.51), IE 30, LU 3.4, NL 92, NO 77 (Multiconsult); was 493 GW in total,
  now 1,497. Literature review in `private_notes/renewables_research/rooftop_2026-11-12.md`.
- 2026-11-12 Ground PV potential, stricter (fork `850f028c`, user: "potentials seem high"):
  no natural land (other land = brownfield and corridors only); farmland = CORINE 12–20
  outside Natura 2000, WDPA and EEA High Nature Value farmland, national shares applied
  to that area (DE too: 115 GW instead of the EEG's 177.5); cells excluded by centre /
  majority. Caps GW: BE 11, DE 149, DK 57, FR 150, GB 131, IE 43, LU 1.0, NL 17, NO 4.7
  (total 565, was 1,493 in the morning, 1,723 on 11-10). `--keep-landscape` variant
  (IUCN V eligible): DE 179, FR 165, GB 150.
- 2026-11-12 Ground PV potential, user's choices (fork `fa2d2e5f`): other land =
  Tröndle et al. (2019) rule (WDPA + Natura out, slope <= 10°, 10 % at 80 MW/km²) on
  natural open land plus brownfield and road/rail corridors (CORINE 3, 4, 7–9); CORINE 29
  dropped; 1 ha/MW kept (2.25 ha/MW = sensitivity). Slope computed from GEBCO by the
  script (`--gebco`); WDPA 2025+ schema (`REALM`) handled. National farmland rules read
  in the official texts (FR, NL, Wallonia, IE, DK, LU, NO; Flanders and IE's CAP25 target
  secondary): wording corrected, shares unchanged (no text sets a quantity). Caps
  in `data/ground_pv_potential.csv` (BE 14, DE 209, FR 238, GB 259, NL 19, NO 629 GW).
  The nic6 runs `...-3h-grid-pv` / `...-2h-grid-pv` used the previous caps.
- 2026-11-10 Ground-mounted PV potential per country (fork `25f56a2c`,
  `renewable_limits.ground_pv_file`, user): farmland share from national rules (DE: EEG
  ceiling 177.5 GW) + other eligible land at PyPSA-Eur's rule. Run 3h with network costs
  and PV caps launched (91049/91050); Tröndle variant of the other land computed
  (`update_ground_pv_potential.py --wdpa --slope`, not applied); 2h run launched
  (91081/91082).
- 2026-11-10 pypsa2html `8551ff8` (report review R7–R13): emissions charts equal the
  model's net CO2 (carbon-neutral import uptakes, discovered atmosphere ports, coal
  supply generator); self-sufficiency split into electricity / molecules / primary
  with gross pairwise electricity flows; small bar items merged into "Other" (2 %);
  NH3 out of the hydrogen demand group; "EU" group node in the report config. Four
  reports published (cap-50, −90 % 24h, −90 % 3h, −90 % 24h network costs).
- 2026-11-10 Network costs (fork `6c4e26a1` + `7ed4fe29`, user): one central regulated
  discount rate for network assets (`network_costs.discount_rate`, 4 % real; the 3.5 %
  set through `costs.overwrites` was ignored and is replaced), offshore wind
  connections included, distribution 620 €/kW, rooftop PV hosting 120 €/kWp, industry at
  transmission level off the LV bus (option `distribution_grid`), reversed DC twins no
  longer priced a converter pair (with `patex.enable`). Runs: 3h −90 % optimal
  (90617/90618); network-cost run launched (90694/90695); 3h report published.
- 2026-11-10 pypsa2html `2d8930d`: stacked bars sorted per bar (legend = first bar);
  carbon Sankey oil node conserves carbon (network oil intensity, refinery CO2 in,
  naphtha carbon kept in products) and a carbon imbalance check (build + tests);
  `568560a`: gas (network intensity, feedstock carbon kept in products) and methanol
  (country trade = node residual) likewise.
- 2026-11-10 Run `patex-levers2-nwe-bz-co2-90-2040-24h` optimal (nic6 90590/90591),
  published with the cap-50 NWE report rebuilt (pypsa2html `8d4f509`: bars ordered largest
  first by the earliest horizon, methanol storage shown); BE-LU-NL reports removed from
  caneurope (user). `config/patex/3h.yaml` (3-hourly overlay), run launched (90617/90618).
  Review of the report: `private_notes/REPORT_REVIEW.md`.
- 2026-11-10 `patex.fallback_import_caps: eu_per_capita` (user): import cap of each
  modelled non-PatEx country (GB, NO, CH) per fuel = EU import cap per person (PatEx caps,
  imports + production gap, of every bundle country / their population) × its
  population; population from JRC ARDECO (`SNPTD`, PyPSA-Eur's own source). Replaces its
  Eurostat imports (cap 0 for H2 / methanol / NH3 / synthetic fuels); domestic caps
  unchanged. Overlay `config/patex/co2-cap-90-2040-24h.yaml` (−50 % 2030, −90 % 2040 and
  2050). pypsa2html (local branch `can-climact`): page "Imports and self-sufficiency"
  (imports per vector and supply region from outside / from modelled regions, cap, use,
  dual; electricity exchanges; self-sufficiency per region). Run
  `patex-levers2-nwe-bz-co2-90-2040-24h` launched on nic6.
- 2026-11-09 `import_limits.transit_penalty` (0.01 EUR/MWh, user: trade with modelled
  non-EU countries at the cost of foreign imports, no fuel routed through the other side):
  tie-break on pool flows and on gas / H2 pipelines crossing the EU / non-EU boundary.
  NW Europe report published (caneurope `pypsa_results/patex-levers2-nwe-bz-co2-cap-50-24h/`).
- 2026-11-09 `import_limits`: EU-wide fuel pools (oil, coal, methanol, NH3) split per
  region (user): own import / production copies for each non-PatEx country, net annual
  flow of each into the pool counted as EU import (or as its own import); demand located
  (`regional_coal_demand`, `regional_methanol_demand`, `ammonia: regional` in
  `config.patex.yaml`). Electricity: no cap (self-sufficiency indicators). CO2 storage
  2030 change of the same day reverted (FID / built sites only in 2030, PatEx total).
- 2026-11-09 `import_limits` with non-PatEx countries (GB, NO): caps per region — PatEx
  countries together (PatEx imports; gross gas / H2 pipeline inflow from GB, NO counts as
  EU import) and each other country (Eurostat imports and production, latest year with
  data: GB 2019); EU-wide-bus fuels one summed cap. Tests; `docs/energy.md`. Run overlay
  `config/patex/levers2-nwe-bz.yaml` (GB, IE, Benelux, DE, FR, DK, NO; bidding zones;
  4 resource classes).
- 2026-11-09 T30 `interconnection_limits` on a physical basis (user): cap = factor[h] ×
  (usable capacity of PyPSA-Eur's grid + TYNDP 2024 transfer-capacity increase of the
  cross-border projects commissioned 2026..h, statuses 2–4, not already in PyPSA-Eur's
  TYNDP 2020 lines); `data/interconnection_projects_tyndp2024.csv`,
  `scripts/update_interconnection_projects.py`; NTCs logged for comparison only. Replaces
  the NTC-based cap of the entry below. `docs/energy.md` rewritten.
- 2026-11-09 T30 `interconnection_limits` (new top-level config section, standalone,
  default off; `scripts/_interconnection_limits.py`, `compose_network`, `solve_network`):
  usable cross-border capacity per border (AC × s_max_pu + DC, existing and new) ≤
  factor[horizon] × TYNDP 2026 reference-grid NTC 2030 (`data/interconnection_ntc_2030.csv`,
  `scripts/update_interconnection_ntc.py`); factor 1.0 in 2030, 1.5 after (config); existing
  above the cap kept, not expanded. Tests; `docs/energy.md`. On in `config.patex.yaml`.
- 2026-11-09 T31 `renewable_limits` (new top-level config section, standalone, default
  off; `scripts/_renewable_limits.py`, applied in `compose_network`, constraint in
  `solve_network`): offshore wind per country capped at its TEN-E 2050 goal at every
  horizon (`data/offshore_wind_goals.csv`, Member States' goals of January 2023 read in
  ENTSO-E's ONDP 2024), PyPSA-Eur's per-node offshore potential lifted there; 2030 onshore,
  offshore and solar capped at TYNDP 2026 National Trends+
  (`data/renewables_planned_2030.csv`, `scripts/update_renewables_planned.py`); existing
  capacity counted. Tests; `docs/energy.md`. On in `config.patex.yaml` and the PatEx test.
- 2026-11-09 T32 `co2_storage` (new top-level config section, standalone, default off;
  `scripts/_co2_storage.py`): CO2 sequestered per country and year capped at the
  injection capacity of its storage projects from the IEA CCUS Projects Database
  (`data/co2_storage_projects.csv`, `scripts/update_co2_storage_projects.py`, KAPSARC open
  copy or the IEA file); `GlobalConstraint` type `co2_storage_limit` per country, solved
  on all build years of the `co2 sequestered` stores (fixes upstream's per-build-year
  CO2StoP ceiling under myopic foresight, as PyPSA-Wal); CO2StoP `e_nom_max` removed.
  `patex.co2_sequestration` (true): total cap = PatEx CO2 stored over the modelled
  countries, instead of `sector.co2_sequestration_potential`. Tests; `docs/energy.md`.
  On in `config.patex.yaml` and the PatEx test config.
- 2026-11-09 T16 `ev_flexibility` (new top-level config section, standalone, default off;
  `scripts/_ev_flexibility.py`, `add_EVs`): Elia AdeqFlex 2025 market share flexible,
  inflexible load `land transport EV inflexible` on Elia's charging curves (local time
  per country; moved to low voltage), Elia availability, 60 kWh, no V2G; flexible load
  net of the charger loss. `patex.phev_fleet_factor` (0). Data `data/ev_charging/`.
  Tests; `docs/transport.md`. On in `config.patex.yaml`.
- 2026-11-07 `nuclear_fleet`: a horizon without any usable reactor no longer fails
  (BE-LU-NL 2040, found by the T37 run); test.
- 2026-11-07 `data/nuclear_fleet.csv` from IAEA PRIS (status, net MW, grid year per unit;
  `scripts/update_nuclear_fleet_from_pris.py`, raw `data/nuclear_pris.csv`).
- 2026-11-07 `nuclear_fleet.min_remaining_years` 5 → 4 (user): BE's Doel 4 / Tihange 3
  (end 2035) now in the 2030 horizon.
- 2026-11-07 T34 `nuclear_fleet` (new top-level config section, standalone, default off;
  `scripts/_nuclear_fleet.py`, applied in `compose_network` after the brownfield step):
  per-reactor links from `data/nuclear_fleet.csv`, duplicate generators removed, uranium
  supply, lifetime extension and must-run; `test/test_nuclear_fleet.py`; `docs/energy.md`.
  `config.patex.yaml`: on, 50 years default, margin 0.10. Colours for oil / coal production.
- 2026-11-07 T29 `import_limits` (new top-level config section, standalone, default off;
  `scripts/_import_limits_config.py`): caps on gross imports per fuel for the whole region
  and on domestic gas / oil / coal (`GlobalConstraint` types `import_limit` /
  `domestic_limit`, `solve_network.add_supply_limits_per_fuel`); gas fields split from the
  entries (`gas production`); `add_bio_imports` (`import biogas`, `import bioliquids`);
  `add_domestic_supply`. PatEx hook `patex.import_limits` (`patex_supply_{h}.csv`, Eurostat
  production for the gap). `config.patex.yaml`: import options on. Overlay
  `config/patex/co2-cap-50-24h.yaml`. Plot colours; `docs/energy.md`.
- 2026-11-06 T18 non-electric cooking: `add_patex_cooking_loads` (flat loads per fuel, links
  with the fuel's CO2, `H2 for cooking`), cooking columns split like PyPSA-Eur's cooking
  totals. T19 district heating losses: `add_heat` gets `no_district_heating_loss` (PatEx
  countries), `add_patex_district_heating_losses` (PatEx rate on building + industry heat of
  each urban central bus, `patex.district_heating`). Plot colours; `docs/buildings.md`,
  `docs/energy.md`.
- 2026-11-06 Pushed `develop` to origin (user consent).
- 2026-11-05 Gas storage from working gas, no clip (behind `patex.enable`;
  `build_gas_input_locations` param `patex_enable`); `docs/energy.md`.
- 2026-11-05 T27 reverted: no `scale_patex_industry_co2`, no industry intensity file; physical
  factors; `docs/energy.md` explains why (CRF calibration not transferred). Test overlay
  without cap at 24h (fast chain test).
- 2026-11-05 T26/T27: `scale_patex_industry_co2` (industry CO2 ports per country with PatEx's
  CRF-calibrated factors); `oil_refining_emissions` from the bundle; rules pass
  `patex_industry_co2_intensity_{h}.csv`; `compose_network` skips the `oil refining` row;
  `docs/energy.md` (calibration, refineries), `docs/README.md`.
- 2026-11-05 T24: `oil for industry` load (burnt industry liquids, oil CO2) in
  `add_industry`; `build_industrial_energy_demand_per_node` requires the column and sets the
  PatEx-only columns (`methane feedstock`, `oil for industry`) to 0 for fallback countries;
  plot colour; `docs/industry.md`.
- 2026-11-05 `docs/energy.md`, `docs/README.md`: CO2 accounting rule (process emissions from
  PatEx, every other emission computed by PyPSA-Eur with PatEx's fuel factors).
- 2026-11-05 BE-LU-NL overlays: solve `mem_mb` 25000, Gurobi 16 threads (measured on nic6);
  test overlay without CO2 cap: no `co2_stored` interactive map (empty balance without cap).
- 2026-11-03 Rule `build_patex_report` (`rules/patex.smk`, not in `all`).
- 2026-11-03 Pushed `master` and `develop` to origin (user consent).

- 2026-11-03 Remaining PatEx inputs, behind `patex.enable` (`MODEL_CHANGES.md`):
  process emissions and `ammonia`/`methanol` = 0 (industry file), `gas feedstock for
  industry` load without CO2, CO2 intensity of gas/oil/coal from the bundle
  (`compose_network.py`), district heating share from PatEx
  (`build_district_heat_share.py`), land-transport loads scaled per fuel and EV fleet
  from PatEx (`add_land_transport`, `add_EVs(number_evs=)`); config flags
  `co2_intensity`, `district_heating`. Upstream test: objective 570,205,121 (−0.0004 %).
- 2026-11-03 PatEx hooks, behind `patex.enable` (`pypsa_eur_integration/README.md`):
  `patex:` config section (in `config.default.yaml` and schema), rule
  `build_patex_demands`, energy totals, industry, base load, land transport (distance and
  shares per node), international shipping; `config/config.patex.yaml` (with T1 machinery
  shares, `"NO"` quoted), `config/test/config.patex.yaml`. Upstream test unchanged.
- 2026-11-03 New fork cloned from upstream `d02406c4`; `develop` created, `upstream`
  remote set. The old checkout (`Julien2000info/pypsa-eur`, no own commits) is removed.

- 2026-11-02 Added remote `upstream` (PyPSA/pypsa-eur), fast-forwarded `master` by 3
  upstream commits (`8d4b7d30`), created `develop`.

- 2026-11-04 `config/patex/levers2-be-lu-nl.yaml`: run overlay for BE, LU, NL (levers 2
  bundle, 10 nodes, 3h, solve memory 60 GB, Gurobi 32 threads);
  `config/patex/test-no-co2-cap.yaml`: technical test without CO2 cap (T11 open).
- 2026-11-04 `patex.plastics_eol_co2` (default false, PatEx convention) and
  `industry.waste_to_energy: true` in `config.patex.yaml` (T23); `docs/`: data flow per
  sector (buildings, transport, industry, agriculture, energy).
- 2026-11-04 Industry hydrogen split over nodes by gross uses (T22).
- 2026-11-05 T15, behind `patex.enable`: `add_shipping` fuel shares per country from
  PatEx, energy per fuel without conversion (config shares unchanged otherwise:
  refactored to per-node shares, same loads); `add_gas_vehicles` (new, gas road on the gas
  bus with CO2, ICE profile); `add_patex_transport_loads` (new: rail / aviation / shipping
  electricity with the base-load shape, H2 for rail flat); PatEx-only columns split like
  the related PyPSA-Eur column (`hydrogen road` now like `total road`, was population);
  old bundles fail (re-export). PatEx configs: colours of the new carriers, no methanol
  interactive map (empty without methanol ships). `docs/transport.md`, `energy.md`.
- 2026-11-05 `docs/<sector>.md`: "Why" sections (settled reasons moved from
  `SOFTLINKING_PLAN.md`, incl. the chlor-alkali research in `industry.md`).

## PatEx

Not modified. Used as is (`patex run`, dataset `47.x.4` on S3).

## PATEX_PyPSA

### 2026-11-09 — T32 PatEx CO2 stored in the bundle

- Rule `co2 stored` (`patex_parameters_{h}.csv`, Mt/a): `clm_total-emissions-CCS` × −1;
  a country below 0 (PatEx's CO2 deficit booked as negative storage) is set to 0 at export
  with a warning (`export.CLIP_AT_ZERO`). Caps the total CO2 sequestration in the fork
  (`patex.co2_sequestration`). levers2 bundle re-exported.
- `check_network_ledger.py`: total sequestration cap vs PatEx, per-country caps and CO2
  sequestered. Tests.

### 2026-11-09 — T16 BEV and PHEV fleets

- Export `number bev` and `number phev` instead of `number evs`; ledger: EV grid draw
  (flexible / charger efficiency + inflexible) and fleet behind the chargers. Test.

### 2026-11-07 — CO2-cap run (T36) and its post-processing

- `co2_by_sector.py`: CO2 taken up on port 0 (carbon-neutral imports), imports as fuel
  supply; the sector total equals the CO2 in the atmosphere (= the cap).
- `CLUSTER_NIC6.md`: job sizes measured for a 24h run.

### 2026-11-07 — T29 supply caps in the bundle

- Export `patex_supply_{h}.csv`: gross imports per fuel (supply Sankey `source = import`,
  bioenergy `origin = import`) and `<fuel> production` (primary production of gas, oil,
  coal); methanol / NH3 = 0; rest of the supply Sankey and domestic bioenergy ignored.
- `check_network_ledger.py`: supply caps of the network vs the bundle. Test.

### 2026-11-06 — T18 cooking per fuel, T19 PatEx district heating loss rate

- Export: `{gas,oil,solid biomass,coal,hydrogen} cooking` (energy totals), `district heating
  loss` (parameters: heat distribution losses / heat delivered from
  `elc_energy-sankey-detailed`; rest of that Sankey explicitly ignored, coverage stays empty).
- Report Sankey: non-electric cooking goes to `Building cooking (non-electric)`.
- `check_network_ledger.py`: cooking per fuel, district heating loss rate, cooking CO2
  intensities; `co2_by_sector.py`: cooking carriers → buildings. Tests.
- `levers2` bundle re-exported; BE 2030 test ledger all 1.0000 (building heat now exact).
- Pushed `develop` (user consent, before this change).

### 2026-11-05 — T35: CO2 per sector with bio credits on consumers

- `scripts/co2_by_sector.py` (+ test): per country and sector, gross / bio credit / net;
  the bio credit of the gas, oil and methanol pools goes to their consumers (mass balance).

### 2026-11-05 — T27 reverted: PatEx's CRF calibration not transferred

- `emissions.industry_co2_intensity` and `patex_industry_co2_intensity_{h}.csv` removed;
  solid waste CO2 back to PatEx's factor; ledger checks the fuel factors. PatEx calibrates
  every sector on the inventory; its rates partly move emissions between sectors, which
  PyPSA-Eur counts physically. Baseline consistency moves to T11.

### 2026-11-05 — T26, T27: refinery CO2 and CRF-calibrated industry CO2

- `emissions.industry_co2_intensity`: per country and fuel, PatEx's industry factor ×
  its CRF calibration rates (per material, weighted by the fuel's use) →
  `patex_industry_co2_intensity_{h}.csv`; solid waste CO2 calibrated the same way.
- `emissions.refinery_co2_intensity`: refinery emissions before capture / refinery output
  → row `oil refining` of `patex_co2_intensity_{h}.csv`.
- Ledger: refinery and per-country industry factors; tests (calibration reproduces
  PatEx's combustion CO2).

### 2026-11-05 — T24: burnt industry oil with CO2

- `data/extraction_rules.csv`: `naphtha` = liquid feedstock only; new `oil for industry` =
  burnt liquids. Sankey node `Industry oil`; ledger check `industry oil`; test.
- Found by the CO2 accounting check (T24–T27): the CO2 of oil burnt in industry was lost in
  PyPSA-Eur's plastics chain.

### 2026-11-05 — T15: one load per transport fuel

- `data/extraction_rules.csv`: new `gas road`, `hydrogen rail`, `electricity aviation`,
  `electricity navigation`, `hydrogen navigation`; rail, aviation and shipping electricity
  out of `electricity base load`.
- `data/sankey_nodes.csv`, `sankey_flows.csv`: Land transport gas, Rail electricity /
  hydrogen, Aviation electricity, Shipping oil / hydrogen / electricity.
- `transport.land_transport_scale`: any engine column (gas). Ledger script: the new loads.
- `OPEN_QUESTIONS.md` Q14 (methanol / ammonia ships absent from PatEx), `MODEL_CHANGES.md`.

### 2026-11-05 — SOFTLINKING_PLAN.md → OPEN_QUESTIONS.md

- The plan is past: `OPEN_QUESTIONS.md` keeps only the open questions (Q1, Q3, Q5, Q8,
  Q9 kept; new Q10–Q16, incl. Q14 methanol / ammonia ships absent from PatEx). Closed
  questions, steps and the TIMES comparison removed; settled reasons moved to the fork's
  `docs/<sector>.md` ("Why"), the pitfalls table to `MODEL_CHANGES.md`, the 25-country
  PatEx run command and fallback countries to the README.

### 2026-11-04 — Cluster nic6 and pypsa2html

- `scripts/cluster/nic6_env.sh`, `scripts/cluster/pypsa_job.sh`: environment and generic
  Slurm job (any config files, snakemake on the job's cores and memory).
- `scripts/pypsa2html_config.py`: pypsa2html project config for one run, country groups
  from `n.buses.country` (any country set), network pattern `solved_{horizon}.nc`.

### 2026-11-04 — Docs cleanup

- `pypsa_eur_integration/` removed (one README repeating `MODEL_CHANGES.md` and the
  install notes); its content is in README, section "PyPSA-Eur side", with the BE test
  command. README layout lists the docs and `private_notes/`; test commands as in both envs.
- `SOFTLINKING_PLAN.md`: status, report row, district heating losses (T19) updated.
- `TODO.md`: T5, T18, T19 brought in line with the handover proposals.

### 2026-11-03 — Report: Sankey and PatEx indicators

- `patex_pypsa/sankey.py`, `data/sankey_flows.csv`, `data/sankey_nodes.csv`: every PatEx
  demand row once, fuel → sector → PyPSA-Eur input; reconciliation with the bundle.
- `patex_pypsa/indicators.py`, `data/indicators.csv`: PatEx output series.
- `patex_pypsa/pages.py`, CLI `report`: HTML pages (after TIMES_PyPSA), `run_coupled.sh`
  builds them. Export writes `sankey_flows.csv` and `patex_indicators.csv`.
- `extraction.signed_sum` (moved from the ledger script).

### 2026-11-03 — CO2, process emissions, district heating, EV fleet

- `MODEL_CHANGES.md`: what is passed and changed in each model, and why (for review).
- Rules: process emissions (olefins apart), `methane feedstock`, solid waste (→ CO2 at
  export), electric aviation/shipping into `electricity base load`, `district heat`,
  `number evs`. `ammonia`, `methanol` = 0.
- `patex_pypsa/emissions.py`: PatEx CO2 factors (dataset) → `patex_co2_intensity_{h}.csv`;
  `export-coupling --dataset`. New bundle files `patex_parameters_{h}.csv`,
  `patex_co2_factors.csv`.
- `patex_pypsa/transport.py`: `land_transport_scale` replaces `land_transport_from_energy`.
- Long table: `TWh` column → `value` + `unit` (a category mixing units fails).
- `check_network_ledger.py`: process emissions, feedstock gas, EV fleet, district heating
  share, CO2 intensities.

### 2026-11-03 — Hooks applied, land transport, ledger check

- `patex_pypsa/transport.py` (`land_transport_from_energy`): PatEx road energy by carrier
  → PyPSA-Eur driven distance and EV / fuel-cell / ICE shares per node.
- `extraction_rules.csv`: new column `hydrogen road`.
- `scripts/check_network_ledger.py`: composed network loads vs bundle, per country.
- `pypsa_eur_integration/`: the file copies are removed (they live in the fork); the
  README now documents the applied hooks.
- Paths `../../pypsa-eur` → `../../PyPSA-Eur-CANEU`; `origin` set to
  `IntSusEnergySystems/PatEx-PyPSA` (not pushed).

### 2026-11-02 — Agriculture split by use (`2941a7d`)

- `patex_pypsa/agriculture.py`, `data/agriculture_use_shares.csv`: PatEx agriculture by
  carrier → PyPSA-Eur electricity / heat / machinery, with the JRC-IDEES 2021 shares of
  each country (EU27 fallback). CLI `build-agriculture-shares`.
- Rules: agriculture extracted by carrier group; PatEx gasoline grouped with fuel oil.
- Electric machinery goes into `total agriculture electricity`; machinery = liquid fuel.
- `scripts/check_agriculture_split.py`: base-year check against IDEES.
- `config.patex.yaml`: machinery shares left commented out (TODO T1).

### 2026-11-02 — First version (`ddf5386`)

- Package `patex_pypsa`: read `patex run -o` pickles, signed extraction rules,
  coverage/sign/horizon checks, coupling bundle with manifest, country → node allocation.
- `data/extraction_rules.csv`, `data/mapping_countries.csv` (EL→GR, UK→GB).
- `pypsa_eur_integration/`: `patex:` config section, `build_patex_demands` rule, hooks
  documented; `fallback_countries` for AL BA CH GB ME MK NO RS XK.
- `scripts/run_coupled.sh`, tests (both environments).
