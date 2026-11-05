# PATEX_PyPSA

Soft-link from **PatEx** (Climact's Pathways Explorer scenario model) to **PyPSA-Eur**:
PatEx annual demands per country and year become PyPSA-Eur demand inputs per planning
horizon. Built after `../../TIMES2PYPSA/TIMES_PyPSA` (TIMES-WAL → pypsa-wal).

PatEx sets **what has to be served** (demand by sector, end use and carrier, i.e. the
consequences of renovation, electrification and sufficiency levers). PyPSA-Eur stays in
charge of **how it is served**: capacities, flexibility, imports, grids and costs. PatEx
supply outputs (power capacities, imports, ...) are not imposed. They are used only to
compare results.

See [MODEL_CHANGES.md](MODEL_CHANGES.md) for what is passed and what was changed in each
model, the fork's `docs/<sector>.md` for the data flow and the reasons per sector,
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) for what is still open (`Qn`) and
[TODO.md](TODO.md) for the work items (`Tn`).

## Layout

```
PATEX2PYPSA/
├── PATEX_PyPSA/                  # this repository
│   ├── patex_pypsa/
│   │   ├── io.py                 # read `patex run -o` pickle, split stacked frames
│   │   ├── extraction.py         # apply rules, coverage check
│   │   ├── export.py             # write <coupling_dir>/pypsa_inputs + manifest
│   │   ├── agriculture.py        # agriculture carriers → PyPSA uses (JRC-IDEES shares)
│   │   ├── allocate.py           # country totals → PyPSA nodes (used inside pypsa-eur)
│   │   ├── transport.py          # road energy per fuel → scale of PyPSA-Eur's land-transport loads
│   │   ├── emissions.py          # PatEx CO2 factors → PyPSA-Eur CO2 intensity per carrier
│   │   ├── sankey.py             # every PatEx demand row → fuel / sector / PyPSA-Eur input
│   │   ├── indicators.py         # PatEx output series (data/indicators.csv)
│   │   ├── pages.py              # HTML report: Sankey + indicator pages
│   │   └── cli.py                # patex-pypsa export-coupling | inspect
│   ├── data/
│   │   ├── extraction_rules.csv  # PatEx variable + filters → PyPSA-Eur column (THE mapping)
│   │   ├── mapping_countries.csv # EL→GR, UK→GB
│   │   ├── agriculture_use_shares.csv  # JRC-IDEES 2021 carrier → use shares
│   │   ├── sankey_flows.csv      # Sankey path of every PatEx demand row
│   │   ├── sankey_nodes.csv      # PyPSA-Eur nodes and the bundle columns they must equal
│   │   └── indicators.csv        # indicator charts (variable, filters, split)
│   ├── MODEL_CHANGES.md          # what is passed / changed in each model, and why
│   ├── OPEN_QUESTIONS.md         # open questions Qn (Climact, CAN, ours)
│   ├── TODO.md, CHANGELOG.md
│   ├── scripts/run_coupled.sh    # PatEx run → export → (snakemake)
│   ├── scripts/check_agriculture_split.py  # base-year check vs JRC-IDEES
│   ├── scripts/check_network_ledger.py     # composed network loads vs bundle
│   └── tests/
├── private_notes/                # outside git: PatEx figures (FINDINGS.md), session handover
└── runs/<scenario>/              # one coupling bundle per scenario (created by runs, outside git)
```

Model checkouts used: `../../patex` (uv env, Python 3.11, pandas 2.2) and `../../PyPSA-Eur-CANEU`
(pixi env, pandas 3). `patex_pypsa` only depends on pandas and works in both
environments. The two models exchange **CSV files only**.

## Install

```bash
# in the PatEx env (to export)
cd ../../patex && uv pip install -e ../PATEX2PYPSA/PATEX_PyPSA
# in the PyPSA-Eur env (to use override_country_totals inside the workflow)
# (the pixi env has no pip; redo after a pixi install that recreates the env)
cd ../../PyPSA-Eur-CANEU && uv pip install --python .pixi/envs/default/bin/python \
    --no-deps -e ../PATEX2PYPSA/PATEX_PyPSA
```

## Usage

```bash
# 1. Run PatEx (real dataset needed for meaningful values; xx.pkl = synthetic test run)
#    every country PyPSA-Eur models that PatEx has: EU27 minus CY, MT (Greece = EL)
cd ../../patex
uv run patex run "AT|BE|BG|CZ|DE|DK|EE|ES|FI|FR|EL|HR|HU|IE|IT|LT|LU|LV|NL|PL|PT|RO|SE|SI|SK" \
    --dataset "s3://climact-dataset/patex/47.x.4?region=eu-central-1" \
    --levers-file ../PATEX2PYPSA/runs/pac2/patex/levers.json \
    -o ../PATEX2PYPSA/runs/pac2/patex/run.pkl          # runs/levers2: --levers-default 2

# 2. Look at what a run contains
uv run patex-pypsa inspect --pkl ../PATEX2PYPSA/runs/pac2/patex/run.pkl --grep energy-demand

# 3. Export the coupling bundle
uv run patex-pypsa export-coupling --pkl ../PATEX2PYPSA/runs/pac2/patex/run.pkl \
    --coupling-dir ../PATEX2PYPSA/runs/pac2 --horizons 2030,2040,2050 \
    --dataset "s3://climact-dataset/patex/47.x.4?region=eu-central-1"   # CO2 factors
```

Or do all of it with `scripts/run_coupled.sh runs/pac2 [--snakemake]`.

Countries without PatEx data (47.x.4: AL, BA, CH, GB, ME, MK, NO, RS, XK) keep
PyPSA-Eur's own demands; they are listed in `patex.fallback_countries`. Any other
modelled country missing from the bundle stops the workflow, so a failed PatEx country
cannot fall back silently.

## Report: Sankey and PatEx indicators

```bash
patex-pypsa report --coupling-dir ../PATEX2PYPSA/runs/pac2     # → runs/pac2/report/index.html
# or from PyPSA-Eur: snakemake ... results/<run>/patex_report/index.html
```

Built after TIMES_PyPSA's Sankey and indicator pages, from the bundle only (no PatEx run
needed, pandas only):

- `sankey_{year}.html` (base year + horizons): PatEx final energy and ambient heat, fuel →
  PatEx sector / end use → PyPSA-Eur input, with a country selector (EU = sum of the bundle
  countries). Links are coloured by PyPSA-Eur sector, grey for energy not passed on purpose.
  Every row of the PatEx demand variables is drawn exactly once (`data/sankey_flows.csv`,
  checked at export), and a table reconciles each PyPSA-Eur node with the bundle (ratio 1
  expected; another value is a mapping hole).
- `indicators_{page}.html`: stacked PatEx trajectories 2021–2050 (final energy, buildings,
  transport, industry, agriculture, emissions, power, district heat) with their tables.
- `indicators_catalogue.html`: every series, filterable by country / category / indicator,
  with sparkline and Δ%.

These pages describe the PatEx side, not the PyPSA-Eur results.

Output in `<coupling_dir>/pypsa_inputs/`:

| File | Content |
|---|---|
| `patex_energy_totals_{h}.csv` | country × PyPSA-Eur `energy_totals` columns (+ `electricity base load`), TWh/a |
| `patex_industry_{h}.csv` | country × `industrial_energy_demand` columns, TWh/a (process emissions MtCO2e/a) |
| `patex_parameters_{h}.csv` | country × `district heat share` [-], `number evs` |
| `patex_co2_intensity_{h}.csv` | `gas`, `oil`, `coal` → CO2 intensity [tCO2/MWh]; `oil refining` → refinery CO2 per MWh of oil products |
| `patex_co2_factors.csv` | PatEx CO2 factors used (country, sector, fuel) |
| `patex_demands_long.csv` | every year, long format, for QA and plots |
| `coverage.csv` | PatEx energy that no rule exports or ignores (must be empty) |
| `manifest.json` | PatEx run checksum, rules checksum, horizons, countries, timestamp |

## Mapping rules

`data/extraction_rules.csv`, one signed term per row; rows with the same `category` are
summed:

```
category,target,sign,patex_variable,filters,note
total residential space,energy_totals,1,bld_energy-demand-incl-district-heating[TWh],building-type=residential; end-use=heating,
total residential space,energy_totals,-1,bld_energy-demand[TWh],building-type=residential; end-use=heating; energy-carrier=ambiant,
```

- `filters`: `dim=a|b` keeps, `dim!=a|b` drops, `;` combines. Unknown dimensions fail;
  filter values absent from the run trigger a warning (avoids silent 0 TWh). The unit
  is the one of the PatEx variable (`unit` column of the long table); a category mixing
  units fails.
- `target = ignore` declares a slice that is left out on purpose. The export then checks
  that every non-zero row of each source variable is either exported or ignored
  (`coverage.csv`, `--strict` turns it into an error).
- Negative demands fail (`--allow-negative` only for the synthetic dataset, which is
  random).

Agriculture is the one exception to "one rule = one column": PatEx only gives it by
carrier, PyPSA-Eur needs it by use. The `agriculture` rules extract carrier groups, then
`agriculture.py` splits them with `data/agriculture_use_shares.csv`:

```bash
uv run --extra idees patex-pypsa build-agriculture-shares \
    --idees-dir ../../PyPSA-Eur-CANEU/data/jrc_idees/archive/2023-v1      # rebuild the shares
python scripts/check_agriculture_split.py runs/levers2 ../../PyPSA-Eur-CANEU/data/jrc_idees/archive/2023-v1
```

Mapping edits go in `data/` only. Each run copies the rules into `<coupling_dir>/mappings/`.

## PyPSA-Eur side

The hooks live only in the fork
[`IntSusEnergySystems/PyPSA-Eur-CANEU`](https://github.com/IntSusEnergySystems/PyPSA-Eur-CANEU)
(`../../PyPSA-Eur-CANEU`, branch `develop`), all behind `patex.enable` (default `false`).
The list of changed files and the reasons is in [MODEL_CHANGES.md](MODEL_CHANGES.md).
`patex_pypsa` must be installed in the pixi env (see Install); it is imported only when
`patex.enable` is true.

```bash
cd ../../PyPSA-Eur-CANEU
pixi run snakemake --configfile config/test/config.overnight.yaml config/test/config.patex.yaml -c4  # BE test
# config/config.patex.yaml is the full run; it expects ../PATEX2PYPSA/runs/pac2 (T6, not built yet)

# check a solved or composed network against the bundle (pixi python)
python ../PATEX2PYPSA/PATEX_PyPSA/scripts/check_network_ledger.py \
    results/<run>/networks/solved_<h>.nc ../PATEX2PYPSA/runs/<scenario> --horizon <h> \
    --heating-efficiencies resources/<run>/heating_efficiencies.csv
```

## Tests

```bash
PYTHONPATH=. ../../patex/.venv/bin/python -m pytest -q -p no:cacheprovider tests
PYTHONPATH=. ../../PyPSA-Eur-CANEU/.pixi/envs/default/bin/python -m pytest -q -p no:cacheprovider tests
```

The end-to-end test uses `../../patex/xx.pkl` (synthetic region `XX`) when present.
