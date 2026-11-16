"""Cross-border transfers of a solved network against caps and TYNDP NTCs (T30).

    python scripts/interconnection_check.py <solved network.nc> [--ntc <fork>/data/interconnection_ntc_2030.csv]

Per border c0-c1 (MW):
- ``cap``: the `interconnection_limit` constraint (usable capacity, AC x s_max_pu + DC);
- ``built``: usable capacity after the solve (s_nom_opt x s_max_pu + p_nom_opt);
- ``max c0->c1`` / ``max c1->c0``: largest hourly net transfer over the year (sum of the
  flows of every line and DC link crossing the border). In PyPSA there is one market and
  one network, so this is both the physical flow and the exchange: the counterpart of an
  NTC, as an outcome of the model;
- ``ntc c0->c1`` / ``ntc c1->c0``: TYNDP 2026 reference-grid NTC 2030 (comparison only).
"""

import argparse

import pandas as pd
import pypsa


def border_flows(n: pypsa.Network) -> tuple[pd.DataFrame, pd.Series]:
    country = n.buses.country
    flows, built = {}, {}
    parts = (
        ("Line", n.lines, n.lines_t.p0, "s_nom_opt", n.lines.s_max_pu),
        ("Link", n.links[n.links.carrier == "DC"], n.links_t.p0, "p_nom_opt", 1.0),
    )
    for _, static, p0, attr, derate in parts:
        a, b = static.bus0.map(country), static.bus1.map(country)
        cross = static.index[a.notna() & b.notna() & (a != b)]
        reversed_ = static.get("reversed", pd.Series(False, static.index)).fillna(False)
        for i in cross:
            c0, c1 = sorted((a[i], b[i]))
            sign = 1.0 if a[i] == c0 else -1.0  # positive = c0 -> c1
            key = f"{c0}-{c1}"
            flow = p0[i] * sign if i in p0 else 0.0
            flows[key] = flows.get(key, 0.0) + flow
            d = derate[i] if isinstance(derate, pd.Series) else derate
            if not bool(reversed_[i]):  # "-reversed" DC copy: same capacity, count once
                built[key] = built.get(key, 0.0) + static.at[i, attr] * d
    return pd.DataFrame(flows), pd.Series(built)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("network")
    parser.add_argument("--ntc", help="interconnection_ntc_2030.csv of the fork")
    args = parser.parse_args()
    n = pypsa.Network(args.network)
    flows, built = border_flows(n)
    out = pd.DataFrame({"built": built})
    glc = n.global_constraints[n.global_constraints.type == "interconnection_limit"]
    out["cap"] = glc.set_index("carrier_attribute")["constant"].reindex(out.index)
    out["max c0->c1"] = flows.clip(lower=0).max()
    out["max c1->c0"] = (-flows).clip(lower=0).max()
    if args.ntc:
        ntc = pd.read_csv(args.ntc)
        ntc.index = ntc.country0 + "-" + ntc.country1
        out["ntc c0->c1"] = ntc["mw_0to1"].reindex(out.index)
        out["ntc c1->c0"] = ntc["mw_1to0"].reindex(out.index)
    pd.set_option("display.width", 200)
    print(f"{args.network}: cross-border capacity and transfers [MW]")
    print(out.round(0).to_string())


if __name__ == "__main__":
    main()
