import sys
from pathlib import Path

import pandas as pd
import pytest

pypsa = pytest.importorskip("pypsa")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from co2_by_sector import co2_by_sector  # noqa: E402


def test_bio_credit_moves_to_consumers_and_total_is_kept():
    n = pypsa.Network()
    n.set_snapshots(pd.RangeIndex(2))
    for bus, carrier in [("BE0 gas", "gas"), ("BE0 biogas", "biogas"), ("co2 atmosphere", "co2"),
                         ("BE0 heat", "heat"), ("BE0 ind", "gas for industry")]:
        n.add("Bus", bus, carrier=carrier, location="BE0" if bus != "co2 atmosphere" else "EU")
    n.add("Generator", "fossil gas", bus="BE0 gas", carrier="gas", p_nom=100, marginal_cost=1)
    n.add("Generator", "biogas", bus="BE0 biogas", carrier="biogas", p_nom=25)
    n.add("Store", "co2 atmosphere", bus="co2 atmosphere", e_nom=1e9, e_min_pu=-1, carrier="co2")
    n.add("Link", "BE0 biogas to gas", bus0="BE0 biogas", bus1="BE0 gas", bus2="co2 atmosphere",
          carrier="biogas to gas", efficiency2=-0.2, p_nom=25)
    n.add("Link", "BE0 rural gas boiler", bus0="BE0 gas", bus1="BE0 heat", bus2="co2 atmosphere",
          carrier="rural gas boiler", efficiency2=0.2, p_nom=100)
    n.add("Link", "BE0 gas for industry", bus0="BE0 gas", bus1="BE0 ind", bus2="co2 atmosphere",
          carrier="gas for industry", efficiency2=0.2, p_nom=100)
    n.add("Load", "heat", bus="BE0 heat", p_set=60)
    n.add("Load", "ind", bus="BE0 ind", p_set=40)
    n.optimize()
    table, atmosphere = co2_by_sector(n)
    t = table.loc["BE"]
    # 2 h: 200 MWh burnt (40 gross Mt-units), 50 MWh biogas (-10) → 25 % of the credit each way
    w = 8760 / 2 / 1e6
    assert t.loc["buildings", "gross"] == pytest.approx(60 * 2 * 0.2 * w)
    assert t.loc["buildings", "bio credit"] == pytest.approx(-25 * 2 * 0.2 * 0.6 * w)
    assert t.loc["industry", "bio credit"] == pytest.approx(-25 * 2 * 0.2 * 0.4 * w)
    assert t.loc["fuel supply", "net"] == pytest.approx(0.0, abs=1e-9)
    assert table["net"].sum() == pytest.approx(atmosphere)
