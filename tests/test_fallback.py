"""Countries outside PatEx follow PatEx's EU trend from their own base data."""

import math

import pandas as pd
import pytest

from patex_pypsa.fallback import (
    base_load_factor,
    relative_share,
    trend_energy_totals,
    trend_industry,
    trend_parameters,
    trend_waste_to_energy,
)


def test_relative_share_rules():
    # EU share falls 0.4 → 0.1: proportional, GB 0.2 → 0.05
    assert relative_share(0.2, 0.4, 0.1) == pytest.approx(0.05)
    # EU share rises 0.01 → 0.8: GB keeps its position in what is left to switch
    assert relative_share(0.001, 0.01, 0.8) == pytest.approx(1 - 0.999 * 0.2 / 0.99)
    assert relative_share(None, 0.4, 0.1) == 0.1  # no national value: EU share
    assert relative_share(0.0, 0.0, 0.3) == pytest.approx(0.3)  # new fuel
    assert relative_share(0.5, 0.5, 0.5) == pytest.approx(0.5)


def test_energy_totals_total_trend_and_shares():
    cols = ["total road", "electricity road", "hydrogen road", "gas road",
            "total residential space", "electricity residential space",
            "electricity base load"]
    eu_b = pd.Series({"total road": 100.0, "electricity road": 1.0, "hydrogen road": 0.0,
                      "gas road": 2.0, "total residential space": 200.0,
                      "electricity residential space": 20.0, "electricity base load": 50.0})
    eu_h = pd.Series({"total road": 50.0, "electricity road": 40.0, "hydrogen road": 5.0,
                      "gas road": 1.0, "total residential space": 150.0,
                      "electricity residential space": 30.0, "electricity base load": 60.0})
    base = pd.DataFrame({"total road": [10.0], "electricity road": [0.2],
                         "total residential space": [30.0],
                         "electricity residential space": [6.0]}, index=["GB"])
    out = trend_energy_totals(base, eu_b, eu_h, cols)
    assert out.at["GB", "total road"] == pytest.approx(5.0)  # 10 × 50/100
    # electricity 0.02 with the EU rising 0.01 → 0.8; hydrogen (no national value)
    # and gas (EU unchanged, no national value) take the EU shares 0.1 and 0.02
    elec = 1 - 0.98 * 0.2 / 0.99
    assert out.at["GB", "electricity road"] == pytest.approx(5.0 * elec)
    assert out.at["GB", "hydrogen road"] == pytest.approx(0.5)
    assert out.at["GB", "gas road"] == pytest.approx(0.1)
    # heat: EU 0.1 → 0.2, GB 0.2 → 1 − 0.8 × 0.8/0.9, of 30 × 0.75
    assert out.at["GB", "electricity residential space"] == pytest.approx(
        (1 - 0.8 * 0.8 / 0.9) * 22.5)
    assert out["electricity base load"].isna().all()  # factor in the parameters


def test_cooling_stays_in_the_fallback_base_load():
    res, ser = "electricity residential space cooling", "electricity services space cooling"
    cols = ["total road", "electricity base load", res, ser]
    eu_b = pd.Series({"total road": 1.0, "electricity base load": 90.0, res: 2.0, ser: 8.0})
    eu_h = pd.Series({"total road": 1.0, "electricity base load": 100.0, res: 10.0, ser: 20.0})
    out = trend_energy_totals(pd.DataFrame({"total road": [1.0]}, index=["GB"]),
                              eu_b, eu_h, cols)
    assert out[[res, ser]].isna().all().all()  # no own load
    assert base_load_factor(eu_b, eu_h) == pytest.approx(1.3)  # (100 + 30) / (90 + 10)
    assert base_load_factor(eu_b.drop([res, ser]),
                            eu_h.drop([res, ser])) == pytest.approx(100 / 90)


def test_energy_totals_shares_capped_at_the_total():
    cols = ["total road", "electricity road", "hydrogen road"]
    eu = pd.Series({"total road": 10.0, "electricity road": 6.0, "hydrogen road": 6.0})
    out = trend_energy_totals(pd.DataFrame({"total road": [1.0]}, index=["GB"]), eu, eu, cols)
    assert out.loc["GB", ["electricity road", "hydrogen road"]].sum() == pytest.approx(1.0)


def test_industry_relative_position_and_renormalisation():
    cols = ["coal", "electricity", "hydrogen", "methane", "methane feedstock", "naphtha",
            "process emission", "process emission from feedstock", "coke"]
    eu_b = pd.Series({"coal": 20.0, "electricity": 40.0, "hydrogen": 0.0, "methane": 40.0,
                      "methane feedstock": 5.0, "naphtha": 15.0})
    eu_h = pd.Series({"coal": 10.0, "electricity": 50.0, "hydrogen": 20.0, "methane": 20.0,
                      "methane feedstock": 5.0, "naphtha": 15.0, "process emission": 40.0,
                      "process emission from feedstock": 6.0, "coke": 0.0})
    src_c = pd.DataFrame({"coal": [5.0], "electricity": [10.0], "hydrogen": [math.nan],
                          "methane": [5.0], "methane feedstock": [1.0], "naphtha": [3.0],
                          "process emission": [2.0]}, index=["GB"])
    src_eu = pd.DataFrame({"coal": [20.0], "electricity": [100.0], "hydrogen": [math.nan],
                           "methane": [80.0], "methane feedstock": [10.0], "naphtha": [30.0],
                           "process emission": [40.0]}, index=["GB"])
    out = trend_industry(src_c, src_eu, eu_b, eu_h, cols)
    energy = ["coal", "electricity", "hydrogen", "methane"]
    # total = EU energy 100 × GB/EU source 20/200
    assert out.loc["GB", energy].sum() == pytest.approx(10.0)
    # PatEx-term base shares: EU base share × (GB source share / EU source share)
    raw = {
        "coal": relative_share(0.2 * 0.25 / 0.1, 0.2, 0.1),
        "electricity": relative_share(0.4 * 0.5 / 0.5, 0.4, 0.5),
        "hydrogen": 0.2,  # no source: EU share
        "methane": relative_share(0.4 * 0.25 / 0.4, 0.4, 0.2),
    }
    assert out.at["GB", "coal"] == pytest.approx(10.0 * raw["coal"] / sum(raw.values()))
    assert out.at["GB", "process emission"] == pytest.approx(40.0 * 2.0 / 40.0)
    assert out.at["GB", "process emission from feedstock"] == pytest.approx(6.0 * 3.0 / 30.0)
    assert out.at["GB", "coke"] == 0.0


def test_parameters_dh_share_capped_ev_fleet_from_energy():
    out = trend_parameters(
        pd.Series({"GB": 0.02, "NO": 0.6}),
        pd.Series({"district heat share": 0.1}),
        pd.Series({"district heat share": 0.2, "district heating loss": 0.12,
                   "number bev": 1e6}),
        ev_energy_c=pd.Series({"GB": 2.0, "NO": 1.0}),
        ev_energy_eu=10.0,
        columns=["co2 stored", "number bev", "number phev", "district heat share",
                 "district heating loss"],
        base_load_factor=1.2,
    )
    assert out.at["GB", "district heat share"] == pytest.approx(0.04)
    assert out.at["NO", "district heat share"] == 1.0  # 1.2 capped
    assert out.at["GB", "number bev"] == pytest.approx(2e5)
    assert out["district heating loss"].eq(0.12).all()
    assert out["co2 stored"].isna().all()
    assert out["electricity base load factor"].eq(1.2).all()


def test_fallback_route_split_balances_and_keeps_carriers_non_negative():
    from patex_pypsa.export import MWH_NH3_PER_T
    from patex_pypsa.fallback import split_routes, with_routes

    eu_routes_b = pd.Series({"ammonia production": 1000.0, "ammonia|methane feedstock": 6.0})
    eu_routes_h = pd.Series({"ammonia production": 500.0, "ammonia|methane feedstock": 2.0,
                             "ammonia|process emission": 1.0})
    # EU industry with the route added back
    back = with_routes(pd.Series({"methane feedstock": 10.0, "process emission": 4.0}), eu_routes_h)
    assert back["methane feedstock"] == 12.0 and back["process emission"] == 5.0
    ind = pd.DataFrame({"methane feedstock": [3.0, 0.1], "process emission": [2.0, 0.0]},
                       index=["GB", "NO"])
    out = split_routes(ind, pd.DataFrame({"ammonia": [100.0, 200.0]}, index=["GB", "NO"]),
                       eu_routes_b, eu_routes_h)
    # production on the EU trend (× 0.5): 50 and 100 kt; route per kt at the horizon:
    # 0.004 TWh gas, 0.002 Mt CO2
    assert out.at["GB", "methane feedstock"] == pytest.approx(3.0 - 50 * 0.004)
    assert out.at["GB", "process emission"] == pytest.approx(2.0 - 50 * 0.002)
    assert out.at["NO", "methane feedstock"] == 0.0  # clipped at 0
    assert out.at["GB", "ammonia"] == pytest.approx(50 * MWH_NH3_PER_T / 1e3)


def test_waste_to_energy_on_eu_share_and_factor():
    src_c = pd.Series({"GB": 30.0, "NO": 4.0, "XX": 1.0})
    src_eu = pd.Series({"GB": 150.0, "NO": 160.0, "XX": 0.0})
    out = trend_waste_to_energy(src_c, src_eu, eu_fuel=60.0, eu_co2=21.0)
    assert out.at["GB", "fuel"] == pytest.approx(12.0)  # 60 × 30 / 150
    assert out.at["NO", "fuel"] == pytest.approx(1.5)
    assert out.at["GB", "co2"] == pytest.approx(12.0 * 0.35)
    assert out.at["XX", "fuel"] == 0.0  # no EU source: nothing, not inf
