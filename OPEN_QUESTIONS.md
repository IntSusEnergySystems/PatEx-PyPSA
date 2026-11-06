# Open questions of the PatEx → PyPSA-Eur soft-link

Only the questions that are still open. What is passed and why is in the fork's
`docs/<sector>.md` (data flow and "Why" per sector) and in [MODEL_CHANGES.md](MODEL_CHANGES.md);
the work items are in [TODO.md](TODO.md) (`Tn`). Close a question by moving its answer to
the sector doc and deleting it here.

> **Figures.** PatEx outputs and Climact dataset values are not public: the numbers
> behind these questions are in `../private_notes/FINDINGS.md` (outside git).
> Only PyPSA-Eur and JRC-IDEES values are quoted here.

## For Climact

- **Q1 Heat accounting boundary.** PyPSA-Eur heat columns are *final* energy, converted
  to useful heat with its `heating_efficiencies.csv` (today's carrier mix per country).
  The rules take `incl-district-heating − ambient`. Is that PatEx's final-energy boundary?
  Should PatEx's own heating efficiencies be used, since its carrier mix changes over time?
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
- **Q13 Plastics end of life (T23).** The link follows PatEx (CO2 only where waste is
  burned, `patex.plastics_eol_co2: false`). Confirm this convention for PAC 2.0.
- **Q14 Methanol and ammonia ships (T15).** PatEx shipping (IWW and bunkers-marine) runs on
  marine fuel oil (fossil, bio, synthetic), electricity and hydrogen only. Methanol and
  ammonia are expected to take a large share of shipping fuel by 2040–2050 (PyPSA-Eur's
  default: methanol 55 % in 2040, 80 % in 2045). Will PatEx add them? The link takes the
  fuel split from PatEx, so without them PyPSA-Eur has no methanol ships in PatEx
  countries; ammonia ships would need a new load in PyPSA-Eur.
- **Q15 PAC 2.0 lever file (T6)** → `runs/pac2/patex/levers.json` (runs use levers = 2).
- **Q17 Fossil imports and domestic production (T29).** For gas and coal, PatEx imports
  `demand × energy-net-import-refineries[%]` and books the rest as primary production,
  also where a country has no resource (coal in Belgium). What do the lever's values
  stand for, and will PAC 2.0 set them per country? Until then the soft-link adds the
  production above today's (Eurostat) to the import cap.
- **Q18 Bioenergy imports (T29).** Gross imports by origin (`agr_bio-energy-production-by-
  energy-carrier-origin`): some countries import far more biogas than their gas use
  (figures in FINDINGS). Expected? Only one country imports electricity: is electricity
  trade switched off elsewhere?

## For CAN

- **Q16 Scenario settings (T11, T28–T34).** CO2 target (EU or national, or PatEx's own
  emission trajectory per country), nuclear (closure dates per country, lifetime extensions
  such as Doel 4 / Tihange 3 to 2035 and Borssele, no new build?), CCS (fossil CCS allowed?),
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
