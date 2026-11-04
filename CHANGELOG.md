# Changelog

What changed and why, in this repository **and in the linked models** (pypsa-eur fork,
PatEx). One entry per merge into `master`. Details: `git log`.

## pypsa-eur fork (branch `develop`)

Fork: `IntSusEnergySystems/PyPSA-Eur-CANEU`, cloned to `../../PyPSA-Eur-CANEU`.

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
  bundle, 10 nodes, 3h, solve memory 60 GB, Gurobi 32 threads).

## PatEx

Not modified. Used as is (`patex run`, dataset `47.x.4` on S3).

## PATEX_PyPSA

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
