# Model changes for the PatEx → PyPSA-Eur soft-link

What each model gets from the link, what was changed in it, and why. Keep one line per
change; details and data checks are in the fork's `docs/<sector>.md` ("Why"), open
questions in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), dates in [CHANGELOG.md](CHANGELOG.md).

**Rule of the link.** PatEx sets *what has to be served* (annual demand per country,
fleet, district heating share, process emissions, CO2 factors). PyPSA-Eur decides *how*
(capacities, flexibility, fuel origin, CCS, imports, costs). Each country keeps
PyPSA-Eur's split across its nodes and over the hours; only the annual total is PatEx's.
Countries without PatEx data (`patex.fallback_countries`) keep PyPSA-Eur's own inputs.

## PatEx (Climact)

Not modified. Run as is (`patex run`, dataset `47.x.4`). The link reads the run pickle
and, for the CO2 factors and the heating efficiencies and technology mix (with the
levers of the run), the dataset.

## PatEx → bundle (this repository, `data/extraction_rules.csv` and `patex_pypsa/`)

| PyPSA-Eur input | From PatEx | Why this way |
|---|---|---|
| Building heat (`total/electricity {residential,services} {space,water}`) | `bld_energy-demand-incl-district-heating` − ambient heat | final energy incl. district heat, the base of PyPSA-Eur's heat totals; ambient heat is modelled by PyPSA through heat-pump COPs |
| `electricity base load` (new) | building electricity − electric heating − electric cooling | residual hourly load after PyPSA-Eur's explicit electric heating and cooling |
| `electricity {residential,services} space cooling` (new, audit #5b) | building electricity, end use cooling, by building type | own load with the Hotmaps residential / tertiary cooling profiles (`patex.cooling`); grows much faster than the rest of the base load |
| Agriculture electricity / heat / machinery | by carrier, split by use with JRC-IDEES 2021 shares per country | PyPSA-Eur needs uses, PatEx has carriers; electric machinery goes to electricity |
| Road and rail: `electricity road`, `hydrogen road`, `gas road`, `electricity rail`, `hydrogen rail` (new except `electricity rail`), ICE rest | road + rail by carrier | one load per fuel (see fork, land transport) |
| Aviation, navigation | domestic + bunkers, without their electricity | kerosene / shipping loads |
| `electricity aviation`, `electricity navigation`, `hydrogen navigation` (new) | domestic + bunkers by carrier | own loads; hydrogen share of shipping per country (PatEx has no methanol or ammonia ships, Q14) |
| Industry carriers | `ind_energy-demand-by-carrier-feedstock` | PatEx `solid-ff-coal` includes coke |
| `methane feedstock` (new) | feedstock gas (ammonia, olefins) | not burnt: no combustion CO2; its released CO2 is in PatEx process emissions |
| `naphtha` / `oil for industry` (new, T24) | industry liquids: feedstock / burnt | feedstock feeds the plastics chain; burnt oil gets combustion CO2 (was lost in the plastics chain) |
| `ammonia`, `methanol`, `coke` = 0 | — | PatEx makes them from carriers already exported; PyPSA-Eur would make them again |
| `process emission` | PatEx process emissions except olefins + solid-waste CO2 | before capture (PyPSA decides CCS); CO2e, small non-CO2 share |
| `process emission from feedstock` | PatEx olefin process emissions | in PyPSA-Eur only a split of the naphtha carbon, not extra CO2 |
| Solid waste in industry | energy × PatEx CO2 factor → process emission | no such fuel in PyPSA-Eur: not supplied by the network, only its CO2 kept |
| `waste to energy fuel` / `co2` (new, parameters, audit #2) | non-renewable waste input to power and heat plants (sankey transformation input × non-renewable share of waste production) × PatEx power factor | waste burned for energy is in the 1990 baseline (CRF 1.A.1.a); PatEx's power sector holds it |
| `total {sector} {use} efficiency` (new, parameters, audit #4) | PatEx useful heat (final by carrier × PatEx efficiency by technology, heat pumps electricity + ambient, district heat at 1) / bundle final heat | heat demand = PatEx's useful heat, not today's mix (`patex_pypsa.heat`) |
| `district heat share` (new) | district heat / building useful heat (audit #4; was final heat) | replaces PyPSA-Eur's today share + progress; applied to useful heat in PyPSA-Eur |
| `patex_supply_{h}.csv` (new, T29): gross imports per fuel, `<fuel> production` | supply Sankey `source = import` / `primary-production`; bioenergy `origin = import` | caps on imports per fuel for the whole region (`import_limits`); domestic production capped at min(PatEx, today's Eurostat), the rest added to the import cap |
| `district heating loss` (new, T19) | heat distribution losses / heat delivered (`elc_energy-sankey-detailed`) = PatEx `network-losses[%]` | PatEx's rate per country on all network heat (buildings and industry), replaces PyPSA-Eur's 15 % on building heat only |
| `{gas,oil,solid biomass,coal,hydrogen} cooking` (new, T18) | non-electric cooking per fuel, residential + services | PyPSA-Eur has no cooking load: the fuel and its CO2 were missing |
| `number bev`, `number phev` (T16) | cars and vans BEV / PHEV | EV fleet = BEV + `phev_fleet_factor` (0) × PHEV: sizes chargers and the EV battery |
| `co2 stored` (T32) | `clm_total-emissions-CCS` × −1 (captured − (CO2 use − DAC)); a negative country (PatEx books a CO2 deficit as negative storage) set to 0 at export | total CO2 sequestration cap = PatEx sum over the modelled countries (`patex.co2_sequestration`); CCS amount is a PAC 2.0 lever, where to capture and store stays PyPSA-Eur's |
| CO2 intensity of `gas`, `oil`, `coal` | PatEx combustion factors (ind, tra, agr, bld) weighted by PatEx fossil use per horizon | PyPSA-Eur counts combustion CO2 with PatEx's factors; values are computed from PatEx, not written in the config |
| Not passed: PatEx's inventory (CRF) calibration of combustion CO2 (T27) | — | its rates partly move emissions between sectors; PyPSA counts physical carbon; baseline consistency handled as a total (T11, fork `docs/energy.md`) |
| `oil refining` CO2 per MWh of oil (row of `patex_co2_intensity_{h}.csv`, new, T26) | PatEx refinery emissions (before capture) / refinery output, all run countries | emissions-per-unit parameter from PatEx, like the fuel factors; replaces `industry.oil_refining_emissions` |

Not passed (on purpose): power-sector outputs `elc_*` (compared afterwards), fuel origin
(fossil/bio/syn), refinery throughput (only its CO2 per MWh), heating technologies; of the
heat network losses only the rate is passed (PyPSA-Eur applies it to its own delivered heat).

## PyPSA-Eur (fork `IntSusEnergySystems/PyPSA-Eur-CANEU`, branch `develop`)

Everything is behind `patex.enable` (default `false`): without it the results are
unchanged (upstream test objective within solver tolerance).

| File | Change | Why |
|---|---|---|
| `scripts/_patex_config.py`, `config_updates.py`, `config.default.yaml`, schema | `patex:` section (`enable`, `coupling_dir`, `fallback_countries`, `energy_totals`, `industry`, `co2_intensity`, `district_heating`, `heating_efficiencies`, `base_load`, ...) | config keys must be declared (strict validation) |
| `rules/patex.smk`, `scripts/build_patex_demands.py` | copy and check the bundle per horizon | each run records its PatEx inputs; a missing country fails |
| `rules/compose.smk`, `rules/build_sector.smk` | PatEx inputs wired when enabled | |
| `build_industrial_energy_demand_per_node.py` | industry carriers and process emissions per country from PatEx; hydrogen split over nodes by gross uses | the chlorine by-product (negative in PyPSA-Eur's ratios, absent from PatEx) flipped the split's signs |
| `build_district_heat_share.py` | country share from PatEx, spread like today's share | PatEx sets district heating per horizon |
| `build_gas_input_locations.py`, `prepare_sector_network.add_h2_gas_infrastructure` | existing gas storage = SciGRID working gas (not cushion gas), no 98 % clip | upstream data bug (found in PyPSA-Wal): BE storage 15x too small, NL 4x too large |
| `compose_network.py` | CO2 intensity of gas, oil, coal from the bundle (the `oil refining` row is skipped) | same CO2 per fuel as PatEx |
| `prepare_sector_network.main` | `industry.oil_refining_emissions` from the bundle (T26); error if the row is missing | refinery CO2 per MWh from PatEx |
| `prepare_sector_network.main` | energy totals per country from PatEx (heat, agriculture, aviation, navigation); base load rescaled at the end | |
| `prepare_sector_network.build_heat_demand`, `main` (audit #5) | electric heating subtracted from the measured load = PyPSA-Eur's own (kept before the PatEx override), not PatEx's | the measured load holds today's electric heating; residual the same in every horizon |
| `prepare_sector_network.main` (base load) | negative residual hours set to 0 before the rescaling | subtracted electric heating above the measured load (IE, March 2013 cold spell) |
| `rules/patex.smk` `build_patex_cooling`, `prepare_sector_network.patex_cooling_shape`, `add_patex_cooling_load` (`patex.cooling`, audit #5b) | Hotmaps generic cooling profiles (per country, sector, day type, local hour, ∝ daily mean T − 18 °C; `data/hotmaps_cooling_profiles.csv` from `scripts/hotmaps_cooling_table.py`) on population-weighted daily cooling degree days per node; today's electric cooling per sector (JRC-IDEES, weather year) out of the measured load; PatEx cooling as load `electricity cooling` | PyPSA-Eur has no cooling demand; PatEx cooling would otherwise get the base load's winter-leaning shape |
| rules `build_{daily,hourly}_heat_demand_horizon`, `build_patex_cooling_horizon`; `build_cop_profiles`, `build_central_heating_temperature_profiles`, `build_daily_heat_demand`, `prepare_sector_network.build_heat_demand` (`patex.temperature_shift`) | per horizon, a uniform shift added to the weather year's outdoor temperature for heat demand, cooling, heat-pump COPs (air, ground) and DH forward temperatures; the heating and cooling held by the measured load keep the unshifted profiles | one weather year for every horizon: a growing cooling volume only raised the same peaks; the climate trend spreads it (and concentrates heating) |
| `build_electricity_demand.scale_gb_to_dukes` (`patex.gb_load_dukes`, `data/dukes_electricity_available.csv`) | GB load of each weather year scaled to DUKES 5.1.2 "Electricity available" | upstream's NESO National Demand excludes embedded wind and solar (−25 % in 2023); GB's base load follows it |
| `prepare_sector_network.main` (`patex.heating_efficiencies`) | `total {sector} {use} efficiency` of the PatEx countries from the bundle (`patex_heating_efficiencies`) | heat demand = PatEx useful heat (audit #4) |
| `prepare_sector_network.add_land_transport` | EV, fuel-cell, gas and oil loads = PyPSA-Eur hourly profile × PatEx energy per fuel; EV fleet from PatEx | PyPSA-Eur builds road demand once from 2023 energy as a distance; PatEx gives future energy per fuel |
| `prepare_sector_network.add_EVs` | optional `number_evs` sizes chargers / DSM / V2G | instead of share × today's cars |
| `scripts/_ev_flexibility.py`, `add_EVs` (`ev_flexibility`, T16) | Elia AdeqFlex market share flexible, rest on Elia's charging curves, Elia availability, 60 kWh, no V2G, grid draw = EV demand | PyPSA-Eur overstates EV flexibility (fork `docs/transport.md`) |
| `prepare_sector_network.add_ice_cars` | multiply by the share before renaming | allows a per-node share (same result for a scalar) |
| `prepare_sector_network.add_shipping` | international navigation per country from PatEx, port split kept; fuel shares per country from PatEx, energy per fuel without conversion | `shipping_demand.csv` is built from 2023; PyPSA-Eur's shares and efficiencies would change PatEx's fuel mix and energy |
| `prepare_sector_network.add_gas_vehicles` (new) | `land transport gas` load per node, ICE profile, from the gas bus with CO2 | PyPSA-Eur has no gas vehicles |
| `prepare_sector_network.add_patex_transport_loads` (new) | loads `rail electricity`, `aviation electricity`, `shipping electricity` (base-load shape, transmission bus), `H2 for rail` (flat) | PyPSA-Eur has no such loads; each fuel visible in its own load |
| `prepare_sector_network.add_heat` (`no_district_heating_loss`), `add_patex_district_heating_losses` (new) | `district_heating_loss` = 0 for the PatEx countries; load `urban central heat losses` = PatEx rate × building + low-temperature industry heat on each urban central bus (`patex.district_heating`) | see `district heating loss`; losses visible as their own load |
| `prepare_sector_network.add_patex_cooking_loads` (new) | flat loads `gas / oil / coal / solid biomass for cooking` fed by links with the fuel's CO2, `H2 for cooking` on the H2 bus (`patex.energy_totals`) | see `<fuel> cooking` |
| `scripts/_import_limits_config.py`, `prepare_sector_network.add_supply_limits` / `add_domestic_supply` / `add_bio_imports` / `patex_supply_limits`, `add_h2_gas_infrastructure` (`split_gas_production`), `solve_network.add_supply_limits_per_fuel` (T29) | caps on gross imports per fuel (whole region) and domestic gas / oil / coal; gas fields split from the entries; carbon-neutral biogas / bioliquids imports; `import_limits` is standalone (default off), PatEx values with `patex.import_limits` | self-sufficiency scenarios; PatEx imports as upper bounds (fork `docs/energy.md`) |
| `scripts/_nuclear_fleet.py`, `compose_network.py`, `data/nuclear_fleet.csv` (T34) | one link per reactor (official table), no duplicate generators, uranium supply, one 10-year extension (model's choice), not used within 4 years of its end, must-run | upstream double-counts nuclear and keeps generators forever; powerplantmatching is out of date (fork `docs/energy.md`) |
| `scripts/_co2_storage.py`, `prepare_sector_network.main`, `solve_network` (`add_co2_storage_constraints`, total cap kept if already in the network), `data/co2_storage_projects.csv`, `scripts/update_co2_storage_projects.py` (T32) | `co2_storage` (standalone, default off): CO2 sequestered per country ≤ injection capacity of its storage projects (IEA CCUS Projects Database; built only until 2030, planned from their operation year, undated from 2040), all build years of the stores together, CO2StoP `e_nom_max` removed; `patex.co2_sequestration`: total cap = PatEx CO2 stored | CO2StoP has gaps (NO, FR, ES ~0) and no injection rate; the per-node ceiling applied per build year let the fleet exceed it under myopic foresight; upstream's total has no source (fork `docs/energy.md`) |
| `scripts/_interconnection_limits.py`, `compose_network.py`, `solve_network.add_interconnection_constraints`, `data/interconnection_ntc_2030.csv`, `scripts/update_interconnection_ntc.py` (T30) | `interconnection_limits` (standalone, default off): usable capacity per border (AC × s_max_pu + DC) ≤ factor[horizon] × (PyPSA-Eur grid + TYNDP 2024 projects commissioned 2026..horizon); factor 1.0 in 2030, 1.5 after; `data/interconnection_projects_tyndp2024.csv` | with `vopt` cross-border expansion is nearly free and replaces flexibility; physical ratings, not NTCs (an NTC cap double counts the network limits PyPSA's power flow already models) (fork `docs/energy.md`) |
| `scripts/_renewable_limits.py`, `compose_network.py`, `solve_network.add_renewable_limit_constraints`, `data/offshore_wind_goals.csv`, `data/renewables_planned_2030.csv`, `scripts/update_renewables_planned.py` (T31) | `renewable_limits` (standalone, default off): offshore wind per country ≤ its TEN-E 2050 goal at every horizon (per-node potential lifted); 2030 onshore / offshore / solar ≤ TYNDP 2026 National Trends+; existing included; no build rate | upstream's offshore potential (2 MW/km²) is below installed capacity in BE and far below national plans; 2030 is mostly decided (fork `docs/energy.md`) |
| `prepare_sector_network.add_industry` | load `gas feedstock for industry` on the gas bus, no CO2 | see `methane feedstock` |
| `prepare_sector_network.add_industry` | load `oil for industry` + link from the oil bus with oil CO2 (T24) | see `oil for industry` |
| `build_industrial_energy_demand_per_node.py` | `methane feedstock`, `oil for industry` = 0 for fallback countries; error if the bundle has no `oil for industry` | the copied PyPSA-Eur values would double their gas and naphtha |
| `prepare_sector_network.add_industry`, `patex.waste_to_energy` (true) with `plastics_eol_co2: false` and `industry.waste_to_energy: true` | HVC stores = PatEx waste-to-energy fuel per country (population split), emptied by waste CHPs only (must-burn, no `HVC to air`), CO2 at PatEx's factor; the rest of the naphtha carbon stays in products | PatEx / inventory / 1990-baseline convention (audit #2, 2026-11-16); the former setting dropped the waste-to-energy CO2 |
| `build_patex_demands`, fallback countries | waste-to-energy = PatEx EU × the country's share of Eurostat non-renewable waste to power and heat | same rule as their industry |
| `config.patex.yaml`: `sector.dac: false` | no direct air capture | scenario choice (user, 2026-11-16); PatEx levers2 has some DAC by 2050 |
| `rules/patex.smk` (`build_patex_report`) | HTML Sankey + PatEx indicators into `results/<run>/patex_report/` (not in `all`) | visual check of the PatEx side, as `build_times_sankey` in pypsa-wal |
| `config/config.patex.yaml`, `config/test/config.patex.yaml` | run configs: `reduce_space_heat_exogenously: false`, machinery shares 0 / 1, plot colour | PatEx demand already includes renovation and machinery electrification |

## Pitfalls already handled

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

## Checks

The report (`patex-pypsa report`) draws every PatEx demand row from fuel to PyPSA-Eur input
and reconciles each PyPSA-Eur node with the bundle (levers 2, all horizons: ratio 1).

`scripts/check_network_ledger.py` compares a solved or composed network with the bundle:
loads per carrier and country, process emissions, EV fleet, building useful heat,
district heat [TWh], district heating share and loss rate, cooking per fuel, CO2 intensities. BE 2030 test (2026-11-06): all 1.0000.
