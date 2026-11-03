"""PatEx land-transport energy per fuel → PyPSA-Eur land-transport loads.

PyPSA-Eur builds land transport as three loads: electricity on the EV battery bus,
hydrogen for fuel-cell vehicles and oil for ICEs. Each is
``share × driven distance(t) / efficiency(t)``, with a distance derived from today's
energy and EU-wide shares (``sector.land_transport_*_share``).

PatEx gives the final energy per fuel directly, so the loads are set to it: each
load keeps PyPSA-Eur's hourly profile (``distance(t) / efficiency(t)``, i.e. traffic
and temperature) and is scaled to PatEx's energy. No distance and no vehicle
efficiency enter the totals. The EV fleet, which sizes chargers, smart charging and
V2G, comes from PatEx as well (``number evs``).
"""

from __future__ import annotations

import pandas as pd

ENGINES = ["electric", "fuel_cell", "ice"]


def land_transport_scale(
    unit_profiles: dict[str, pd.DataFrame],
    energy: pd.DataFrame,
    weights: pd.Series,
) -> pd.DataFrame:
    """node × engine factors that scale PyPSA-Eur's load profiles to PatEx's energy.

    Parameters
    ----------
    unit_profiles
        engine → snapshot × node load profile of PyPSA-Eur for a share of 1 (MW).
    energy
        node × engine final energy over the modelled period (MWh).
    weights
        snapshot weightings (h).

    Returns
    -------
    node × engine factor, used by PyPSA-Eur in place of the drivetrain share:
    ``factor × unit profile`` sums to ``energy``. 0 where PatEx has no energy.
    """
    nodes = energy.index
    out = pd.DataFrame(0.0, index=nodes, columns=ENGINES)
    for engine in ENGINES:
        annual = unit_profiles[engine][nodes].mul(weights, axis=0).sum()
        out[engine] = (energy[engine] / annual.where(annual > 0)).fillna(0.0)
    return out
