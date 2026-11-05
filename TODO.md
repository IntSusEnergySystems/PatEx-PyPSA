# TODO

Backlog of the PatEx → PyPSA-Eur soft-link. Open questions (`Qn`) are in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), reasons per sector in the fork's `docs/<sector>.md`. Update this file
at the end of every task: tick, add, or move items to "Done" with the commit.

## Next

> Session handover (decisions waiting, implementation plans): `../private_notes/NEXT_SESSION.md`
> (outside git). T18 and T19 below: proposal made, **wait for the user's confirmation**.

- [ ] **T5 Push** (needs the user's written consent in the chat): both repos were pushed
  on 2026-11-03; PatEx-PyPSA has local commits since (`git log origin/develop..develop`).
  SSH key `id_ed25519` authenticates.
- [ ] **T24 Burnt industry oil has no CO2** (found 2026-11-05): the `naphtha` column holds
  every industry liquid, feedstock and burnt (olefin cracker fuel, other industries). In
  PyPSA-Eur all of it enters the plastics (HVC) chain; with `plastics_eol_co2: false` the
  non-burned plastics emit nothing, so the CO2 of the burnt oil is lost (BE-LU-NL test
  2030: all HVC to `HVC to air`, waste CHPs unused). Fix (follows the CO2 rule): split
  `naphtha` (feedstock liquids) / new `oil for industry` (excl-feedstock liquids), a load on
  the oil bus through a link with oil CO2, like `gas for industry`; Sankey, ledger, docs.
- [ ] **T25 Plastics burned at end of life**: waste CHPs are optional and `HVC to air` is
  free and emits nothing, so under a cap the model never burns plastics; PatEx has waste
  incineration emissions in power/heat. Decide: force the burned share (PatEx) through
  waste CHPs, or accept.
- [ ] **T26 Refinery CO2**: `oil refining` uses PyPSA-Eur's `oil_refining_emissions`
  (0.013 t/MWh oil); PatEx reports refinery emissions. Option: factor from PatEx
  (refinery emissions / oil throughput) at export, like the fuel factors.
- [ ] **T27 PatEx combustion calibration**: PatEx scales industry combustion emissions to the
  CRF inventories (rates per material, in FINDINGS); PyPSA-Eur uses the raw
  factors. Decide whether the industry factors should carry PatEx's calibration.
- [ ] **T16 EV battery of PHEVs**: the EV fleet counts BEV + PHEV cars and vans with
  PyPSA-Eur's car battery (`bev_energy` 50 kWh). PHEVs have ~15 kWh: smart charging and
  V2G may be overestimated where PHEVs dominate (e.g. BE).
  Option: count PHEVs × 15/50 for the DSM store only.

- [ ] **T18 Non-electric cooking is lost**: PatEx gas/oil/biomass/H2 cooking is exported
  as `total {residential,services} cooking`, but PyPSA-Eur has no load for it (upstream gap
  too). Not heat (user). Proposal: per-carrier cooking loads on the gas / oil / biomass /
  H2 buses, CO2 counted, flat profile (plan in the handover).
- [ ] **T19 District heating losses**: PatEx exports delivered heat and reports network
  losses per country (`elc_energy-sankey-detailed`, heat → distribution-losses, buildings
  and industry); PyPSA-Eur adds `district_heating_loss` 15 % EU-wide on building heat only.
  Proposal (user's idea): loss 0 for PatEx countries + a PatEx loss load on the urban
  central heat bus (plan in the handover).
  (Figures: `../private_notes/FINDINGS.md`.)

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
  CCS, import limits.

## Later

- [ ] **T12 Fallback countries' heat (Q8)**: with `reduce_space_heat_exogenously: false`
  they stay at 2023 demand until 2050. Keep, or apply the reduction to them only.
- [ ] **T13 Compare back** PyPSA supply results with PatEx `elc_*` outputs (plan step 8).

## Done

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
