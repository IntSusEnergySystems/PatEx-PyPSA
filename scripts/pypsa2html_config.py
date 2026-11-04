"""
Write a pypsa2html project config for one PyPSA-Eur run of the soft-link.

pypsa2html detects the clustered buses (``BE0 0AC`` ...) as nodes; country pages need
explicit ``nodes.groups``. They are built from ``n.buses.country`` of a solved network
(never from name prefixes), so any country set works.

    python scripts/pypsa2html_config.py <pypsa-eur dir> <run name> <out.yaml> [--html-dir DIR]

Run in an environment with pypsa (the PyPSA-Eur pixi env).
"""

import argparse
from pathlib import Path

import pypsa
import yaml

COUNTRY_NAMES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CZ": "Czechia", "DE": "Germany",
    "DK": "Denmark", "EE": "Estonia", "ES": "Spain", "FI": "Finland", "FR": "France",
    "GR": "Greece", "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IT": "Italy",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "NL": "Netherlands",
    "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SE": "Sweden", "SI": "Slovenia",
    "SK": "Slovakia", "GB": "Great Britain", "CH": "Switzerland", "NO": "Norway",
    "AL": "Albania", "BA": "Bosnia and Herzegovina", "ME": "Montenegro",
    "MK": "North Macedonia", "RS": "Serbia", "XK": "Kosovo",
}


def country_groups(network_file):
    n = pypsa.Network(network_file)
    # Electricity buses carry the node locations pypsa2html detects.
    buses = n.buses[(n.buses.carrier == "AC") & n.buses.country.ne("")]
    members = buses.groupby("country").apply(lambda b: sorted(set(b.location)))
    return {c: m for c, m in members.items()}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    p.add_argument("pypsa_eur", type=Path)
    p.add_argument("run")
    p.add_argument("out", type=Path)
    p.add_argument("--html-dir", default="results/{scenario}/html")
    a = p.parse_args()

    results = Path("results") / a.run
    networks = sorted((a.pypsa_eur / results / "networks").glob("solved_*.nc"))
    if not networks:
        raise SystemExit(f"no solved networks under {a.pypsa_eur / results}")
    groups = country_groups(networks[0])
    countries = sorted(groups)

    config = {
        "root": str(a.pypsa_eur.resolve()),
        "project": {
            "name": "CAN Europe PAC 2.0 — PyPSA-Eur",
            "subtitle": f"PatEx → PyPSA-Eur soft-link, run {a.run}",
        },
        # flows under 0.1 TWh (library default) were dropped per node, which left
        # small countries (LU) visibly unbalanced
        "model": {"network_pattern": "networks/solved_{horizon}.nc", "flow_threshold": 0.01},
        "nodes": {
            "detect": True,
            "focus": countries[0],
            "labels": {c: COUNTRY_NAMES.get(c, c) for c in countries},
            "aggregate": {"enabled": True, "code": "ALL", "label": "All countries"},
            "groups": [
                {"code": c, "label": COUNTRY_NAMES.get(c, c), "members": groups[c]}
                for c in countries
            ],
        },
        "scenarios": [
            {
                "name": a.run,
                "label": a.run,
                "results_dir": str(results),
                "resources_dir": str(Path("resources") / a.run),
            }
        ],
        "landing": {"scenario": a.run, "node": countries[0], "page": "key_figures"},
        "output": {"dir": a.html_dir, "plotly": "cdn"},
    }
    a.out.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    print(f"{a.out}: countries {countries}")


if __name__ == "__main__":
    main()
