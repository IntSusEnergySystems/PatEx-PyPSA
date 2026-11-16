"""Ammonia route: PatEx production becomes an NH3 demand, its energy and process CO2
leave the industry carriers, and nothing is lost or counted twice (2026-11-12)."""

import pandas as pd
import pytest

from patex_pypsa.export import MWH_NH3_PER_T, check_industry_balance, horizon_tables


def long_table(nh3_gas=10.0, other_gas=30.0, nh3_kt=1000.0, nh3_co2=2.0, other_co2=5.0):
    rows = [
        ("industry", "methane feedstock", other_gas),
        ("routes", "ammonia|methane feedstock", nh3_gas),
        ("industry", "process emission", other_co2),
        ("routes", "ammonia|process emission", nh3_co2),
        ("routes", "ammonia production", nh3_kt),
        ("energy_totals", "total road", 1.0),
        ("parameters", "number bev", 1.0),
    ]
    return pd.DataFrame(
        [{"target": t, "category": c, "country": "BE", "year": 2030, "unit": "TWh",
          "value": v} for t, c, v in rows]
    )


def tables(gas=40.0, co2=7.0):
    return {
        "ind_energy-demand-by-carrier-feedstock[TWh]": pd.DataFrame(
            {"Country": ["BE"], "Years": [2030], "ind_energy-demand-by-carrier-feedstock[TWh]": [gas]}
        ),
        "ind_emissions-by-material-by-type[MtCO2e]": pd.DataFrame(
            {"Country": ["BE", "BE"], "Years": [2030, 2030], "emission-type": ["process", "combustion"],
             "ind_emissions-by-material-by-type[MtCO2e]": [co2, 100.0]}
        ),
    }


def test_balance_holds_when_route_and_industry_add_up():
    check_industry_balance(long_table(), tables())


@pytest.mark.parametrize("kind,kwargs", [("energy", {"gas": 50.0}), ("process", {"co2": 9.0})])
def test_balance_fails_when_the_route_is_lost_or_doubled(kind, kwargs):
    with pytest.raises(ValueError, match=f"industry {kind} balance"):
        check_industry_balance(long_table(), tables(**kwargs))


def test_nh3_demand_from_production_and_route_out_of_industry():
    out = horizon_tables(long_table(), 2030)["industry"]
    assert out.at["BE", "ammonia"] == pytest.approx(1000.0 * MWH_NH3_PER_T / 1e3)
    assert out.at["BE", "methane feedstock"] == pytest.approx(30.0)  # route not in it
    assert out.at["BE", "methanol"] == 0.0
