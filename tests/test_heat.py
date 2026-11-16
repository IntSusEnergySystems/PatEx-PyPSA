"""PatEx useful building heat and heating efficiencies (audit #4)."""

import pandas as pd
import pytest

from patex_pypsa import patex_heating_efficiencies
from patex_pypsa.export import HEAT_COLUMNS, horizon_tables
from patex_pypsa.heat import (
    EFFICIENCY,
    EFFICIENCY_COLUMNS,
    FINAL,
    INCL_DH,
    MIX,
    heating_efficiencies,
    useful_heat,
)

RES, NONRES = "residential", "non-residential"

#: (technology, carrier) → efficiency; heat pump: 1/2 + 1/2 = 1
EFF = {
    ("gaseous-ff-natural", "gaseous-ff-natural"): 0.9,
    ("liquid-ff-oil", "liquid-ff-oil"): 0.85,
    ("solid-biomass", "solid-biomass"): 0.8,
    ("solid-ff-coal", "solid-ff-coal"): 0.8,
    ("elec-hp", "ambiant"): 2.0,
    ("elec-hp", "electricity"): 2.0,
    ("elec-direct", "electricity"): 0.9,
    ("solar-thermal", "ambiant"): 1.0,
}
#: end-use → technology mix (heat pumps for space heating, solar thermal for hot water)
MIX_BY_USE = {
    "heating": {"elec-hp": 0.4, "solar-thermal": 0.0},
    "hotwater": {"elec-hp": 0.0, "solar-thermal": 0.1},
}


def _tech(year=2030):
    rows = []
    for bt in (RES, NONRES):
        for eu in ("heating", "hotwater"):
            for (ewp, ec), e in EFF.items():
                rows.append((("BE", year, bt, eu, ewp, ec, e, MIX_BY_USE[eu].get(ewp, 0.1))))
    return pd.DataFrame(
        rows,
        columns=["Country", "Years", "building-type", "end-use", "energy-way-of-prod",
                 "energy-carrier", EFFICIENCY, MIX],
    )


def _tables(res_heating_electricity=5.0, extra=None):
    final = {
        (RES, "heating"): {"gaseous-ff-natural": 10.0, "gaseous-bio": 2.0,
                           "electricity": res_heating_electricity, "ambiant": 4.0,
                           "solid-biomass": 1.0},
        (RES, "hotwater"): {"gaseous-ff-natural": 2.0, "ambiant": 0.5, "electricity": 1.0},
        (NONRES, "heating"): {"liquid-ff-oil": 4.0},
    }
    if extra:
        final[(RES, "heating")].update(extra)
    district = {(RES, "heating"): 5.0, (NONRES, "heating"): 1.0}
    rows = [("BE", 2030, bt, eu, c, v) for (bt, eu), carriers in final.items()
            for c, v in carriers.items()]
    rows.append(("BE", 2030, RES, "cooking", "gaseous-ff-natural", 99.0))  # not heat
    w = pd.DataFrame(rows, columns=["Country", "Years", "building-type", "end-use",
                                    "energy-carrier", FINAL])
    incl = [("BE", 2030, bt, eu, sum(final.get((bt, eu), {}).values()) + district.get((bt, eu), 0.0))
            for bt in (RES, NONRES) for eu in ("heating", "hotwater")]
    incl = pd.DataFrame(incl, columns=["Country", "Years", "building-type", "end-use", INCL_DH])
    return {FINAL: w, INCL_DH: incl}


def test_useful_heat_by_technology():
    final, useful = useful_heat(_tables(), _tech(), 2030)
    # space heating: gas + biogas at the gas boiler's 0.9, biomass 0.8; ambient 4 all
    # heat pump -> its electricity 4 x 2/2 = 4 of 5, output 4 + 4; direct 1 x 0.9; DH 5
    assert useful.at["BE", "total residential space"] == pytest.approx(12 * 0.9 + 0.8 + 8 + 0.9 + 5)
    assert final.at["BE", "total residential space"] == pytest.approx(27 - 4)  # without ambient
    # hot water: ambient = solar thermal (no heat pumps in the mix), electricity direct
    assert useful.at["BE", "total residential water"] == pytest.approx(1.8 + 0.5 + 0.9)
    assert final.at["BE", "total residential water"] == pytest.approx(3.0)
    assert useful.at["BE", "total services space"] == pytest.approx(4 * 0.85 + 1)
    assert final.at["BE", "total services water"] == 0.0
    eff = heating_efficiencies(final, useful)
    assert list(eff.columns) == EFFICIENCY_COLUMNS
    assert eff.at["BE", "total residential space efficiency"] == pytest.approx(25.5 / 23)
    assert eff.at["BE", "total services water efficiency"] == 1.0  # no heat


def test_heat_pump_electricity_capped_at_reported(caplog):
    # ambient 4 needs 4 of electricity at PatEx's COP, only 3 reported (calibration)
    _, useful = useful_heat(_tables(res_heating_electricity=3.0), _tech(), 2030)
    assert useful.at["BE", "total residential space"] == pytest.approx(12 * 0.9 + 0.8 + 3 + 4 + 5)
    assert "more heat-pump electricity" in caplog.text


def test_unknown_carrier_and_missing_year_fail():
    with pytest.raises(ValueError, match="without a PatEx technology"):
        useful_heat(_tables(extra={"heat": 1.0}), _tech(), 2030)
    with pytest.raises(ValueError, match="no PatEx heating efficiencies"):
        useful_heat(_tables(), _tech(2040), 2030)


def test_patex_efficiencies_replace_pypsa_ones_where_given():
    pypsa = pd.DataFrame(0.8, index=["BE", "GB", "NL"], columns=EFFICIENCY_COLUMNS + ["other"])
    params = pd.DataFrame({c: [1.1, float("nan")] for c in EFFICIENCY_COLUMNS}, index=["BE", "GB"])
    out = patex_heating_efficiencies(pypsa, params)
    assert (out.loc["BE", EFFICIENCY_COLUMNS] == 1.1).all()
    assert (out.loc[["GB", "NL"], EFFICIENCY_COLUMNS] == 0.8).all().all()  # fallback, no PatEx
    assert (out["other"] == 0.8).all()
    with pytest.raises(ValueError, match="re-export"):
        patex_heating_efficiencies(pypsa, params.drop(columns=EFFICIENCY_COLUMNS[0]))


def test_district_heat_share_on_useful_heat():
    long = pd.DataFrame(
        [("parameters", "district heat", "BE", 2030, "TWh", 6.0)]
        + [("energy_totals", c, "BE", 2030, "TWh", 10.0) for c in HEAT_COLUMNS],
        columns=["target", "category", "country", "year", "unit", "value"],
    )
    eff = pd.DataFrame({c: [0.5] for c in EFFICIENCY_COLUMNS}, index=["BE"])
    out = horizon_tables(long, 2030, heat_efficiency=eff)["parameters"]
    assert out.at["BE", "district heat share"] == pytest.approx(6.0 / 20.0)  # useful 4 x 5
    assert out.at["BE", "total residential space efficiency"] == 0.5
    assert horizon_tables(long, 2030)["parameters"].at["BE", "district heat share"] == (
        pytest.approx(6.0 / 40.0)  # final base without efficiencies
    )
