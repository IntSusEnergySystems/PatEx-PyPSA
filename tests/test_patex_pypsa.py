from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from patex_pypsa import (
    coverage,
    default_mappings_dir,
    export_coupling_dir,
    extract,
    land_transport_scale,
    load_patex_tables,
    load_rules,
    override_country_totals,
    split_stacked,
)
from patex_pypsa.export import HEAT_COLUMNS, horizon_tables
from patex_pypsa.extraction import Rule, parse_filters

SYNTHETIC_RUN = Path(__file__).resolve().parents[3] / "patex" / "xx.pkl"

BLD = "bld_energy-demand[TWh]"
BLD_DH = "bld_energy-demand-incl-district-heating[TWh]"


def stacked_bld() -> pd.DataFrame:
    """Two variables stacked as in a PatEx legacy frame."""
    a = pd.DataFrame(
        {
            "Country": ["BE"] * 3,
            "Years": [2030] * 3,
            "building-type": ["residential"] * 3,
            "end-use": ["heating", "heating", "cooking"],
            "energy-carrier": ["electricity", "ambiant", "gaseous-ff-natural"],
            BLD: [2.0, 3.0, 1.0],
        }
    )
    b = pd.DataFrame(
        {
            "Country": ["BE"],
            "Years": [2030],
            "building-type": ["residential"],
            "end-use": ["heating"],
            BLD_DH: [10.0],
        }
    )
    return pd.concat([a, b], ignore_index=True)


def test_split_stacked_keeps_only_own_dimensions():
    tables = split_stacked(stacked_bld())
    assert set(tables) == {BLD, BLD_DH}
    assert "energy-carrier" not in tables[BLD_DH].columns
    assert len(tables[BLD]) == 3


def test_parse_filters():
    assert parse_filters("a=x|y; b!=z") == {
        "a": (True, frozenset({"x", "y"})),
        "b": (False, frozenset({"z"})),
    }
    assert parse_filters("") == {}


def test_signed_rules_are_summed_per_category():
    tables = split_stacked(stacked_bld())
    rules = [
        Rule("total residential space", "energy_totals", 1, BLD_DH, parse_filters("end-use=heating")),
        Rule(
            "total residential space",
            "energy_totals",
            -1,
            BLD,
            parse_filters("end-use=heating; energy-carrier=ambiant"),
        ),
    ]
    long = extract(tables, rules)
    assert long["value"].item() == pytest.approx(7.0)


def test_coverage_reports_unmatched_energy():
    tables = split_stacked(stacked_bld())
    rules = [Rule("x", "energy_totals", 1, BLD, parse_filters("end-use=heating"))]
    gaps = coverage(tables, rules)
    assert gaps["value_all_years"].sum() == pytest.approx(1.0)  # the gas cooking row


def test_unknown_dimension_fails():
    tables = split_stacked(stacked_bld())
    with pytest.raises(KeyError):
        extract(tables, [Rule("x", "energy_totals", 1, BLD, parse_filters("vehicule-type=LDV"))])


def test_country_codes_are_mapped():
    tables = split_stacked(stacked_bld().replace({"BE": "EL"}))
    long = extract(tables, [Rule("x", "energy_totals", 1, BLD)], {"EL": "GR"})
    assert set(long["country"]) == {"GR"}


def test_override_country_totals_conserves_totals_and_shares():
    nodal = pd.DataFrame({"a": [1.0, 3.0, 5.0], "b": [0.0, 0.0, 2.0]}, index=["BE0", "BE1", "FR0"])
    node_country = pd.Series({"BE0": "BE", "BE1": "BE", "FR0": "FR"})
    weights = pd.Series({"BE0": 0.5, "BE1": 0.5, "FR0": 1.0})
    totals = pd.DataFrame({"a": [8.0], "b": [4.0]}, index=["BE"])
    out = override_country_totals(nodal, totals, node_country, weights)
    np.testing.assert_allclose(out.loc[["BE0", "BE1"], "a"], [2.0, 6.0])  # PyPSA shares kept
    np.testing.assert_allclose(out.loc[["BE0", "BE1"], "b"], [2.0, 2.0])  # fallback weights
    assert out.loc["FR0"].tolist() == [5.0, 2.0]  # country without PatEx data untouched


def test_land_transport_scale_reproduces_energy_per_fuel():
    snapshots = pd.RangeIndex(2)
    profiles = {
        "electric": pd.DataFrame({"BE0": [1.0, 3.0]}, index=snapshots),
        "fuel_cell": pd.DataFrame({"BE0": [2.0, 2.0]}, index=snapshots),
        "ice": pd.DataFrame({"BE0": [0.0, 0.0]}, index=snapshots),
        "gas": pd.DataFrame({"BE0": [1.0, 1.0]}, index=snapshots),
    }
    energy = pd.DataFrame(
        {"electric": [8.0], "fuel_cell": [2.0], "ice": [5.0], "gas": [3.0]}, index=["BE0"]
    )
    weights = pd.Series(2.0, index=snapshots)  # 2 h per snapshot
    factor = land_transport_scale(profiles, energy, weights)
    for engine in ("electric", "fuel_cell", "gas"):
        burnt = (factor.at["BE0", engine] * profiles[engine]["BE0"] * weights).sum()
        assert burnt == pytest.approx(energy.at["BE0", engine])
    assert factor.at["BE0", "ice"] == 0.0  # no profile: no load rather than a division by 0


def test_categories_cannot_mix_units():
    tables = split_stacked(stacked_bld())
    tables["x_y[MtCO2e]"] = tables[BLD].rename(columns={BLD: "x_y[MtCO2e]"})
    rules = [Rule("a", "industry", 1, BLD), Rule("a", "industry", 1, "x_y[MtCO2e]")]
    with pytest.raises(ValueError, match="mixing units"):
        extract(tables, rules)


def long_rows(rows):
    return pd.DataFrame(rows, columns=["target", "category", "country", "year", "unit", "value"])


def test_horizon_tables_turn_waste_into_co2_and_district_heat_into_share():
    long = long_rows(
        [
            ("industry", "solid waste", "BE", 2030, "TWh", 10.0),
            ("industry", "process emission", "BE", 2030, "MtCO2e", 3.0),
            ("parameters", "district heat", "BE", 2030, "TWh", 5.0),
            ("parameters", "number evs", "BE", 2030, "number", 1e6),
        ]
        + [("energy_totals", c, "BE", 2030, "TWh", 5.0) for c in HEAT_COLUMNS]
    )
    out = horizon_tables(long, 2030, pd.Series({"BE": 0.4}))
    assert "solid waste" not in out["industry"]
    assert out["industry"].at["BE", "process emission"] == pytest.approx(3.0 + 10.0 * 0.4)
    assert out["industry"].at["BE", "ammonia"] == 0.0  # made from PatEx carriers already
    assert out["parameters"].at["BE", "district heat share"] == pytest.approx(0.25)
    with pytest.raises(ValueError, match="CO2 factors"):
        horizon_tables(long, 2030)


def test_co2_intensity_weights_factors_by_patex_energy():
    from patex_pypsa.emissions import co2_intensity

    energy = pd.DataFrame(
        {
            "Country": "BE",
            "Years": 2030,
            "sector": ["tra", "tra", "ind"],
            "energy-carrier": ["liquid-ff-diesel", "liquid-ff-gasoline", "gaseous-ff-natural"],
            "TWh": [3.0, 1.0, 2.0],
        }
    )
    factors = pd.DataFrame(
        {
            "Country": "BE",
            "sector": ["tra", "tra", "ind", "ind"],
            "energy-carrier": [
                "liquid-ff-diesel",
                "liquid-ff-gasoline",
                "gaseous-ff-natural",
                "solid-ff-coal",
            ],
            "tCO2/MWh": [0.265, 0.252, 0.203, 0.354],
        }
    )
    ci = co2_intensity(energy, factors, 2030)
    assert ci["oil"] == pytest.approx((3 * 0.265 + 0.252) / 4)
    assert ci["gas"] == pytest.approx(0.203)
    assert ci["coal"] == pytest.approx(0.354)  # unused: mean of its factors
    with pytest.raises(ValueError, match="no PatEx CO2 factor"):
        co2_intensity(energy.assign(sector="agr"), factors, 2030)


@pytest.mark.skipif(not SYNTHETIC_RUN.exists(), reason="no synthetic PatEx run (patex/xx.pkl)")
def test_canonical_rules_on_synthetic_run(tmp_path):
    tables = load_patex_tables(SYNTHETIC_RUN)
    rules = load_rules(default_mappings_dir() / "extraction_rules.csv")
    assert coverage(tables, rules).empty  # every TWh exported or explicitly ignored
    factors = pd.DataFrame(
        [
            (ct, sector, carrier, 0.3)
            for ct in load_patex_tables(SYNTHETIC_RUN)["bld_energy-demand[TWh]"]["Country"].unique()
            for sector in ("ind", "tra", "agr", "bld")
            for carrier in ["solid-waste", "gaseous-ff-natural", "solid-ff-coal", "liquid-ff-oil",
                            "liquid-ff-diesel", "liquid-ff-gasoline", "liquid-ff-kerosene",
                            "liquid-ff-marinefueloil"]
        ],
        columns=["Country", "sector", "energy-carrier", "tCO2/MWh"],
    )
    out = export_coupling_dir(
        tmp_path, SYNTHETIC_RUN, [2030, 2050], allow_negative=True, co2_factors=factors
    )
    et = pd.read_csv(out / "patex_energy_totals_2030.csv", index_col=0)
    assert {"total road", "electricity residential", "total residential space"} <= set(et.columns)
    ind = pd.read_csv(out / "patex_industry_2030.csv", index_col=0)
    assert {"process emission", "methane feedstock"} <= set(ind.columns)
    ci = pd.read_csv(out / "patex_co2_intensity_2030.csv", index_col=0)["CO2 intensity"]
    assert ci.to_dict() == pytest.approx({"gas": 0.3, "oil": 0.3, "coal": 0.3})
    with pytest.raises(ValueError, match="horizon 2033"):
        export_coupling_dir(tmp_path, SYNTHETIC_RUN, [2033], allow_negative=True)


IDEES_BE = (
    Path(__file__).resolve().parents[3]
    / "PyPSA-Eur-CANEU/data/jrc_idees/archive/2023-v1/BE/JRC-IDEES-2023_Tertiary_BE.xlsx"
)


def agriculture_long(country="BE"):
    return pd.DataFrame(
        {
            "target": "agriculture",
            "category": ["electricity", "diesel", "gas"],
            "country": country,
            "year": 2030,
            "unit": "TWh",
            "value": [2.0, 10.0, 4.0],
        }
    )


def agriculture_shares():
    rows = []
    for ct in ("BE", "EU27"):
        rows += [
            (ct, "electricity", 0.6, 0.2, 0.2),
            (ct, "diesel", 0.0, 0.3, 0.7),
            (ct, "gas", 0.0, 1.0, 0.0),
        ]
    return pd.DataFrame(rows, columns=["country", "group", "electricity", "heat", "machinery"])


def test_agriculture_split_conserves_energy_and_keeps_electric_machinery_as_electricity():
    from patex_pypsa.agriculture import split_agriculture

    out = split_agriculture(agriculture_long(), agriculture_shares())
    v = out.set_index("category")["value"]
    assert v["total agriculture electricity"] == pytest.approx(2.0 * 0.6 + 2.0 * 0.2)
    assert v["agriculture machinery electric"] == pytest.approx(0.4)
    assert v["total agriculture heat"] == pytest.approx(0.4 + 3.0 + 4.0)
    assert v["total agriculture machinery"] == pytest.approx(7.0)  # liquid fuel only
    columns = ["total agriculture electricity", "total agriculture heat", "total agriculture machinery"]
    assert v[columns].sum() == pytest.approx(16.0)


def test_agriculture_split_falls_back_to_eu27_and_rejects_unknown_groups():
    from patex_pypsa.agriculture import split_agriculture

    out = split_agriculture(agriculture_long("XX"), agriculture_shares())
    assert set(out["country"]) == {"XX"}
    bad = agriculture_long().assign(category="kerosene")
    with pytest.raises(ValueError, match="kerosene"):
        split_agriculture(bad, agriculture_shares())


@pytest.mark.skipif(not IDEES_BE.exists(), reason="no JRC-IDEES data in ../PyPSA-Eur-CANEU")
def test_idees_by_use_belgium_2021():
    from patex_pypsa.agriculture import idees_by_use

    t = idees_by_use(IDEES_BE, 2021)
    assert t.loc["diesel", "heat"] == pytest.approx(1.12, abs=0.01)  # greenhouses
    assert t.loc["diesel", "machinery"] == pytest.approx(2.49, abs=0.01)
    assert t.loc["electricity", "machinery"] == pytest.approx(0.26, abs=0.01)  # motor drives
    assert t.loc["electricity", "heat"] == pytest.approx(0.28, abs=0.01)
    assert t.loc["electricity", "electricity"] == pytest.approx(1.19, abs=0.01)


def test_sankey_rows_are_drawn_once_and_ambient_is_not_passed():
    from patex_pypsa.sankey import sankey_flows

    tables = split_stacked(stacked_bld())
    flow_rules = [
        (Rule("Building heat", "sankey", 1, BLD, parse_filters("end-use=heating; energy-carrier!=ambiant")), "", "Residential {end-use}"),
        (Rule("Ambient heat (heat-pump COP)", "sankey", 1, BLD, parse_filters("end-use=heating; energy-carrier=ambiant")), "", "Residential {end-use}"),
        (Rule("Not modelled in PyPSA-Eur", "sankey", 1, BLD, parse_filters("end-use=cooking")), "", "Residential other uses"),
    ]
    flows = sankey_flows({BLD: tables[BLD]}, flow_rules, [], pd.DataFrame())
    assert flows["TWh"].sum() == pytest.approx(6.0)  # every TWh once
    assert set(flows["sector"]) == {"Residential heating", "Residential other uses"}
    assert flows.set_index("fuel").at["Ambient heat", "pypsa"] == "Ambient heat (heat-pump COP)"
    with pytest.raises(ValueError, match="no or several Sankey rules"):
        sankey_flows({BLD: tables[BLD]}, flow_rules[:2], [], pd.DataFrame())  # cooking unmapped
    with pytest.raises(ValueError, match="no or several Sankey rules"):
        sankey_flows({BLD: tables[BLD]}, flow_rules + flow_rules[2:], [], pd.DataFrame())  # twice


@pytest.mark.skipif(not SYNTHETIC_RUN.exists(), reason="no synthetic PatEx run (patex/xx.pkl)")
def test_report_pages_from_synthetic_bundle(tmp_path):
    from patex_pypsa.pages import write_report

    factors = pd.DataFrame(
        [("XX", s, c, 0.3) for s in ("ind", "tra", "agr", "bld")
         for c in ["solid-waste", "gaseous-ff-natural", "solid-ff-coal", "liquid-ff-oil",
                   "liquid-ff-diesel", "liquid-ff-gasoline", "liquid-ff-kerosene",
                   "liquid-ff-marinefueloil"]],
        columns=["Country", "sector", "energy-carrier", "tCO2/MWh"],
    )
    export_coupling_dir(tmp_path, SYNTHETIC_RUN, [2030], allow_negative=True, co2_factors=factors)
    out = write_report(tmp_path)
    assert (out / "sankey_2030.html").exists() and (out / "indicators_catalogue.html").exists()
    assert "PX_DATA" in (out / "indicators_energy.html").read_text()
