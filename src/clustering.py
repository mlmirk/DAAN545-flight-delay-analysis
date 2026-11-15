"""Clustering helpers for carrier–airport–month delay profiles.

K-Means and Ward hierarchical clustering share one scaled feature matrix.
PCA is used for the scatter plots. It becomes the clustering space only when
the first two components explain most of the variance.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from .cleaning import CAUSE_DELAY_COLS, iqr_outlier_mask

# Security's share of delay minutes is tiny in this extract; we drop it
# inside prepare_cluster_frame if its standard deviation is below this.
SECURITY_SHARE_STD_FLOOR = 0.02
# Cluster in the first two PCs only when they carry at least this much variance.
PCA_CLUSTER_VARIANCE = 0.70
K_RANGE = range(2, 9)
RANDOM_STATE = 42
SLOT_AIRPORTS = frozenset({"JFK", "LGA", "EWR", "DCA"})

CAUSE_SHARE_MAP = {
    "carrier_delay": "share_carrier",
    "weather_delay": "share_weather",
    "nas_delay": "share_nas",
    "security_delay": "share_security",
    "late_aircraft_delay": "share_late_aircraft",
}

RATE_FEATURES = ["pct_delayed", "pct_cancelled"]
CORE_SHARE_FEATURES = [
    "share_carrier",
    "share_weather",
    "share_nas",
    "share_late_aircraft",
]


def prepare_cluster_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Build one row per carrier–airport–month with delay rates and cause shares.

    Months below the 10th percentile of ``arr_flights`` are left out. A few
    flights can make ``pct_delayed`` jump around, so those rows are a weak
    basis for a cluster. Cause shares are delay minutes / ``arr_delay``.
    Months with no delay minutes get share 0.
    """
    work = df.copy()
    flights = work["arr_flights"]
    flight_cut = float(flights.quantile(0.10))
    keep = flights.notna() & (flights >= flight_cut)
    keep &= work["pct_delayed"].notna() & work["pct_cancelled"].notna()
    out = work.loc[keep].copy()

    delay_minutes = out["arr_delay"].replace(0, np.nan)
    for src, dest in CAUSE_SHARE_MAP.items():
        out[dest] = out[src] / delay_minutes
        out[dest] = out[dest].fillna(0.0)

    security_std = float(out["share_security"].std(ddof=1))
    features = list(RATE_FEATURES) + list(CORE_SHARE_FEATURES)
    dropped_security = security_std < SECURITY_SHARE_STD_FLOOR
    if not dropped_security:
        features.append("share_security")

    out["iqr_outlier_pct_delayed"] = iqr_outlier_mask(out["pct_delayed"], k=1.5)
    month = out["month"].astype(int)
    out["season"] = np.select(
        [
            month.isin([12, 1, 2]),
            month.isin([3, 4, 5]),
            month.isin([6, 7, 8]),
            month.isin([9, 10, 11]),
        ],
        ["winter", "spring", "summer", "fall"],
        default="other",
    )

    meta = {
        "n_rows_in": int(len(df)),
        "n_rows_clustered": int(len(out)),
        "n_rows_dropped": int(len(df) - len(out)),
        "min_arr_flights": flight_cut,
        "flight_cutoff_rule": "10th percentile of arr_flights",
        "security_share_std": round(security_std, 4),
        "dropped_security_share": dropped_security,
        "features": features,
    }
    return out.reset_index(drop=True), meta


def scale_features(frame: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, StandardScaler]:
    scaler = StandardScaler()
    scaled = scaler.fit_transform(frame[features])
    return scaled, scaler


def pca_summary(scaled: np.ndarray) -> dict:
    pca = PCA(random_state=RANDOM_STATE)
    pca.fit(scaled)
    ratios = pca.explained_variance_ratio_
    two = float(ratios[:2].sum())
    return {
        "explained_variance_ratio": [round(float(r), 4) for r in ratios],
        "variance_first_two": round(two, 4),
        "cluster_in_pca_space": two >= PCA_CLUSTER_VARIANCE,
        "pca_rule": f"cluster in PC1–PC2 only if they explain at least {PCA_CLUSTER_VARIANCE:.0%}",
        "coords": pca.transform(scaled)[:, :2],
    }


def _sweep_k(scaled: np.ndarray) -> pd.DataFrame:
    rows = []
    for k in K_RANGE:
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
        km_labels = km.fit_predict(scaled)
        ward = AgglomerativeClustering(n_clusters=k, linkage="ward")
        ward_labels = ward.fit_predict(scaled)
        rows.append(
            {
                "k": k,
                "kmeans_inertia": float(km.inertia_),
                "kmeans_silhouette": float(silhouette_score(scaled, km_labels)),
                "ward_silhouette": float(silhouette_score(scaled, ward_labels)),
            }
        )
    return pd.DataFrame(rows)


def choose_k(sweep: pd.DataFrame) -> int:
    """k with the highest K-Means silhouette. Exact ties use the smaller k."""
    best = float(sweep["kmeans_silhouette"].max())
    close = sweep.loc[np.isclose(sweep["kmeans_silhouette"], best), "k"]
    return int(close.min())


def fit_cluster_models(scaled: np.ndarray, k: int) -> dict:
    km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
    km_labels = km.fit_predict(scaled)
    ward = AgglomerativeClustering(n_clusters=k, linkage="ward")
    ward_labels = ward.fit_predict(scaled)
    return {
        "k": k,
        "kmeans_labels": km_labels,
        "ward_labels": ward_labels,
        "kmeans_silhouette": float(silhouette_score(scaled, km_labels)),
        "ward_silhouette": float(silhouette_score(scaled, ward_labels)),
        "adjusted_rand": float(adjusted_rand_score(km_labels, ward_labels)),
    }


def _mode_share(series: pd.Series) -> str:
    counts = series.value_counts(normalize=True)
    top = counts.index[0]
    return f"{top} ({100 * counts.iloc[0]:.0f}%)"


def profile_clusters(frame: pd.DataFrame, label_col: str, features: list[str]) -> pd.DataFrame:
    rows = []
    for label, part in frame.groupby(label_col, sort=True):
        row = {
            "method": label_col,
            "cluster": int(label),
            "n_rows": int(len(part)),
            "share_of_rows": round(len(part) / len(frame), 4),
            "median_arr_flights": float(part["arr_flights"].median()),
            "iqr_outlier_pct": round(100 * part["iqr_outlier_pct_delayed"].mean(), 1),
            "top_airports": ", ".join(
                part["airport"].value_counts().head(3).index.tolist()
            ),
            "slot_airport_pct": round(100 * part["airport"].isin(SLOT_AIRPORTS).mean(), 1),
            "top_season": _mode_share(part["season"]),
        }
        for feat in features:
            row[f"mean_{feat}"] = round(float(part[feat].mean()), 2)
        rows.append(row)
    return pd.DataFrame(rows)


def run_clustering(df: pd.DataFrame) -> dict:
    """Prepare rates, choose k, fit K-Means and Ward, and profile both."""
    frame, meta = prepare_cluster_frame(df)
    features = meta["features"]
    scaled, _scaler = scale_features(frame, features)
    pca = pca_summary(scaled)
    space = pca["coords"] if pca["cluster_in_pca_space"] else scaled
    sweep = _sweep_k(space)
    k = choose_k(sweep)
    models = fit_cluster_models(space, k)
    frame = frame.copy()
    frame["kmeans_cluster"] = models["kmeans_labels"]
    frame["ward_cluster"] = models["ward_labels"]
    profiles = pd.concat(
        [
            profile_clusters(frame, "kmeans_cluster", features),
            profile_clusters(frame, "ward_cluster", features),
        ],
        ignore_index=True,
    )
    return {
        "frame": frame,
        "meta": meta,
        "features": features,
        "scaled": scaled,
        "space": space,
        "pca": {k_: v for k_, v in pca.items() if k_ != "coords"},
        "pca_coords": pca["coords"],
        "sweep": sweep,
        "models": {k_: v for k_, v in models.items() if not k_.endswith("labels")},
        "profiles": profiles,
    }


def save_cluster_figures(result: dict, fig_dir: Path) -> list[Path]:
    """Save the k sweep, two PCA scatters, and a profile heatmap."""
    fig_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    written: list[Path] = []

    sweep = result["sweep"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(sweep["k"], sweep["kmeans_silhouette"], marker="o", label="K-Means")
    ax.plot(sweep["k"], sweep["ward_silhouette"], marker="s", label="Ward")
    chosen = result["models"]["k"]
    ax.axvline(chosen, color="0.4", ls="--", lw=1, label=f"chosen k={chosen}")
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Mean silhouette")
    ax.set_title("Silhouette vs k (same scaled features)")
    ax.legend()
    path = fig_dir / "13_cluster_silhouette_vs_k.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    coords = result["pca_coords"]
    frame = result["frame"]
    var = result["pca"]["variance_first_two"]
    for col, fname, title in (
        ("kmeans_cluster", "14_kmeans_pca_scatter.png", "K-Means clusters"),
        ("ward_cluster", "15_ward_pca_scatter.png", "Ward clusters"),
    ):
        fig, ax = plt.subplots(figsize=(8, 5.5))
        plot_df = pd.DataFrame(
            {
                "PC1": coords[:, 0],
                "PC2": coords[:, 1],
                "cluster": frame[col].astype(str),
            }
        )
        sns.scatterplot(
            data=plot_df,
            x="PC1",
            y="PC2",
            hue="cluster",
            s=12,
            alpha=0.45,
            ax=ax,
            linewidth=0,
        )
        ax.set_title(f"{title} on PC1–PC2 ({100 * var:.0f}% of scaled variance)")
        ax.set_xlabel("PC1")
        ax.set_ylabel("PC2")
        path = fig_dir / fname
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        written.append(path)

    features = result["features"]
    share_cols = [f for f in features if f.startswith("share_")]
    heat = result["profiles"].copy()
    heat["row"] = heat["method"].str.replace("_cluster", "") + " " + heat["cluster"].astype(str)
    heat_vals = heat.set_index("row")[[f"mean_{f}" for f in share_cols]]
    heat_vals.columns = [c.replace("mean_share_", "") for c in heat_vals.columns]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1, 1.4]})
    delay_plot = heat.melt(
        id_vars=["row"],
        value_vars=["mean_pct_delayed", "mean_pct_cancelled"],
        var_name="metric",
        value_name="percent",
    )
    delay_plot["metric"] = delay_plot["metric"].map(
        {
            "mean_pct_delayed": "delayed 15+ min",
            "mean_pct_cancelled": "cancelled",
        }
    )
    sns.barplot(data=delay_plot, x="row", y="percent", hue="metric", ax=axes[0])
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Mean percent")
    axes[0].set_title("Delay and cancel rates")
    sns.heatmap(heat_vals, annot=True, fmt=".2f", cmap="Blues", ax=axes[1])
    axes[1].set_title("Mean share of delay minutes")
    axes[1].set_ylabel("")
    path = fig_dir / "16_cluster_profile_heatmap.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)
    return written


def assignment_table(result: dict) -> pd.DataFrame:
    cols = [
        "year",
        "month",
        "carrier",
        "airport",
        "arr_flights",
        "pct_delayed",
        "pct_cancelled",
        "kmeans_cluster",
        "ward_cluster",
        "iqr_outlier_pct_delayed",
    ]
    return result["frame"][cols].copy()
