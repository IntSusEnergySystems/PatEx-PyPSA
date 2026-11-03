# TODO

Backlog of the PatEx → PyPSA-Eur soft-link. Reasons and data are in
[SOFTLINKING_PLAN.md](SOFTLINKING_PLAN.md) (`Qn` = open question there). Update this file
at the end of every task: tick, add, or move items to "Done" with the commit.

## Next

> Session handover (decisions waiting, implementation plans): `../private_notes/NEXT_SESSION.md`
> (outside git). T18 and T19 below: proposal made, **wait for the user's confirmation**.

- [ ] **T5 Push** (needs the user's written consent in the chat): remotes are set
  (`origin` = `IntSusEnergySystems/PatEx-PyPSA` and `IntSusEnergySystems/PyPSA-Eur-CANEU`,
  SSH key `id_ed25519` authenticates). To push: `master` and `develop` of both repos.
- [ ] **T14 Multi-country test run**: the test cutout (`be-03-2013-era5`) only covers BE.
  Needs a larger ERA5 cutout (download, several GB) for e.g. BE+NL+DE+FR, then
  `check_network_ledger.py` per country, and one myopic run 2030–2050.
- [ ] **T15 Shipping fuel mix from PatEx**: like land transport, set the shipping loads
  per fuel from PatEx bunkers-marine + IWW by carrier (today: PyPSA-Eur default shares,
  the energy then differs from PatEx by the fuel efficiencies, −2 % on BE 2030). Same
  question for hydrogen rail and gas road, served as oil now.
- [ ] **T16 EV battery of PHEVs**: the EV fleet counts BEV + PHEV cars and vans with
  PyPSA-Eur's car battery (`bev_energy` 50 kWh). PHEVs have ~15 kWh: smart charging and
  V2G may be overestimated where PHEVs dominate (e.g. BE).
  Option: count PHEVs × 15/50 for the DSM store only.

- [ ] **T18 Non-electric cooking is lost**: PatEx gas/oil/biomass/H2 cooking is exported as `total {residential,services} cooking`, but
  PyPSA-Eur has no load for it (upstream gap too). Options: a gas load (CO2 counted), or
  add it to building heat. Decision needed.
- [ ] **T19 District heating losses**: PatEx exports delivered heat and adds network
  losses in its supply module (`network-losses[%]` per country); PyPSA-Eur adds `district_heating_loss` 15 % EU-wide on the
  same base, so no double count. Option: PatEx losses per country instead of 15 %.
  (Figures: `../private_notes/FINDINGS.md`.)

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
  shipping hooks (`pypsa_eur_integration/README.md`).
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
