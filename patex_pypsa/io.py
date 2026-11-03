"""Read PatEx results into tidy tables, without importing ``patex``.

``patex run ... -o run.pkl`` writes the *legacy* output dict: one stacked
DataFrame per module (``bld_out_1``, ``tra_out_1``, ...) where several variables
with different dimensions share rows, each variable holding NaN in the value
and dimension columns of the others. :func:`split_stacked` does what
``patex.legacy_adapter.split_legacy`` does, so this package only needs pandas
and can run in the PyPSA-Eur environment as well as in the PatEx one.
"""

from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

import pandas as pd

#: Dimension columns present in every PatEx variable.
KEY_COLUMNS = ("Country", "Years")


def is_value_column(column: str) -> bool:
    """PatEx variables are named ``<prefix>_<name>[<unit>]``."""
    return isinstance(column, str) and column.endswith("]") and "[" in column


def split_stacked(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split one stacked legacy frame into ``{variable: tidy table}``.

    Each tidy table holds ``Country``, ``Years``, the dimension columns used by
    the variable, and one value column named after the variable.
    """
    value_columns = [c for c in frame.columns if is_value_column(c)]
    dim_columns = [c for c in frame.columns if not is_value_column(c)]
    tables = {}
    for variable in value_columns:
        rows = frame[frame[variable].notna()]
        dims = [c for c in dim_columns if rows[c].notna().any()]
        tables[variable] = rows[dims + [variable]].reset_index(drop=True)
    return tables


def load_patex_tables(path: str | Path) -> dict[str, pd.DataFrame]:
    """Every output variable of a PatEx run, from a ``patex run -o`` pickle."""
    path = Path(path)
    if path.suffix != ".pkl":
        raise ValueError(
            f"{path}: expected the pickle written by `patex run ... -o run.pkl`"
        )
    with open(path, "rb") as f:
        legacy = pickle.load(f)
    tables: dict[str, pd.DataFrame] = {}
    for key, frame in legacy.items():
        if key == "metrics":
            continue
        tables.update(split_stacked(frame))
    return tables


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
