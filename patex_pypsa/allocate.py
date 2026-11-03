"""Put PatEx country totals onto PyPSA-Eur nodes.

PyPSA-Eur builds nodal annual demands (``pop_weighted_energy_totals.csv``,
``industrial_energy_demand_{h}.csv``) from country totals and a distribution
key (population, industrial sites). Rather than re-inventing those keys, the
soft-link keeps PyPSA's intra-country distribution and only rescales each
country so that it sums to the PatEx total. This is the multi-country version
of what pypsa-wal does for the single Walloon node.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def override_country_totals(
    nodal: pd.DataFrame,
    country_totals: pd.DataFrame,
    node_country: pd.Series,
    fallback_weights: pd.Series,
    scale: float = 1.0,
) -> pd.DataFrame:
    """Replace the columns of ``nodal`` present in ``country_totals``.

    Parameters
    ----------
    nodal
        node × column annual values from PyPSA-Eur.
    country_totals
        country × column PatEx totals (TWh/a, PyPSA country codes).
    node_country
        node → country code (``pop_layout.ct``).
    fallback_weights
        node → share of its country, used where PyPSA's own value is zero for
        the whole country (``pop_layout.fraction``).
    scale
        unit factor applied to ``country_totals`` (1 for TWh, 1e6 for MWh).

    Countries absent from ``country_totals`` keep their PyPSA-Eur values.
    """
    out = nodal.copy()
    columns = nodal.columns.intersection(country_totals.columns)
    countries = node_country.loc[nodal.index]
    missing = sorted(set(countries) - set(country_totals.index))
    if missing:
        logger.warning("no PatEx totals for %s: PyPSA-Eur values kept", missing)
    for ct in country_totals.index.intersection(countries.unique()):
        nodes = countries.index[countries == ct]
        current = nodal.loc[nodes, columns]
        sums = current.sum()
        shares = current.div(sums.where(sums != 0))
        weights = fallback_weights.loc[nodes] / fallback_weights.loc[nodes].sum()
        shares = shares.apply(lambda s: s.fillna(weights))
        out.loc[nodes, columns] = shares.mul(country_totals.loc[ct, columns] * scale)
    return out
