# TODO

Backlog of the PatEx → PyPSA-Eur soft-link. Open questions (`Qn`) are in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), reasons per sector in the fork's `docs/<sector>.md`. Update this file
at the end of every task: tick, add, or move items to "Done" with the commit.

## Next

> Session handover (state, decisions waiting): `../private_notes/NEXT_SESSION.md` (outside git).

- [ ] **T5 Push** (needs the user's written consent in the chat): `develop` of both repos
  pushed on 2026-11-06; later commits are local (`git log origin/develop..develop`).
- [ ] **T16 EV battery of PHEVs**: the EV fleet counts BEV + PHEV cars and vans with
  PyPSA-Eur's car battery (`bev_energy` 50 kWh). PHEVs have ~15 kWh: smart charging and
  V2G may be overestimated where PHEVs dominate (e.g. BE). Option: PHEVs × 15/50 for the
  DSM store only.
- [ ] **T23 Plastics end-of-life CO2**: PatEx convention applied (`patex.plastics_eol_co2:
  false`, `industry.waste_to_energy: true`); talking point with Climact / CAN.
- Follow-ups: T29 stricter use of PatEx's domestic "production" once PAC 2.0 is checked
  (now: the part above today's Eurostat production is added to the import cap);
  electricity self-sufficiency per country if CAN wants it (Q16). T34 new build (none; CAN,
  Q16), Belgium's legal end date after the 2025 repeal (2035 kept), Sizewell C once under
  construction in PRIS, long-term-operation investment cost.

### System constraints from PyPSA-Wal (decided 2026-11-05; general, every country)

Each as an option with its data retrieved online (rule + source + date in the fork's
`docs/`), never hand-written per country. Reference code: `../../TIMES2PYPSA/pypsa-wal`.

- [ ] **T28 National CO2 caps** (with T11), EU cap kept as an option (PyPSA-Wal
  `add_co2limit_country`). Trap: carriers on EU-level buses (oil, methanol, kerosene,
  shipping, naphtha) carry their bio / synthetic credit at EU level; decide where the bio
  credit is booked (T35 does it in reporting only). Data: national targets (CAN) or PatEx.
- [ ] **T30 Cross-border capacity limits** per border (NTC ceilings, PyPSA-Wal
  `set_NTCs.py`). Data: ENTSO-E TYNDP 2024.
- [ ] **T31 Offshore wind potentials** per country from marine spatial plans (upstream's
  2 MW/km² is below installed capacity in BE, NL, DE). Data: EU MSP platform.
- [ ] **T32 CO2 storage limits**: per-site cap (upstream's 25 Gt clip is too large) and a
  deployment ramp per country. Data: CO2StoP / national CCS strategies.
- [ ] (undecided) **T33 Build-rate limits** for renewables per country (IRENA additions ×
  factor, PyPSA-Wal `res_growth_allowance`).

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

One line per item; details in [CHANGELOG.md](CHANGELOG.md) and the commits.

- 2026-11-07 T37 T36 rerun with the nuclear fleet on nic6 (whole pipeline, 43 steps, no
  error after the empty-fleet fix): optimal at every horizon, ledger 1.0000, CO2 = cap,
  report republished at the same address.
- 2026-11-07 T36 BE-LU-NL on nic6, CO2 cap 50 % of 1990, 24h, import limits: optimal at
  every horizon, ledger 1.0000, report at caneurope
  `pypsa_results/patex-levers2-be-lu-nl-co2-cap-50-24h/` (every Sankey node balances).
- 2026-11-07 T34 Nuclear (fork `nuclear_fleet`): one link per reactor, data from IAEA PRIS
  (112 operating, 4 under construction) and official end dates; one 10-year extension, not
  used within 4 years of its end, 50 years default, must-run 0.10.
- 2026-11-07 T29 Import limits (fork `import_limits`, PatEx `patex_supply_{h}.csv`): gross
  imports per fuel for the whole region; domestic supply capped at today's production.
- 2026-11-06 T18 non-electric cooking per fuel; T19 PatEx district heating loss rate.
- 2026-11-05 T15 transport fuels, T24 burnt industry oil, T26 refinery CO2, T27 CRF
  calibration not transferred, T35 CO2 per sector, gas storage fix (working gas).
- 2026-11-04/05 T20 first BE-LU-NL runs on nic6 (default 2030 cap infeasible, test without
  cap); T21 pypsa2html on the current PyPSA-Eur layout (local branch `can-climact`); T22
  industry hydrogen by gross uses; nic6 set up; T14 superseded.
- 2026-11-02/03 Package, export, report, hooks (T1–T4), move to the fork, agriculture split.
