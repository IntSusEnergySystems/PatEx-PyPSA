# TODO

Backlog of the PatEx → PyPSA-Eur soft-link. Open questions (`Qn`) are in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), reasons per sector in the fork's `docs/<sector>.md`,
history in [CHANGELOG.md](CHANGELOG.md). Update this file at the end of every task: tick,
add, or move items to "Done" with the commit.

> Session handover (state, runs, decisions waiting): `../private_notes/NEXT_SESSION.md`
> (outside git). Code audit of 2026-11-12: `../private_notes/AUDIT_2026-11-12.md`.

## Next

- [ ] **Temperature shift** (`patex.temperature_shift`, +0.3 / +0.7 °C on the 2023 weather
  year): check against the IPCC AR6 Atlas (Western & Central Europe, SSP2-4.5,
  2021–2040 / 2041–2060 vs 1995–2014), possibly seasonal shifts.
- [ ] **T5 Push**: only with the user's written consent in the chat (`master` and
  `develop` last merged and pushed 2026-11-16, user's go).
- [ ] **Code audit #6–#21** (`AUDIT_2026-11-12.md`), one at a time with Julien; next #6
  (existing PV split rooftop / ground per country).
- [ ] **Report of the reference run** (pypsa2html, 3h for published results: the 24h
  resolution removes batteries and distorts solar, `REPORT_REVIEW.md`), then publish.
- [ ] Options for later runs: cold-year sensitivity (2010) for heating peaks; NESO embedded
  wind and solar to correct GB's hourly shape (NESO National Demand excludes them);
  national production data for fallback countries' industry (NO aluminium, alumina).

## Open choices for Julien

- **Ground PV potential** (fork `850f028c`): landscape designations (IUCN V: DE
  Landschaftsschutzgebiete, FR PNR, UK national parks) out (now) or eligible
  (`--keep-landscape`); Flanders' note and IE's CAP25 split in official texts; per-node
  split; KBA (data on request).
- **Rooftop PV**: policy floor (option A); later per-building JRC GeoPackages instead of the
  population split; deployable share as a sensitivity; GB national data.
- **Grid costs**: reporting layers (existing grid, intra-country transmission) per country;
  WACC of DE, FR, NL, DK, NO, LU from the primary decisions.
- **Supply limits**: T29 stricter use of PatEx's domestic "production" once PAC 2.0 is
  checked (now: the part above today's Eurostat production is added to the import cap);
  electricity imports into the EU uncapped; electricity self-sufficiency per country if
  CAN wants it (Q16).
- **CO2 storage (T32)**: refresh `data/co2_storage_projects.csv` from the IEA 2026 file
  (IEA account, `--xlsx`); CO2 network to the coast inside a country not costed.
- **Nuclear (T34)**: new build (CAN, Q16); Belgium's legal end date after the 2025 repeal
  (2035 kept); Sizewell C once under construction in PRIS; long-term-operation cost.

### System constraints from PyPSA-Wal (decided 2026-11-05; general, every country)

Each as an option with its data retrieved online (rule + source + date in the fork's
`docs/`), never hand-written per country. Reference code: `../../TIMES2PYPSA/pypsa-wal`.

- [ ] **T28 National CO2 caps** (with T11), EU cap kept as an option (PyPSA-Wal
  `add_co2limit_country`). Trap: carriers on EU-level buses (oil, methanol, kerosene,
  shipping, naphtha) carry their bio / synthetic credit at EU level; decide where the bio
  credit is booked (T35 does it in reporting only). Data: national targets (CAN) or PatEx.
- [ ] (later) **T33 Build-rate limits** for renewables per country (IRENA additions ×
  factor, PyPSA-Wal `res_growth_allowance`): not for now (user, 2026-11-09: let the model
  invest up to the potentials after 2030 and see).

## Waiting for Climact / CAN

- [ ] **T6 PAC 2.0 lever file** → `runs/pac2/patex/levers.json` (runs use levers = 2 so far).
- [ ] **T7 Farm bioenergy (Q9)**, **T8 naphtha (Q3)**, **T9 aviation / navigation
  boundaries (Q5)**, **T17 district heating trends (Q11)**, **T22 chlor-alkali H2 (Q12)**,
  **T23 plastics end of life (Q13)**, **Q14 / Q20** methanol and ammonia, **Q22** heat-pump
  COP and ambient heat.
- [ ] **T11 Scenario settings (Q16)**: CO₂ target (EU or national), nuclear, CCS, import
  limits. The relative cap's 1990 baseline is the inventory (CO2 only): make the model's
  total comparable (fork `docs/energy.md`): carbon missing from the physical count (steel
  coke ovens / blast-furnace gases, fugitive 1.B, refining of exported products), PatEx's
  CO2e (process emissions) vs CO2-only baseline (audit #10).

## Later

- [ ] **T12 Fallback countries' heat (Q8)**: with `reduce_space_heat_exogenously: false`
  they stay at 2023 demand until 2050. Keep, or apply the reduction to them only.
- [ ] **T13 Compare back** PyPSA supply results with PatEx `elc_*` outputs (plan step 8).

## Done

One line per item; details in [CHANGELOG.md](CHANGELOG.md) and the commits.

- 2026-11-16 `develop` merged into `master` and pushed (both repos, user's go) after run
  `...-24h-2023-shift` with the GB fix validated (ledger 1, GB residual = DUKES level).
- 2026-11-16 GB load scaled to DUKES "electricity available" (`patex.gb_load_dukes`, fork
  `149a9595`).
- 2026-11-16 Climate of the horizon (`patex.temperature_shift`, fork `d42b3a40`); run
  `...-24h-2023-shift` (2023 weather, +0.3 / +0.7 °C): cooling peaks about halved vs 2013.
- 2026-11-16 Audit #5b: electric cooling as its own load, Hotmaps residential / tertiary
  profiles, JRC-IDEES today's cooling (fork `ebd5b248`); negative base-load hours set to 0.
- 2026-11-16 Audit #5: base load = measured load − PyPSA-Eur's own electric heating
  (fork `367127cd`).
- 2026-11-16 Audit #4: building heat = PatEx useful heat, DH share on useful heat (fork
  `4ca89cac`). Audit #3: offshore class potentials scaled to the cap (fork `570f70c5`).
  Runs `...-24h-audit` validated #3–#5b; DAC off (`sector.dac: false`) stays feasible.
- 2026-11-16 Audit #2: PatEx waste-to-energy as a must-burn in waste CHPs, naphtha carbon
  kept in products (fork `af990b94`).
- 2026-11-12 Audit #1 / #1b / #1c: GB industry year, fallback countries on PatEx's EU
  trend, ammonia route optimised by PyPSA-Eur (forks `d8b6c1b9`, `4226f072`, `1ffbdab0`).
- 2026-11-12 Rooftop PV potential = JRC 2026 technical potential, cap 50 % (fork
  `850885ed`); ground PV potential, user's rules, stricter (forks `fa2d2e5f`, `850f028c`).
- 2026-11-10 Network costs: one regulated discount rate (4 % real), distribution and
  rooftop hosting costs, industry at transmission level (forks `6c4e26a1`, `7ed4fe29`).
- 2026-11-10 GB / NO / CH import caps = EU import cap per person × population
  (`patex.fallback_import_caps`); self-sufficiency page in the report (pypsa2html `ab2ed81`).
- 2026-11-09 T30 cross-border capacity limits, T31 wind and solar limits, T32 CO2 storage,
  T16 EV flexibility (Elia AdeqFlex).
- 2026-11-07 T29 import limits, T34 nuclear fleet (IAEA PRIS), T36–T37 first BE-LU-NL runs
  with a CO2 cap on nic6.
- 2026-11-06 T18 non-electric cooking per fuel; T19 PatEx district heating loss rate.
- 2026-11-05 T15 transport fuels, T24 burnt industry oil, T26 refinery CO2, T27 CRF
  calibration not transferred, T35 CO2 per sector, gas storage fix (working gas).
- 2026-11-04/05 T20 first runs on nic6; T21 pypsa2html on the current PyPSA-Eur layout
  (local branch `can-climact`); T22 industry hydrogen by gross uses; nic6 set up.
- 2026-11-02/03 Package, export, report, hooks (T1–T4), move to the fork, agriculture split.
