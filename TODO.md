# TODO

Backlog of the PatEx → PyPSA-Eur soft-link. Open questions (`Qn`) are in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), reasons per sector in the fork's `docs/<sector>.md`. Update this file
at the end of every task: tick, add, or move items to "Done" with the commit.

## Next

> Session handover (decisions waiting, implementation plans): `../private_notes/NEXT_SESSION.md`
> (outside git).

- [ ] **T5 Push** (needs the user's written consent in the chat): `develop` of both repos
  pushed on 2026-11-06 (before T18/T19); later commits are local
  (`git log origin/develop..develop`). SSH key `id_ed25519` authenticates.
- [ ] **T36 nic6 run BE-LU-NL, CO2 cap 50 % of 1990, 24h, with the import limits (T29)**:
  overlay `config/patex/co2-cap-50-24h.yaml`; bundle the fork / PATEX_PyPSA commits since the
  cluster's (fork `8c38b995`, PATEX_PyPSA `1aa8cf4`) and the re-exported `levers2` bundle;
  ledger (cooking, DH loss rate, supply caps), report (pypsa2html `can-climact`), publish.
### System constraints from PyPSA-Wal (decided 2026-11-05; general, every country)

Ported in this order, each as an option behind `patex.enable` with its data retrieved
online (rule + source + date in the fork's `docs/`), never hand-written per country.
PyPSA-Wal (`../../TIMES2PYPSA/pypsa-wal`, Belgian data) is the reference for the code.

- [ ] **T28 National CO2 caps** (with T11), keeping the EU cap as an option: per-country
  cap on the CO2 of the links located in the country (PyPSA-Wal `add_co2limit_country`).
  Trap: carriers on EU-level buses (oil, methanol, kerosene, shipping, naphtha) carry their
  bio / synthetic credit at EU level; decide where the bio credit is booked (production:
  linear; consumption: non-linear, T35 does it only in reporting), so a national cap charges the fossil CO2 without the
  credit (PyPSA-Wal excluded aviation). Data: national targets (CAN) or PatEx trajectory.
- [ ] **T30 Cross-border capacity limits** per border (NTC ceilings, grid expansion up to
  them; PyPSA-Wal `set_NTCs.py`). Data: ENTSO-E TYNDP 2024 for every border.
- [x] **T29 Import limits per fuel**: done 2026-11-07 as gross imports per fuel for the
  whole region (user's decision), see Done. Left: stricter treatment of PatEx's domestic
  "production" once the PAC 2.0 scenario is checked (now: gap added to the import cap);
  electricity self-sufficiency per country (PyPSA-Wal `add_selfsufficiency_constraints`),
  if CAN wants it (Q16).
- [ ] **T31 Offshore wind potentials** per country from marine spatial plans (upstream's
  2 MW/km² is below installed capacity in BE, NL, DE). Data: national maritime spatial
  plans / EU MSP platform.
- [ ] **T32 CO2 storage limits**: per-site cap (upstream's 25 Gt clip is too large) and a
  deployment ramp per country. Data: CO2StoP / national CCS strategies.
- [ ] (undecided) **T33 Build-rate limits** for renewables per country (IRENA additions ×
  factor, PyPSA-Wal `res_growth_allowance`).
- [ ] **T34 Nuclear** (PyPSA-Wal: `conventional.inflexible_nuclear`, `nuclear_helper.py`,
  `extendable_nuclear_links`, commits `506106f5`, `bbc9450e`), general for every country:
  - existing fleet and closure dates per country from national policy (PyPSA-Eur's
    lifetimes: BE already 0 in 2030 although Doel 4 / Tihange 3 run to 2035; NL Borssele
    gone by 2040 although an extension is planned); lifetime extension allowed once;
    data: a maintained dataset or national decisions, with source and date;
  - must-run: `p_min_pu = p_max_pu − 0.10` (option; today fully flexible from 0 to 100 %
    each hour, which underestimates the flexibility needs);
  - new build only where / when allowed per node and horizon (none in PAC 2.0: confirm
    with CAN), nuclear as Links only (no Generator duplicate), no 10 MW threshold drop.
- [ ] **T16 EV battery of PHEVs**: the EV fleet counts BEV + PHEV cars and vans with
  PyPSA-Eur's car battery (`bev_energy` 50 kWh). PHEVs have ~15 kWh: smart charging and
  V2G may be overestimated where PHEVs dominate (e.g. BE).
  Option: count PHEVs × 15/50 for the DSM store only.

- [ ] **T20 First multi-country run on nic6 (BE, LU, NL)**, `config/patex/levers2-be-lu-nl.yaml`
  (levers 2, 10 nodes, 3h, myopic 2030-2050). With PyPSA-Eur's default CO2 budget the
  2030 solve is **infeasible** → waits for T11 (CO2 target; option: PatEx's own emission
  trajectory per country, "PatEx at maximum"). Technical test without cap
  (`config/patex/test-no-co2-cap.yaml`) solved all horizons; ledger 1.0000 for BE, LU, NL
  except shipping (0.98 → 0.87 in 2050, T15) and district heating (T19). **Rerun 2026-11-05
  after T15** (fork `0a57d75d`): ledger 1.0000 for every load, every horizon, BE, LU, NL
  (shipping included), except district heating losses (T19); report republished at
  caneurope `pypsa_results/patex-levers2-be-lu-nl-test-no-co2-cap/` (test; Sankey
  electricity gap = new T15 carriers, T21).
- [ ] **T21 pypsa2html on the current PyPSA-Eur layout**: done on the local branch
  `can-climact` of `../../pypsa2html` (**never push**: it would change other projects'
  reports). Single-header CSVs, resource names, Sankey balance (methanolisation
  electricity, nuclear Generator+Link, heat vents, biomass-to-methanol, oil refining,
  bioliquids, PHS, feedstock gas; process nodes for multi-input conversions:
  methanolisation, Haber-Bosch, electrobiofuels). Left: LU electricity −0.2 TWh (3 %) and heat
  < 0.09 TWh per node: all came from `model.flow_threshold` (0.1 TWh); set to 0.01 in
  our config generator, the graph now balances. **Since T15** the electricity node is off by
  the new loads (`rail electricity`, `aviation electricity`, `shipping electricity`, plus
  `H2 for rail`, `land transport gas`), missing from `data/carrier_flows_energy.csv`;
  `_rail_demand` (rail from energy totals) becomes redundant. Fixed 2026-11-05
  (pypsa2html `76467b0`): carriers mapped, no rail estimate when the network has a rail
  load; BE-LU-NL Sankey balances again.

- [ ] **T23 Plastics end-of-life CO2** — PatEx convention applied (user, 2026-11-04,
  fork `fcfd51a8`): `patex.plastics_eol_co2: false` (HVC to air emits nothing),
  `industry.waste_to_energy: true` (waste CHPs burn plastics, CO2 counted). Still a
  **talking point with Climact / CAN**. To validate on the next nic6 run (ledger,
  waste CHP use). Figures: `../private_notes/FINDINGS.md`.

## Waiting for Climact / CAN

- [ ] **T6 PAC 2.0 lever file** → `runs/pac2/patex/levers.json` (runs use levers = 2 so far).
- [ ] **T7 Farm bioenergy (Q9)**: absent from the PatEx base year (heat lower than IDEES).
  If missing on purpose, nothing to do. Otherwise add IDEES 2021 bio energy, held constant.
- [ ] **T8 Industry (Q3)**: is `naphtha` = all industry liquids incl. feedstock the right
  reading? (PyPSA-Eur emits all its carbon, as process share or at end of life.)
- [ ] **T17 District heating trends** (user checks with Climact): sharp falls in some
  Nordic and Baltic countries between 2021 and 2050 in PatEx.
- [ ] **T9 Aviation (Q5)**: no PatEx BE domestic aviation vs 1.55 TWh in PyPSA-Eur. Is
  domestic aviation inside the bunkers? Same question for domestic maritime.
- [ ] **T11 Scenario settings (plan step 5)**: CO₂ target (EU or national), nuclear,
  CCS, import limits. The relative cap's 1990 baseline is the inventory (CO2 only): make the
  model's total comparable (fork `docs/energy.md`, T27 decision): carbon missing from the
  physical count (steel coke ovens / blast-furnace gases, fugitive 1.B, refining of exported
  products), PatEx's CO2e (process emissions) vs CO2-only baseline.

## Later

- [ ] **T12 Fallback countries' heat (Q8)**: with `reduce_space_heat_exogenously: false`
  they stay at 2023 demand until 2050. Keep, or apply the reduction to them only.
- [ ] **T13 Compare back** PyPSA supply results with PatEx `elc_*` outputs (plan step 8).

## Done

- 2026-11-07 T29 Import limits (fork option `import_limits`, standalone; PatEx hook
  `patex.import_limits`, bundle `patex_supply_{h}.csv`): caps on gross imports per fuel
  summed over the modelled countries (gas, oil, coal, H2, NH3, synthetic gas / oil,
  methanol, solid biomass, biogas, bioliquids), as `GlobalConstraint`s solved in
  `solve_network` (dual in `mu`); gas fields split from the entries; new carbon-neutral
  `import biogas` / `import bioliquids`; domestic gas / oil / coal capped at min(PatEx
  production, today's Eurostat production), the rest of PatEx's production added to the
  import cap and logged. BE test: caps hold, biogas binding. pypsa2html maps the new carriers.
- 2026-11-06 T19 District heating losses from PatEx: rate per country (losses / delivered heat,
  `elc_energy-sankey-detailed`) on the building + low-temperature industry heat of each urban
  central bus, as load `urban central heat losses`; `district_heating_loss` 0 for PatEx
  countries (fallback countries keep 15 %). BE test: building heat 1.0000, rate = PatEx's.
- 2026-11-06 T18 Non-electric cooking: flat loads per fuel (gas, oil, coal, solid biomass via
  links with the fuel's CO2; H2 on the H2 bus), PatEx countries only. BE test ledger 1.0000.
- 2026-11-05 T35 `scripts/co2_by_sector.py`: CO2 per country and sector, bio credits moved to
  the consumers of the gas / oil / methanol pools (mass balance, total checked); test.
- 2026-11-05 Gas storage = working gas (upstream reads the cushion gas: BE 15x too small,
  NL 4x too large), no 98 % clip (PatEx runs only). BE test: Loenhout 8.2 TWh.
- 2026-11-05 T26 Refinery CO2 per MWh of oil from PatEx (emissions / output), replaces
  `oil_refining_emissions`. T27 PatEx's CRF calibration tried (industry factors per
  country), then **not transferred**: physical factors everywhere, baseline consistency as a
  total in T11 (reasons in the fork's `docs/energy.md`).
- 2026-11-05 T24 Burnt industry oil gets combustion CO2: `naphtha` = liquid feedstock only,
  new `oil for industry` (burnt liquids) = load on the oil bus via a link with oil CO2;
  `methane feedstock` / `oil for industry` = 0 for fallback countries (would have doubled
  their gas / naphtha). BE test ledger 1.0000 (fork, PATEX_PyPSA, pypsa2html mapping).
- 2026-11-05 T15 Every PatEx transport fuel has its own load: shipping fuel split from
  PatEx (energy per fuel, no PyPSA-Eur shares or efficiencies; methanol 0 since PatEx has
  none, Q14), gas road (`land transport gas`, gas bus with CO2), hydrogen rail, rail /
  aviation / shipping electricity (out of the base load). BE 2030 ledger: all 1.0000
  except district heating (T19). Bundle `levers2` re-exported; nic6 needs the new code
  and bundle before the next run.
- 2026-11-05 `SOFTLINKING_PLAN.md` → `OPEN_QUESTIONS.md` (open questions only); settled
  reasons in the fork's `docs/<sector>.md` ("Why").

- 2026-11-04 T14 superseded: runs on nic6 with the pre-built `europe-2013-sarah3-era5`
  cutout (BE-LU-NL, T20).
- 2026-11-04 pypsa2html `flow_threshold` 0.01 in `scripts/pypsa2html_config.py`: the
  BE-LU-NL Sankey balances exactly.
- 2026-11-04 T22 Industry hydrogen split by **gross uses** per node (fork
  `build_industrial_energy_demand_per_node.py`); chlorine by-product not introduced
  (user). Question for Climact: by-product hydrogen absent from PatEx.
- 2026-11-04 nic6 set up (`../../CLUSTER_NIC6.md`): pixi env on scratch, Gurobi token
  license, `scripts/cluster/` (env, generic Slurm job), `scripts/pypsa2html_config.py`
  (country groups from `n.buses.country`).
- 2026-11-04 Docs cleanup (CHANGELOG); report published at the CAN Europe server
  (address in `../../CLAUDE.md`).

- 2026-11-03 Report (`patex-pypsa report`, rule `build_patex_report`): Sankey PatEx → PyPSA-Eur
  per year with country selector and reconciliation (all nodes ratio 1), PatEx indicator
  pages and catalogue, after TIMES_PyPSA. Fork pushed to origin (`46b4d243`).

- 2026-11-03 Remaining PatEx outputs (`MODEL_CHANGES.md`): process emissions and
  solid-waste CO2, feedstock gas without CO2, `ammonia`/`methanol` = 0, CO2 intensity of
  gas/oil/coal from PatEx factors (`--dataset`), district heating share, EV fleet,
  electric aviation/shipping in the base load. Land transport loads set directly per fuel
  (no distance conversion). Q2 closed (no non-electric "others" in PatEx).
  BE 2030 ledger: all 1.0000 except shipping 0.98 and district heating losses.

- 2026-11-03 T1 Agriculture machinery: `agriculture_machinery_electric_share: 0`,
  `oil_share: 1` in `config/config.patex.yaml` (fork).
- 2026-11-03 T2 Hooks applied on PyPSA-Eur-CANEU `develop`, plus land-transport and
  shipping hooks (README, "PyPSA-Eur side").
- 2026-11-03 T3 Test run BE 2030 (one week, `config/test/config.patex.yaml`): ledger
  holds, all demands = PatEx within 0.2 % (shipping −2 %, building heat +2.4 % = district
  heating loss, both expected). `scripts/check_network_ledger.py`.
- 2026-11-03 T4 Land transport per node from PatEx (distance + EV/FC/ICE shares, not
  the energy ratio), new export column `hydrogen road`.
- 2026-11-03 Moved to the fork `IntSusEnergySystems/PyPSA-Eur-CANEU`
  (`../../PyPSA-Eur-CANEU`); old `pypsa-eur/` checkout removed (its datasets moved over).
- 2026-11-02 Agriculture split by use with JRC-IDEES shares (`2941a7d`).
- 2026-11-02 Package, rules, export, checks, integration files (`ddf5386`).
- 2026-11-02 Resolved: PatEx is calibrated on JRC-IDEES (user). The residential
  space/water gap comes from PyPSA-Eur's Eurostat household override, not from PatEx.
