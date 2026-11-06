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
and, for the CO2 factors only, the dataset.

## PatEx → bundle (this repository, `data/extraction_rules.csv` and `patex_pypsa/`)

| PyPSA-Eur input | From PatEx | Why this way |
|---|---|---|
| Building heat (`total/electricity {residential,services} {space,water}`) | `bld_energy-demand-incl-district-heating` − ambient heat | final energy incl. district heat, the base of PyPSA-Eur's heat totals; ambient heat is modelled by PyPSA through heat-pump COPs |
| `electricity base load` (new) | building electricity − electric heating | residual hourly load after PyPSA-Eur's explicit electric heating |
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
| `district heat share` (new) | district heat / building heat (final) | replaces PyPSA-Eur's today share + progress |
| `patex_supply_{h}.csv` (new, T29): gross imports per fuel, `<fuel> production` | supply Sankey `source = import` / `primary-production`; bioenergy `origin = import` | caps on imports per fuel for the whole region (`import_limits`); domestic production capped at min(PatEx, today's Eurostat), the rest added to the import cap |
| `district heating loss` (new, T19) | heat distribution losses / heat delivered (`elc_energy-sankey-detailed`) = PatEx `network-losses[%]` | PatEx's rate per country on all network heat (buildings and industry), replaces PyPSA-Eur's 15 % on building heat only |
| `{gas,oil,solid biomass,coal,hydrogen} cooking` (new, T18) | non-electric cooking per fuel, residential + services | PyPSA-Eur has no cooking load: the fuel and its CO2 were missing |
| `number evs` (new) | cars and vans BEV + PHEV | sizes chargers, smart charging, V2G |
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
| `scripts/_patex_config.py`, `config_updates.py`, `config.default.yaml`, schema | `patex:` section (`enable`, `coupling_dir`, `fallback_countries`, `energy_totals`, `industry`, `co2_intensity`, `district_heating`, `base_load`) | config keys must be declared (strict validation) |
| `rules/patex.smk`, `scripts/build_patex_demands.py` | copy and check the bundle per horizon | each run records its PatEx inputs; a missing country fails |
| `rules/compose.smk`, `rules/build_sector.smk` | PatEx inputs wired when enabled | |
| `build_industrial_energy_demand_per_node.py` | industry carriers and process emissions per country from PatEx; hydrogen split over nodes by gross uses | the chlorine by-product (negative in PyPSA-Eur's ratios, absent from PatEx) flipped the split's signs |
| `build_district_heat_share.py` | country share from PatEx, spread like today's share | PatEx sets district heating per horizon |
| `build_gas_input_locations.py`, `prepare_sector_network.add_h2_gas_infrastructure` | existing gas storage = SciGRID working gas (not cushion gas), no 98 % clip | upstream data bug (found in PyPSA-Wal): BE storage 15x too small, NL 4x too large |
| `compose_network.py` | CO2 intensity of gas, oil, coal from the bundle (the `oil refining` row is skipped) | same CO2 per fuel as PatEx |
| `prepare_sector_network.main` | `industry.oil_refining_emissions` from the bundle (T26); error if the row is missing | refinery CO2 per MWh from PatEx |
| `prepare_sector_network.main` | energy totals per country from PatEx (heat, agriculture, aviation, navigation); base load rescaled at the end | |
| `prepare_sector_network.add_land_transport` | EV, fuel-cell, gas and oil loads = PyPSA-Eur hourly profile × PatEx energy per fuel; EV fleet from PatEx | PyPSA-Eur builds road demand once from 2023 energy as a distance; PatEx gives future energy per fuel |
| `prepare_sector_network.add_EVs` | optional `number_evs` sizes chargers / DSM / V2G | instead of share × today's cars |
| `prepare_sector_network.add_ice_cars` | multiply by the share before renaming | allows a per-node share (same result for a scalar) |
| `prepare_sector_network.add_shipping` | international navigation per country from PatEx, port split kept; fuel shares per country from PatEx, energy per fuel without conversion | `shipping_demand.csv` is built from 2023; PyPSA-Eur's shares and efficiencies would change PatEx's fuel mix and energy |
| `prepare_sector_network.add_gas_vehicles` (new) | `land transport gas` load per node, ICE profile, from the gas bus with CO2 | PyPSA-Eur has no gas vehicles |
| `prepare_sector_network.add_patex_transport_loads` (new) | loads `rail electricity`, `aviation electricity`, `shipping electricity` (base-load shape, transmission bus), `H2 for rail` (flat) | PyPSA-Eur has no such loads; each fuel visible in its own load |
| `prepare_sector_network.add_heat` (`no_district_heating_loss`), `add_patex_district_heating_losses` (new) | `district_heating_loss` = 0 for the PatEx countries; load `urban central heat losses` = PatEx rate × building + low-temperature industry heat on each urban central bus (`patex.district_heating`) | see `district heating loss`; losses visible as their own load |
| `prepare_sector_network.add_patex_cooking_loads` (new) | flat loads `gas / oil / coal / solid biomass for cooking` fed by links with the fuel's CO2, `H2 for cooking` on the H2 bus (`patex.energy_totals`) | see `<fuel> cooking` |
| `scripts/_import_limits_config.py`, `prepare_sector_network.add_supply_limits` / `add_domestic_supply` / `add_bio_imports` / `patex_supply_limits`, `add_h2_gas_infrastructure` (`split_gas_production`), `solve_network.add_supply_limits_per_fuel` (T29) | caps on gross imports per fuel (whole region) and domestic gas / oil / coal; gas fields split from the entries; carbon-neutral biogas / bioliquids imports; `import_limits` is standalone (default off), PatEx values with `patex.import_limits` | self-sufficiency scenarios; PatEx imports as upper bounds (fork `docs/energy.md`) |
| `scripts/_nuclear_fleet.py`, `compose_network.py`, `data/nuclear_fleet.csv` (T34) | one link per reactor (official table), no duplicate generators, uranium supply, one 10-year extension (model's choice), not used within 5 years of its end, must-run | upstream double-counts nuclear and keeps generators forever; powerplantmatching is out of date (fork `docs/energy.md`) |
| `prepare_sector_network.add_industry` | load `gas feedstock for industry` on the gas bus, no CO2 | see `methane feedstock` |
| `prepare_sector_network.add_industry` | load `oil for industry` + link from the oil bus with oil CO2 (T24) | see `oil for industry` |
| `build_industrial_energy_demand_per_node.py` | `methane feedstock`, `oil for industry` = 0 for fallback countries; error if the bundle has no `oil for industry` | the copied PyPSA-Eur values would double their gas and naphtha |
| `prepare_sector_network.add_industry`, `patex.plastics_eol_co2` (false) + `industry.waste_to_energy: true` | `HVC to air` emits nothing; waste CHPs burn non-recycled plastics with their CO2 | PatEx / inventory convention: plastics carbon is emitted only where waste is burned |
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
loads per carrier and country, process emissions, EV fleet, district heating share and
loss rate, cooking per fuel, CO2 intensities. BE 2030 test (2026-11-06): all 1.0000.
