"""Check the agriculture split of a coupling bundle against JRC-IDEES.

    python scripts/check_agriculture_split.py <coupling_dir> <idees_dir> [--year 2021]

For the base year, per country [TWh]:
- conservation: electricity + heat + machinery = PatEx agriculture total;
- PatEx split vs IDEES by use, with IDEES restricted to the carriers PatEx has
  (no distributed heat, solar or ambient heat) and with motor drives counted as
  electricity, as in the export.
"""

import argparse
from pathlib import Path

import pandas as pd

from patex_pypsa.agriculture import idees_by_use
from patex_pypsa.export import default_mappings_dir, load_country_map

COLUMNS = {
    "electricity": "total agriculture electricity",
    "heat": "total agriculture heat",
    "machinery": "total agriculture machinery",
}

p = argparse.ArgumentParser()
p.add_argument("coupling_dir", type=Path)
p.add_argument("idees_dir", type=Path)
p.add_argument("--year", type=int, default=2021)
args = p.parse_args()

long = pd.read_csv(args.coupling_dir / "pypsa_inputs" / "patex_demands_long.csv")
long = long[long["year"] == args.year]
patex = long[long["target"] == "energy_totals"].pivot_table(
    index="country", columns="category", values="value"
)[list(COLUMNS.values())]
patex.columns = list(COLUMNS)
by_carrier = long[long["target"] == "agriculture"].groupby("country")["value"].sum()

to_idees = {v: k for k, v in load_country_map(default_mappings_dir()).items()}
rows = []
for ct in patex.index:
    code = to_idees.get(ct, ct)
    idees = idees_by_use(args.idees_dir / code / f"JRC-IDEES-2023_Tertiary_{code}.xlsx", args.year)
    # Same definitions as the export: electric machinery (motor drives) counted as
    # electricity; carriers without a PatEx counterpart already left out.
    ref = {
        "electricity": idees.loc["electricity", ["electricity", "machinery"]].sum(),
        "heat": idees["heat"].sum(),
        "machinery": idees["machinery"].drop("electricity").sum(),
    }
    for use in COLUMNS:
        rows.append((ct, use, patex.loc[ct, use], ref[use]))
check = pd.DataFrame(rows, columns=["country", "use", "PatEx", "IDEES"])
check["ratio"] = check["PatEx"] / check["IDEES"]

conservation = (patex.sum(axis=1) - by_carrier).abs().max()
print(f"conservation, max |split − PatEx total| over countries: {conservation:.2e} TWh\n")
table = check.pivot(index="country", columns="use", values=["PatEx", "IDEES", "ratio"])
print(table.round(2).to_string())
total = check.groupby("use")[["PatEx", "IDEES"]].sum()
total["ratio"] = total["PatEx"] / total["IDEES"]
print(f"\nSum of {len(patex)} countries\n{total.round(2).to_string()}")
