"""Data-quality helpers for BTS Airline Delay Cause data."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

# Expected schema for this project
ID_COLS = ["year", "month", "carrier", "carrier_name", "airport", "airport_name"]
COUNT_COLS = [
    "arr_flights",
    "arr_del15",
    "carrier_ct",
    "weather_ct",
    "nas_ct",
    "security_ct",
    "late_aircraft_ct",
    "arr_cancelled",
    "arr_diverted",
]
DELAY_MINUTE_COLS = [
    "arr_delay",
    "carrier_delay",
    "weather_delay",
    "nas_delay",
    "security_delay",
    "late_aircraft_delay",
]
CAUSE_COUNT_COLS = [
    "carrier_ct",
    "weather_ct",
    "nas_ct",
    "security_ct",
    "late_aircraft_ct",
]
CAUSE_DELAY_COLS = [
    "carrier_delay",
    "weather_delay",
    "nas_delay",
    "security_delay",
    "late_aircraft_delay",
]
NUMERIC_COLS = COUNT_COLS + DELAY_MINUTE_COLS

# OpenFlights airports.dat — https://github.com/jpatokal/openflights/blob/master/data/airports.dat
OPENFLIGHTS_SOURCE_URL = (
    "https://github.com/jpatokal/openflights/blob/master/data/airports.dat"
)
OPENFLIGHTS_COLUMNS = [
    "airport_id",
    "name",
    "city",
    "country",
    "iata",
    "icao",
    "lat",
    "lon",
    "altitude_ft",
    "timezone_offset",
    "dst",
    "tz",
    "type",
    "source",
]

# Contiguous US + DC census regions (for one-hots / group comparisons)
US_CENSUS_REGION = {
    "CT": "Northeast",
    "ME": "Northeast",
    "MA": "Northeast",
    "NH": "Northeast",
    "RI": "Northeast",
    "VT": "Northeast",
    "NJ": "Northeast",
    "NY": "Northeast",
    "PA": "Northeast",
    "IL": "Midwest",
    "IN": "Midwest",
    "MI": "Midwest",
    "OH": "Midwest",
    "WI": "Midwest",
    "IA": "Midwest",
    "KS": "Midwest",
    "MN": "Midwest",
    "MO": "Midwest",
    "NE": "Midwest",
    "ND": "Midwest",
    "SD": "Midwest",
    "DE": "South",
    "DC": "South",
    "FL": "South",
    "GA": "South",
    "MD": "South",
    "NC": "South",
    "SC": "South",
    "VA": "South",
    "WV": "South",
    "AL": "South",
    "KY": "South",
    "MS": "South",
    "TN": "South",
    "AR": "South",
    "LA": "South",
    "OK": "South",
    "TX": "South",
    "AZ": "West",
    "CO": "West",
    "ID": "West",
    "MT": "West",
    "NV": "West",
    "NM": "West",
    "UT": "West",
    "WY": "West",
    "AK": "West",
    "CA": "West",
    "HI": "West",
    "OR": "West",
    "WA": "West",
}

TZ_TO_GROUP = {
    "America/New_York": "Eastern",
    "America/Chicago": "Central",
    "America/Denver": "Mountain",
    "America/Phoenix": "Mountain",  # no DST, still Mountain zone
    "America/Los_Angeles": "Pacific",
    "America/Anchorage": "Alaska",
    "Pacific/Honolulu": "Hawaii",
}


def load_delay_cause(csv_path) -> pd.DataFrame:
    """Load the Airline Delay Cause CSV and normalize column names."""
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def load_column_definitions(xlsx_path) -> pd.DataFrame:
    """Load the BTS column-definition workbook."""
    defs = pd.read_excel(xlsx_path)
    defs.columns = [c.strip() for c in defs.columns]
    return defs


def load_openflights_airports(dat_path) -> pd.DataFrame:
    """
    Load OpenFlights ``airports.dat`` and apply light cleaning.

    Source: https://github.com/jpatokal/openflights/blob/master/data/airports.dat
    (CSV, no header; missing values encoded as ``\\N``).

    Cleaning steps:
    - Assign OpenFlights column names
    - Convert ``\\N`` sentinels to null
    - Drop rows with no IATA code (cannot join to BTS ``airport``)
    - Uppercase / strip IATA codes
    - Keep one row per IATA (first occurrence)
    - Coerce lat/lon/altitude/timezone to numeric
    """
    air = pd.read_csv(
        dat_path,
        header=None,
        names=OPENFLIGHTS_COLUMNS,
        na_values=["\\N"],
    )
    air["iata"] = air["iata"].astype("string").str.strip().str.upper()
    air = air[air["iata"].notna() & (air["iata"] != "")].copy()
    air = air.drop_duplicates(subset=["iata"], keep="first")

    for col in ("lat", "lon", "altitude_ft", "timezone_offset"):
        air[col] = pd.to_numeric(air[col], errors="coerce")

    return air.reset_index(drop=True)


def parse_state_from_airport_name(airport_name: pd.Series) -> pd.Series:
    """Extract US state/DC abbreviation from BTS ``City, ST: Airport`` names."""
    return airport_name.astype("string").str.extract(r",\s*([A-Z]{2}):", expand=False)


def build_airport_lookup(
    airports: pd.DataFrame,
    airport_codes: Iterable[str] | None = None,
) -> pd.DataFrame:
    """
    Build a slim airport reference table for joining onto delay rows.

    If ``airport_codes`` is provided, keep only those IATA codes (avoids carrying
    the full worldwide OpenFlights file into the analysis table).
    """
    lookup = airports.rename(
        columns={
            "name": "of_airport_name",
            "city": "of_city",
            "country": "of_country",
        }
    ).copy()

    if airport_codes is not None:
        codes = {str(c).strip().upper() for c in airport_codes}
        lookup = lookup[lookup["iata"].isin(codes)].copy()

    lookup["tz_group"] = lookup["tz"].map(TZ_TO_GROUP).fillna("Other")
    keep = [
        "iata",
        "of_airport_name",
        "of_city",
        "of_country",
        "lat",
        "lon",
        "altitude_ft",
        "timezone_offset",
        "tz",
        "tz_group",
    ]
    return lookup[keep].reset_index(drop=True)


def join_airport_attributes(
    delay_df: pd.DataFrame,
    airports: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """
    Left-join OpenFlights attributes onto BTS delay rows on ``airport`` == ``iata``.

    Also parses ``state`` from BTS ``airport_name`` and maps ``census_region``.

    Returns ``(enriched_df, match_report)`` where ``match_report`` supports the
    P1 writeup (samples matched vs lost at airport and row level).
    """
    out = delay_df.copy()
    out["airport"] = out["airport"].astype("string").str.strip().str.upper()

    codes = out["airport"].dropna().unique().tolist()
    lookup = build_airport_lookup(airports, airport_codes=codes)

    before_rows = len(out)
    before_airports = int(out["airport"].nunique())
    matched_airports = set(lookup["iata"])
    delay_airports = set(codes)
    lost_airports = sorted(delay_airports - matched_airports)

    out = out.merge(lookup, how="left", left_on="airport", right_on="iata")
    if "iata" in out.columns:
        out = out.drop(columns=["iata"])

    out["state"] = parse_state_from_airport_name(out["airport_name"])
    out["census_region"] = out["state"].map(US_CENSUS_REGION)

    matched_rows = int(out["lat"].notna().sum())
    report = {
        "source": OPENFLIGHTS_SOURCE_URL,
        "n_openflights_with_iata": int(airports["iata"].nunique()),
        "n_airports_in_delay": before_airports,
        "n_airports_matched": before_airports - len(lost_airports),
        "n_airports_lost": len(lost_airports),
        "lost_airport_codes": lost_airports,
        "n_rows_before": before_rows,
        "n_rows_matched": matched_rows,
        "n_rows_unmatched": before_rows - matched_rows,
        "match_rate_airports": round(
            100 * (before_airports - len(lost_airports)) / max(before_airports, 1), 2
        ),
        "match_rate_rows": round(100 * matched_rows / max(before_rows, 1), 2),
    }
    return out, report


def missingness_report(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column null counts and percentages."""
    n = len(df)
    out = pd.DataFrame(
        {
            "null_count": df.isna().sum(),
            "null_pct": (df.isna().mean() * 100).round(3),
            "dtype": df.dtypes.astype(str),
        }
    )
    out["n_rows"] = n
    return out.sort_values("null_count", ascending=False)


def duplicate_key_report(
    df: pd.DataFrame,
    keys: Iterable[str] = ("year", "month", "carrier", "airport"),
) -> dict:
    """Check uniqueness of the natural grain (airport × carrier × year × month)."""
    keys = list(keys)
    dup_mask = df.duplicated(subset=keys, keep=False)
    return {
        "keys": keys,
        "n_rows": len(df),
        "n_unique_keys": int(df.groupby(keys).ngroups),
        "n_duplicate_rows": int(dup_mask.sum()),
        "example_duplicates": df.loc[dup_mask].sort_values(keys).head(10),
    }


def logical_checks(df: pd.DataFrame, cause_tol: float = 1.0) -> pd.DataFrame:
    """
    Flag rows that violate basic domain rules.

    BTS cause counts can be fractional (shared attribution), so the sum of
    cause counts is allowed to differ from arr_del15 by ``cause_tol``.
    """
    checks = pd.DataFrame(index=df.index)
    checks["neg_arr_flights"] = df["arr_flights"] < 0
    checks["neg_arr_del15"] = df["arr_del15"] < 0
    checks["del15_gt_flights"] = df["arr_del15"] > df["arr_flights"]
    checks["cancel_gt_flights"] = df["arr_cancelled"] > df["arr_flights"]
    checks["divert_gt_flights"] = df["arr_diverted"] > df["arr_flights"]
    checks["bad_month"] = ~df["month"].between(1, 12)
    checks["neg_delay_minutes"] = df[DELAY_MINUTE_COLS].lt(0).any(axis=1)

    cause_sum = df[CAUSE_COUNT_COLS].sum(axis=1)
    checks["cause_sum_mismatch"] = (cause_sum - df["arr_del15"]).abs() > cause_tol

    delay_sum = df[CAUSE_DELAY_COLS].sum(axis=1)
    checks["delay_sum_mismatch"] = (delay_sum - df["arr_delay"]).abs() > cause_tol

    summary = checks.sum().rename("flagged_rows").to_frame()
    summary["flagged_pct"] = (summary["flagged_rows"] / len(df) * 100).round(3)
    summary.attrs["detail"] = checks
    return summary


def iqr_outlier_mask(series: pd.Series, k: float = 1.5) -> pd.Series:
    """Boolean mask for Tukey IQR outliers (True = outlier)."""
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return (series < lower) | (series > upper)


def outlier_summary(
    df: pd.DataFrame,
    cols: Iterable[str] | None = None,
    k: float = 1.5,
) -> pd.DataFrame:
    """IQR outlier counts for numeric columns (flag-only; does not drop)."""
    cols = list(cols) if cols is not None else [
        c for c in NUMERIC_COLS if c in df.columns
    ]
    rows = []
    for col in cols:
        s = pd.to_numeric(df[col], errors="coerce")
        mask = iqr_outlier_mask(s.dropna(), k=k)
        n = int(mask.sum())
        rows.append(
            {
                "column": col,
                "n_non_null": int(s.notna().sum()),
                "n_outliers_iqr": n,
                "outlier_pct": round(100 * n / max(s.notna().sum(), 1), 3),
            }
        )
    return pd.DataFrame(rows)


def summarize_numeric(df: pd.DataFrame, cols: Iterable[str] | None = None) -> pd.DataFrame:
    """Lesson-4 style summary: center, spread, shape."""
    cols = list(cols) if cols is not None else [
        c for c in NUMERIC_COLS if c in df.columns
    ]
    rows = []
    for col in cols:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append(
            {
                "column": col,
                "n": int(s.shape[0]),
                "mean": s.mean(),
                "median": s.median(),
                "std": s.std(ddof=1),
                "min": s.min(),
                "p25": s.quantile(0.25),
                "p75": s.quantile(0.75),
                "max": s.max(),
                "skew": s.skew(),
                "kurtosis": s.kurtosis(),  # excess kurtosis (pandas)
            }
        )
    return pd.DataFrame(rows).set_index("column")


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add delay rates and a year-month period for plotting."""
    out = df.copy()
    out["period"] = pd.to_datetime(
        dict(year=out["year"], month=out["month"], day=1)
    )
    flights = out["arr_flights"].replace(0, np.nan)
    out["pct_delayed"] = 100 * out["arr_del15"] / flights
    out["pct_cancelled"] = 100 * out["arr_cancelled"] / flights
    out["avg_delay_min_per_delayed"] = out["arr_delay"] / out["arr_del15"].replace(0, np.nan)
    out["cause_count_sum"] = out[CAUSE_COUNT_COLS].sum(axis=1)
    out["cause_delay_sum"] = out[CAUSE_DELAY_COLS].sum(axis=1)
    return out


def clean_delay_cause(df: pd.DataFrame) -> pd.DataFrame:
    """
    Light cleaning suitable for EDA / submission notebooks.

    - Coerce numerics
    - Drop exact duplicate keys keeping first
    - Fill the rare null arr_del15 with 0 when arr_flights == 0, else leave NaN
    - Add derived features
    """
    out = df.copy()
    for c in NUMERIC_COLS:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    keys = ["year", "month", "carrier", "airport"]
    out = out.drop_duplicates(subset=keys, keep="first")

    # One common edge case: airport/carrier month with no arrivals
    null_del = out["arr_del15"].isna()
    out.loc[null_del & (out["arr_flights"].fillna(0) == 0), "arr_del15"] = 0.0

    out = add_derived_features(out)
    return out.reset_index(drop=True)


def quality_overview(df: pd.DataFrame) -> dict:
    """One-shot dictionary used by the notebook for a cleanliness snapshot."""
    miss = missingness_report(df)
    dups = duplicate_key_report(df)
    logic = logical_checks(df)
    return {
        "n_rows": len(df),
        "n_cols": df.shape[1],
        "date_span": (
            lambda s, e: (
                f"{int(s['year'])}-{int(s['month']):02d}"
                f" → {int(e['year'])}-{int(e['month']):02d}"
            )
        )(
            df.sort_values(["year", "month"]).iloc[0],
            df.sort_values(["year", "month"]).iloc[-1],
        ),
        "n_carriers": int(df["carrier"].nunique()),
        "n_airports": int(df["airport"].nunique()),
        "total_nulls": int(df.isna().sum().sum()),
        "cols_with_nulls": int((miss["null_count"] > 0).sum()),
        "duplicate_key_rows": dups["n_duplicate_rows"],
        "logical_flags": logic,
        "missingness": miss,
        "duplicates": dups,
    }
