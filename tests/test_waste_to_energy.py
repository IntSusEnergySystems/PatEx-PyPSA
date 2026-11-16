"""Non-renewable waste burned in PatEx's power and heat plants (audit #2)."""

import pandas as pd
import pytest

from patex_pypsa.emissions import (
    FACTOR,
    GROSS_BY_FUEL,
    NET_BY_FUEL,
    SANKEY,
    waste_to_energy,
)


def _tables(heat_res=3.0):
    sankey = pd.DataFrame(
        {
            "Country": ["BE", "BE", "BE"],
            "Years": [2040] * 3,
            "source": ["transformation-input", "transformation-input", "primary-production"],
            "target": ["electricity", "heat", "available-from-all-sources"],
            "label": ["solid-waste"] * 3,
            SANKEY: [10.0, 20.0, 99.0],
        }
    )
    net = pd.DataFrame(
        {
            "Country": ["BE"] * 3,
            "Years": [2040] * 3,
            "energy-carrier": ["electricity"] * 3,
            "way-of-production": ["CHP", "elec-plant-with-solid-bio-waste", "elec-plant-with-solid-bio-waste"],
            "primary-energy-carrier": ["solid-waste-nonres", "solid-waste-res", "solid-biomass"],
            NET_BY_FUEL: [1.0, 3.0, 50.0],
        }
    )
    gross = pd.DataFrame(
        {
            "Country": ["BE", "BE"],
            "Years": [2040, 2040],
            "energy-carrier": ["heat", "heat"],
            "way-of-production": ["heat-plant", "heat-plant"],
            "primary-energy-carrier": ["solid-waste-nonres", "solid-waste-res"],
            GROSS_BY_FUEL: [1.0, heat_res],
        }
    )
    return {SANKEY: sankey, NET_BY_FUEL: net, GROSS_BY_FUEL: gross}


FACTORS = pd.DataFrame(
    {"Country": ["BE"], "sector": ["elc"], "energy-carrier": ["solid-waste-nonres"], FACTOR: [0.357]}
)


def test_fuel_split_by_production_share_and_co2_factor():
    out = waste_to_energy(_tables(), FACTORS, 2040)
    # electricity input 10 × 1/4 (biomass not waste) + heat input 20 × 1/4
    assert out.at["BE", "fuel"] == pytest.approx(7.5)
    assert out.at["BE", "co2"] == pytest.approx(7.5 * 0.357)


def test_carrier_without_production_takes_the_other_split():
    t = _tables()
    t[GROSS_BY_FUEL] = t[GROSS_BY_FUEL].iloc[:0]  # heat input, no heat production
    out = waste_to_energy(t, FACTORS, 2040)
    assert out.at["BE", "fuel"] == pytest.approx(30.0 * 0.25)


def test_fuel_without_production_fails():
    t = _tables()
    t[GROSS_BY_FUEL] = t[GROSS_BY_FUEL].iloc[:0]
    t[NET_BY_FUEL] = t[NET_BY_FUEL].iloc[:0]
    with pytest.raises(ValueError, match="without waste production"):
        waste_to_energy(t, FACTORS, 2040)


def test_missing_factor_fails():
    with pytest.raises(ValueError, match="power CO2 factor"):
        waste_to_energy(_tables(), FACTORS.iloc[:0], 2040)
