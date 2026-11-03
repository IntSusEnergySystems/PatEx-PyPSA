"""Apply ``extraction_rules.csv`` to PatEx tidy tables.

A rule is one signed term: ``sign × Σ patex_variable[rows matching filters]``.
Rules sharing a ``category`` are summed, so a PyPSA-Eur column can be built
from several PatEx variables (e.g. heat incl. district heating minus ambient
heat). Rules with ``target = ignore`` produce no output; they declare slices
of a PatEx variable that are deliberately left out, so that
:func:`coverage` can flag everything else that no rule picks up.

Filter syntax: ``dim=a|b; other!=c`` (``=`` keeps the listed values, ``!=``
drops them, ``;`` combines conditions). An empty filter keeps every row.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .io import KEY_COLUMNS

logger = logging.getLogger(__name__)

IGNORE = "ignore"


@dataclass(frozen=True)
class Rule:
    category: str
    target: str
    sign: float
    variable: str
    filters: dict[str, tuple[bool, frozenset[str]]] = field(default_factory=dict)
    note: str = ""


def variable_unit(variable: str) -> str:
    """``"ind_emissions-by-material-by-type[MtCO2e]"`` → ``"MtCO2e"``."""
    return variable[variable.rindex("[") + 1 : -1]


def parse_filters(text: str) -> dict[str, tuple[bool, frozenset[str]]]:
    """``"a=x|y; b!=z"`` → ``{"a": (True, {"x", "y"}), "b": (False, {"z"})}``."""
    filters = {}
    for clause in str(text).split(";"):
        clause = clause.strip()
        if not clause or clause == "nan":
            continue
        if "!=" in clause:
            dim, values = clause.split("!=", 1)
            keep = False
        elif "=" in clause:
            dim, values = clause.split("=", 1)
            keep = True
        else:
            raise ValueError(f"filter clause without '=' or '!=': {clause!r}")
        filters[dim.strip()] = (keep, frozenset(v.strip() for v in values.split("|")))
    return filters


def load_rules(path: str | Path) -> list[Rule]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return [
        Rule(
            category=r.category,
            target=r.target,
            sign=float(r.sign or 1),
            variable=r.patex_variable,
            filters=parse_filters(r.filters),
            note=r.note,
        )
        for r in df.itertuples(index=False)
    ]


def rule_mask(table: pd.DataFrame, rule: Rule) -> pd.Series:
    """Rows of ``table`` selected by ``rule``; fails on unknown dimensions."""
    mask = pd.Series(True, index=table.index)
    for dim, (keep, values) in rule.filters.items():
        if dim not in table.columns:
            raise KeyError(
                f"rule {rule.category!r}: {rule.variable} has no dimension {dim!r} "
                f"(dimensions: {[c for c in table.columns if c != rule.variable]})"
            )
        # A typo in a filter value would silently yield 0 TWh: warn about it.
        unknown = values - set(table[dim].dropna().astype(str))
        if unknown:
            logger.warning(
                "rule %r: values %s not found in %s[%s]",
                rule.category, sorted(unknown), rule.variable, dim,
            )
        in_values = table[dim].astype(str).isin(values)
        mask &= in_values if keep else ~in_values
    return mask


def extract(
    tables: dict[str, pd.DataFrame],
    rules: list[Rule],
    country_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Long table ``target, category, country, year, unit, value`` (PyPSA country codes).

    ``unit`` is the one of the PatEx variable (TWh for energy, MtCO2e for emissions,
    number for vehicles); a category summing variables of different units fails.
    """
    parts = []
    for rule in rules:
        if rule.target == IGNORE:
            continue
        if rule.variable not in tables:
            raise KeyError(f"rule {rule.category!r}: PatEx variable {rule.variable!r} not in run")
        table = tables[rule.variable]
        sel = table[rule_mask(table, rule)]
        summed = (
            sel.groupby(list(KEY_COLUMNS))[rule.variable].sum().mul(rule.sign).rename("value")
        )
        parts.append(
            summed.reset_index().assign(
                target=rule.target, category=rule.category, unit=variable_unit(rule.variable)
            )
        )
    long = pd.concat(parts, ignore_index=True)
    units = long.groupby(["target", "category"])["unit"].nunique()
    if (units > 1).any():
        raise ValueError(f"categories mixing units: {sorted(units.index[units > 1])}")
    long = long.groupby(["target", "category", "Country", "Years", "unit"], as_index=False)[
        "value"
    ].sum()
    long = long.rename(columns={"Country": "country", "Years": "year"})
    long["year"] = long["year"].astype(int)
    if country_map:
        long["country"] = long["country"].replace(country_map)
    return long


def coverage(tables: dict[str, pd.DataFrame], rules: list[Rule]) -> pd.DataFrame:
    """Non-zero rows of the used PatEx variables that no rule (incl. ``ignore``) selects.

    Summed over countries and years per dimension combination. An empty result
    means every TWh of every source variable is either exported or explicitly
    ignored.
    """
    by_variable: dict[str, list[Rule]] = {}
    for rule in rules:
        by_variable.setdefault(rule.variable, []).append(rule)
    gaps = []
    for variable, var_rules in by_variable.items():
        if variable not in tables:
            continue
        table = tables[variable]
        matched = pd.Series(False, index=table.index)
        for rule in var_rules:
            matched |= rule_mask(table, rule)
        left = table[~matched & (table[variable].abs() > 1e-9)]
        if left.empty:
            continue
        dims = [c for c in left.columns if c not in (*KEY_COLUMNS, variable)]
        grouped = (
            left.groupby(dims, dropna=False)[variable].sum().rename("value_all_years").reset_index()
            if dims
            else pd.DataFrame({"value_all_years": [left[variable].sum()]})
        )
        grouped.insert(0, "patex_variable", variable)
        gaps.append(grouped)
    if not gaps:
        return pd.DataFrame(columns=["patex_variable", "value_all_years"])
    return pd.concat(gaps, ignore_index=True)


def signed_sum(frame: pd.DataFrame, expression: str) -> pd.Series:
    """``"a + b - c"`` over the columns of ``frame`` (names may contain spaces)."""
    total, sign = 0.0, 1
    for term in re.split(r" ([+-]) ", expression):
        if term in "+-":
            sign = 1 if term == "+" else -1
        else:
            total = total + sign * frame[term].fillna(0.0)
    return total
