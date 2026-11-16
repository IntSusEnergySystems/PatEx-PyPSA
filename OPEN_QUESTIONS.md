# Open questions of the PatEx → PyPSA-Eur soft-link

Only the questions that are still open. What is passed and why is in the fork's
`docs/<sector>.md` (data flow and "Why" per sector) and in [MODEL_CHANGES.md](MODEL_CHANGES.md);
the work items are in [TODO.md](TODO.md) (`Tn`). Close a question by moving its answer to
the sector doc and deleting it here.

> **Figures.** PatEx outputs and Climact dataset values are not public: the numbers
> behind these questions are in `../private_notes/FINDINGS.md` (outside git).
> Only PyPSA-Eur and JRC-IDEES values are quoted here.

## For Climact

- **Q22 Heat-pump COP and ambient heat (2026-11-16, audit #4; Julien asks Climact).**
  (a) With levers 2, the `elec-hp` efficiency rows of `bld energy-efficiency` bring the
  heat-pump COP (useful / electricity) *down* over time in every country checked
  (figures in `FINDINGS.md`), with the ambient row rising to keep 1/eff_el + 1/eff_amb = 1. Is that
  intended (lever level 2 trajectory, or a data issue)? It sets PatEx's electricity
  for heating; PyPSA-Eur uses its own COPs and is not affected. (b) After calibration,
  the ambient heat of residential space heating implies more heat-pump electricity
  than PatEx reports for heating in some countries (DE, DK, NL): electricity and
  ambient heat are calibrated separately. Which one is right? The link counts all that
  electricity as heat pump and its output as electricity + ambient heat.
- **Q3 Naphtha (T8).** Is `naphtha` = all industry liquids incl. feedstock the right
  reading? PyPSA-Eur emits all naphtha carbon, as process share or at end of life.
- **Q5 Aviation and navigation boundaries (T9).** PatEx has no domestic aviation for BE
  (PyPSA-Eur: 1.55 TWh in 2021) and more international aviation than PyPSA-Eur: is
  domestic aviation inside the bunkers? Same for maritime: is domestic maritime in IWW or
  in bunkers-marine? (PyPSA-Eur splits international navigation over ports with
  `shipping_demand.csv`.)
- **Q9 Farm bioenergy (T7).** PatEx agriculture has no base-year solid biomass, biogas or
  biodiesel (bio carriers only appear through the fuel switch), so agriculture heat is
  below JRC-IDEES. Out on purpose (counted elsewhere, e.g. in the bioenergy balance) or
  missing? If missing: add the JRC-IDEES base-year bio energy, held constant.
- **Q10 Residential water heating.** Which source is it calibrated on? PatEx space + water
  matches JRC-IDEES, but the split differs from PyPSA-Eur, which takes Eurostat
  `nrg_d_hhq` (BE water 11.7 TWh vs 8.9 in JRC-IDEES; PatEx in between). Small impact
  (same heat buses, only the profile differs). PyPSA-Eur's own BE value drops to 6.6 TWh
  in 2023 (11.9 in 2022), which matters for the fallback countries.
- **Q11 District heating trends (T17).** The district heating share falls sharply in some
  Nordic and Baltic countries between 2021 and 2050. Intended?
- **Q12 Chlor-alkali hydrogen (T22).** PatEx has no chlorine material and no by-product
  hydrogen (about 3 % of EU hydrogen today, see `docs/industry.md`). Represent it or not?
- **Q13 Plastics end of life (T23).** Settled for the link (audit #2, 2026-11-16): inventory
  convention, PatEx's non-renewable waste-to-energy burned in waste CHPs, the rest of the
  naphtha carbon kept in products, CRF 5.C out of model and baseline. Open for CAN /
  Climact: (a) PAC 2.0 target scope for waste incineration without energy recovery;
  (b) bio / synthetic carbon in products counts as removed in PyPSA's oil pool, PatEx
  gives olefin feedstock no credit (factor 0, other industries 0.75): keep, or book
  products as fossil first?
- **Q14 Methanol and ammonia ships (T15).** PatEx shipping (IWW and bunkers-marine) runs on
  marine fuel oil (fossil, bio, synthetic), electricity and hydrogen only. Methanol and
  ammonia are expected to take a large share of shipping fuel by 2040–2050 (PyPSA-Eur's
  default: methanol 55 % in 2040, 80 % in 2045). Will PatEx add them? The link takes the
  fuel split from PatEx, so without them PyPSA-Eur has no methanol ships in PatEx
  countries; ammonia ships would need a new load in PyPSA-Eur.
- **Q20 Methanol final demand (2026-11-12; Julien asks Climact).** PatEx has no methanol
  demand: chemical methanol sits in "chemical-other" (no production figure), e-methanol
  is only a supply route of synthetic liquids, e-MTO is 0 in levers2. Request: a methanol
  final demand (chemicals, and as a fuel, e.g. shipping, see Q14), so that PyPSA-Eur
  optimises its route as for ammonia. Until then nothing changes for methanol.
- **Q21 Ammonia process CO2 and urea (2026-11-12).** PatEx's ammonia process CO2 per MWh
  of feedstock gas is above the carbon natural gas contains, and urea application CO2 is
  also booked in agriculture (3H): is the ammonia factor gross (urea carbon counted
  twice) or does it include something else? No effect on the model since the ammonia
  route is optimised (PyPSA-Eur computes the reforming CO2), but it matters for PatEx's
  own totals.
- **Q15 PAC 2.0 lever file (T6)** → `runs/pac2/patex/levers.json` (runs use levers = 2).
- **Q17 Fossil imports and domestic production (T29).** For gas and coal, PatEx imports
  `demand × energy-net-import-refineries[%]` and books the rest as primary production,
  also where a country has no resource (coal in Belgium). What do the lever's values
  stand for, and will PAC 2.0 set them per country? Until then the soft-link adds the
  production above today's (Eurostat) to the import cap.
- **Q19 PHEV fleet (T16).** In some countries PatEx's plug-in fleet is mostly PHEVs, with
  battery-electric cars falling to 2050 (figures in FINDINGS). Intended?
- **Q18 Bioenergy imports (T29).** Gross imports by origin (`agr_bio-energy-production-by-
  energy-carrier-origin`): some countries import far more biogas than their gas use
  (figures in FINDINGS). Expected? Only one country imports electricity: is electricity
  trade switched off elsewhere?

## For CAN

- **Q16 Scenario settings (T11, T28–T34).** CO2 target (EU or national, or PatEx's own
  emission trajectory per country), nuclear (rules set by the user on 2026-11-07, T34: one
  10-year extension, 50 years default; new build allowed anywhere?), CCS (fossil CCS allowed?),
  import limits (electricity and per fuel), cross-border capacities (TYNDP?). The relative
  cap's 1990 baseline is the CO2-only inventory; the model counts physical carbon (no CRF
  calibration, see the fork's `docs/energy.md`), so the scope differs on refining of
  exported products, steel coke ovens / blast-furnace gases, fugitive emissions, PatEx's
  CO2e process emissions, plastics end of life, bunkers. A strict cap on a few countries
  can be infeasible (BE-LU-NL 2030, T20).

## Ours

- **Q8 Fallback countries' heat (T12).** The 9 countries in `patex.fallback_countries` keep
  PyPSA-Eur demands for the `energy_totals_year` (2023), the same for every horizon; with
  `reduce_space_heat_exogenously: false` their heat stays at today's level up to 2050.
  Keep (simple, conservative) or apply PyPSA-Eur's reduction to them only (small hook)?
  GB and CH weigh the most (interconnections with FR, BE, DE, IT).
