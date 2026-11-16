"""Per-country hourly space-cooling slopes from the Hotmaps generic cooling profiles.

    python scripts/hotmaps_cooling_table.py <residential.csv> <tertiary.csv> <out.csv>

Inputs (CC BY 4.0, Hotmaps project, H2020 grant 723677; Kuehnbach, Marwitz, Klingler,
Fraunhofer ISI; Pezzutto et al. 2019, "Hotmaps D2.3 WP2 Report - Open Data Set for the
EU28", section 2.7.2-2.7.3):

- https://gitlab.com/hotmaps/load_profile/load_profile_residential_cooling_generic
  (data/hotmaps_task_2.7_load_profile_residential_cooling_generic.csv)
- https://gitlab.com/hotmaps/load_profile/load_profile_tertiary_cooling_generic
  (data/hotmaps_task_2.7_load_profile_tertiary_cooling_generic.csv)

Each file gives, per NUTS2 region, day type (0 weekday, 1 Saturday or day before a
holiday, 2 Sunday or holiday), hour of the day (1-24, local time) and daily mean outdoor
temperature level (19-40 °C; none at 18 °C or below), a unitless load. The load is linear
in (T - 18 °C) and the same for every NUTS2 region of a country, so the output keeps one
slope per country, sector, day type and hour:
``load = slope × max(T_daily_mean - 18 °C, 0)``. The script checks both properties.
Country codes are PyPSA-Eur's (UK -> GB, EL -> GR).
"""

import sys

import pandas as pd

BASE_TEMPERATURE = 18.0
CODES = {"UK": "GB", "EL": "GR"}

if __name__ == "__main__":
    residential, tertiary, out = sys.argv[1:4]
    frames = []
    for sector, path in (("residential", residential), ("services", tertiary)):
        df = pd.read_csv(path)
        df["slope"] = df["load"] / (df["temperature"] - BASE_TEMPERATURE)
        keys = ["NUTS2_code", "day_type", "hour"]
        spread = df.groupby(keys)["slope"].agg(lambda s: s.max() - s.min()).max()
        if spread > 1e-5:
            raise ValueError(f"{path}: load not linear in (T - 18 °C) ({spread})")
        slope = df.groupby(keys)["slope"].mean().reset_index()
        slope["country"] = slope["NUTS2_code"].str[:2].replace(CODES)
        spread = slope.groupby(["country", "day_type", "hour"])["slope"].agg(
            lambda s: s.max() - s.min()
        ).max()
        if spread > 1e-9:
            raise ValueError(f"{path}: NUTS2 regions of a country differ ({spread})")
        table = slope.groupby(["country", "day_type", "hour"])["slope"].first()
        frames.append(table.rename(sector))
    result = pd.concat(frames, axis=1).round(9)
    result.index.names = ["country", "day_type", "hour"]
    result.to_csv(out)
    print(f"wrote {out}: {result.index.get_level_values(0).nunique()} countries")
