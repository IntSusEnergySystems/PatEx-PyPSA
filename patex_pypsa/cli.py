"""``patex-pypsa`` command line.

    patex-pypsa export-coupling --pkl run.pkl --coupling-dir runs/pac2 --horizons 2030,2040,2050 \
        --dataset "s3://climact-dataset/patex/47.x.4?region=eu-central-1"
    patex-pypsa inspect --pkl run.pkl [--grep energy-demand]
    patex-pypsa report --coupling-dir runs/pac2            # HTML Sankey + indicators
    patex-pypsa build-agriculture-shares --idees-dir ../../PyPSA-Eur-CANEU/data/jrc_idees/archive/2023-v1
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .export import (
    AGRICULTURE_SHARES_FILE,
    default_mappings_dir,
    export_coupling_dir,
    load_country_map,
)
from .io import KEY_COLUMNS, load_patex_tables


def _horizons(text: str) -> list[int]:
    return [int(h) for h in text.split(",") if h.strip()]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="patex-pypsa", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("export-coupling", help="write <coupling_dir>/pypsa_inputs")
    e.add_argument("--pkl", type=Path, required=True, help="output of `patex run ... -o`")
    e.add_argument("--coupling-dir", type=Path, required=True)
    e.add_argument("--horizons", type=_horizons, required=True, help="e.g. 2030,2040,2050")
    e.add_argument(
        "--dataset",
        help="PatEx dataset of the run, for the CO2 factors (needs the PatEx environment)",
    )
    e.add_argument("--mappings-dir", type=Path, help="default: the repository data/")
    e.add_argument("--scenario-id", help="default: the pickle file name")
    e.add_argument("--strict", action="store_true", help="fail if some PatEx energy is unmapped")
    e.add_argument(
        "--allow-negative", action="store_true", help="only warn on negative demands (synthetic data)"
    )

    r = sub.add_parser("report", help="HTML Sankey and indicator pages of a coupling bundle")
    r.add_argument("--coupling-dir", type=Path, required=True)
    r.add_argument("--out", type=Path, help="default: <coupling-dir>/report")
    r.add_argument("--years", type=_horizons, help="Sankey years (default: base year + horizons)")

    i = sub.add_parser("inspect", help="list the PatEx variables of a run and their dimensions")
    i.add_argument("--pkl", type=Path, required=True)
    i.add_argument("--grep", default="", help="only variables containing this text")

    a = sub.add_parser(
        "build-agriculture-shares", help="carrier → use shares of agriculture from JRC-IDEES"
    )
    a.add_argument("--idees-dir", type=Path, required=True, help="JRC-IDEES 2023 country folders")
    a.add_argument("--year", type=int, default=2021, help="base year (PatEx calibration year)")
    a.add_argument("--out", type=Path, help=f"default: data/{AGRICULTURE_SHARES_FILE}")
    return p


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "export-coupling":
        export_coupling_dir(
            args.coupling_dir,
            args.pkl,
            args.horizons,
            mappings_dir=args.mappings_dir,
            scenario_id=args.scenario_id,
            strict=args.strict,
            allow_negative=args.allow_negative,
            dataset=args.dataset,
        )
    elif args.command == "build-agriculture-shares":
        from .agriculture import shares_from_idees

        countries = sorted(
            p.name for p in args.idees_dir.iterdir() if p.is_dir() and p.name != "EU27"
        )
        shares = shares_from_idees(
            args.idees_dir, countries, args.year, load_country_map(default_mappings_dir())
        )
        out = args.out or default_mappings_dir() / AGRICULTURE_SHARES_FILE
        shares.to_csv(out, index=False, float_format="%.6f")
        logging.info("wrote %s (%d countries)", out, len(countries))
    elif args.command == "report":
        from .pages import write_report

        write_report(args.coupling_dir, args.out, sankey_years=args.years)
    elif args.command == "inspect":
        for variable, table in sorted(load_patex_tables(args.pkl).items()):
            if args.grep not in variable:
                continue
            dims = [c for c in table.columns if c not in (*KEY_COLUMNS, variable)]
            print(variable)
            for d in dims:
                print(f"    {d}: {', '.join(sorted(table[d].dropna().astype(str).unique()))}")


if __name__ == "__main__":
    main()
