"""Binary feature helpers for association rule mining (mlxtend)."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .cleaning import CAUSE_DELAY_COLS

# Default carriers / airports kept as one-hots (high volume in this extract)
DEFAULT_TOP_CARRIERS = ("AA", "DL", "UA", "WN", "B6", "AS", "NK", "F9")
DEFAULT_TOP_AIRPORTS = (
    "ATL",
    "ORD",
    "DFW",
    "DEN",
    "LAX",
    "CLT",
    "SEA",
    "SFO",
    "JFK",
    "EWR",
    "LGA",
    "MIA",
)


def _share(numer: pd.Series, denom: pd.Series) -> pd.Series:
    d = denom.replace(0, np.nan)
    return numer / d


def build_transaction_matrix(
    df: pd.DataFrame,
    *,
    delay_q: float = 0.75,
    cancel_q: float = 0.75,
    cause_share_threshold: float = 0.35,
    high_altitude_ft: float = 3000.0,
    top_carriers: Iterable[str] | None = DEFAULT_TOP_CARRIERS,
    top_airports: Iterable[str] | None = DEFAULT_TOP_AIRPORTS,
) -> tuple[pd.DataFrame, dict]:
    """
    Build a boolean (0/1) item matrix for apriori / fpgrowth.

    Each row is still one carrier × airport × year × month. Continuous fields
    are discretized with inequalities; categoricals become one-hot dummies.

    Returns ``(binary_df, meta)`` where ``meta`` records thresholds used.
    """
    work = df.copy()
    if "arr_delay" not in work.columns:
        raise ValueError("Expected arr_delay column for cause-share features")

    delay_cut = float(work["pct_delayed"].quantile(delay_q))
    cancel_cut = float(work["pct_cancelled"].quantile(cancel_q))
    lat_med = float(work["lat"].median()) if "lat" in work.columns else np.nan

    items: dict[str, pd.Series] = {}

    # --- discretized outcomes / ops ---
    items["high_delay"] = work["pct_delayed"] >= delay_cut
    items["high_cancel"] = work["pct_cancelled"] >= cancel_cut

    # Cause dominance from delay-minute shares
    for col in CAUSE_DELAY_COLS:
        share = _share(work[col], work["arr_delay"])
        short = col.replace("_delay", "")
        items[f"{short}_dominant"] = share >= cause_share_threshold

    # Season from month
    month = work["month"].astype(int)
    items["is_winter"] = month.isin([12, 1, 2])
    items["is_spring"] = month.isin([3, 4, 5])
    items["is_summer"] = month.isin([6, 7, 8])
    items["is_fall"] = month.isin([9, 10, 11])

    # Geography from OpenFlights join (if present)
    if "census_region" in work.columns:
        for region in sorted(work["census_region"].dropna().unique()):
            items[f"region_{region}"] = work["census_region"] == region
    if "tz_group" in work.columns:
        for tz in sorted(work["tz_group"].dropna().unique()):
            items[f"tz_{tz}"] = work["tz_group"] == tz
    if "altitude_ft" in work.columns:
        items["high_altitude"] = work["altitude_ft"] >= high_altitude_ft
    if "lat" in work.columns and np.isfinite(lat_med):
        items["northern"] = work["lat"] >= lat_med

    # One-hot top carriers / airports (keeps matrix manageable)
    if top_carriers is not None:
        carriers = {str(c).upper() for c in top_carriers}
        for c in sorted(carriers):
            items[f"carrier_{c}"] = work["carrier"].astype(str).str.upper() == c
    if top_airports is not None:
        airports = {str(a).upper() for a in top_airports}
        for a in sorted(airports):
            items[f"airport_{a}"] = work["airport"].astype(str).str.upper() == a

    binary = pd.DataFrame(items, index=work.index)
    # mlxtend expects 0/1 ints or bools; drop rows with any NA in items
    binary = binary.fillna(False).astype(bool)
    # Drop empty columns (all False) — can happen if a top carrier isn't in extract
    binary = binary.loc[:, binary.any(axis=0)].copy()

    meta = {
        "n_rows": int(len(binary)),
        "n_items": int(binary.shape[1]),
        "delay_q": delay_q,
        "delay_cut_pct": delay_cut,
        "cancel_q": cancel_q,
        "cancel_cut_pct": cancel_cut,
        "cause_share_threshold": cause_share_threshold,
        "high_altitude_ft": high_altitude_ft,
        "lat_median": lat_med,
        "item_names": list(binary.columns),
        "item_support": binary.mean().sort_values(ascending=False),
    }
    return binary, meta
