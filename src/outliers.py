"""Outlier flags for carrier–airport–month delay profiles.

Three definitions share the clustering population and the same scaled features.

* Tukey IQR on ``pct_delayed`` and ``pct_cancelled`` (a rate is extreme).
* Mean Euclidean distance to the k nearest neighbors (the profile is isolated).
* Isolation forest (the profile is easy to split off from the rest).

A consensus outlier is a month flagged by at least two of those three.
Rows are flagged, not dropped.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import NearestNeighbors

from .cleaning import iqr_outlier_mask, logical_checks
from .clustering import (
    RANDOM_STATE,
    SLOT_AIRPORTS,
    pca_summary,
    prepare_cluster_frame,
    scale_features,
)

IQR_K = 1.5
KNN_K = 15
KNN_SENSITIVITY = (5, 15, 30)
IF_ESTIMATORS = 200
IF_CONTAMINATION = 0.05

PATTERN_ORDER = ("inlier", "rate_only", "shape_only", "rate_and_shape")
PATTERN_COLORS = {
    "inlier": "#b0b6c2",
    "rate_only": "#d97706",
    "shape_only": "#2563eb",
    "rate_and_shape": "#b91c1c",
}
PATTERN_LABELS = {
    "inlier": "inlier",
    "rate_only": "rate only (IQR)",
    "shape_only": "shape only (k-NN or forest)",
    "rate_and_shape": "rate and shape",
}


def _upper_fence(series: pd.Series, k: float = IQR_K) -> dict:
    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    iqr = q3 - q1
    return {
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lower": q1 - k * iqr,
        "upper": q3 + k * iqr,
    }


def _knn_mean_distance(scaled: np.ndarray, k: int) -> np.ndarray:
    """Mean Euclidean distance to ``k`` other rows. The zero self-distance is dropped."""
    nn = NearestNeighbors(n_neighbors=k + 1, metric="euclidean")
    nn.fit(scaled)
    distances, _ = nn.kneighbors(scaled)
    return distances[:, 1:].mean(axis=1)


def _pattern_labels(frame: pd.DataFrame) -> pd.Series:
    rate = frame["flag_iqr"].to_numpy()
    shape = (frame["flag_knn"] | frame["flag_if"]).to_numpy()
    labels = np.full(len(frame), "inlier", dtype=object)
    labels[rate & ~shape] = "rate_only"
    labels[~rate & shape] = "shape_only"
    labels[rate & shape] = "rate_and_shape"
    return pd.Series(labels, index=frame.index, name="outlier_pattern")


def _profile_row(frame: pd.DataFrame, mask: pd.Series, group: str) -> dict:
    sub = frame.loc[mask]
    n = int(mask.sum())
    if n == 0:
        return {"group": group, "n_rows": 0}
    slot = sub["airport"].isin(SLOT_AIRPORTS)
    return {
        "group": group,
        "n_rows": n,
        "share_of_rows_pct": round(100 * n / len(frame), 2),
        "median_arr_flights": round(float(sub["arr_flights"].median()), 1),
        "mean_pct_delayed": round(float(sub["pct_delayed"].mean()), 2),
        "mean_pct_cancelled": round(float(sub["pct_cancelled"].mean()), 2),
        "mean_share_carrier": round(float(sub["share_carrier"].mean()), 3),
        "mean_share_weather": round(float(sub["share_weather"].mean()), 3),
        "mean_share_nas": round(float(sub["share_nas"].mean()), 3),
        "mean_share_late_aircraft": round(float(sub["share_late_aircraft"].mean()), 3),
        "slot_pct": round(100 * float(slot.mean()), 1),
        "winter_pct": round(100 * float((sub["season"] == "winter").mean()), 1),
        "summer_pct": round(100 * float((sub["season"] == "summer").mean()), 1),
    }


def _example_block(
    frame: pd.DataFrame,
    order_col: str,
    label: str,
    n: int = 5,
    *,
    ascending: bool = False,
) -> pd.DataFrame:
    cols = [
        "year",
        "month",
        "carrier",
        "airport",
        "arr_flights",
        "pct_delayed",
        "pct_cancelled",
        "share_carrier",
        "share_weather",
        "share_nas",
        "share_late_aircraft",
        "knn_score",
        "if_score",
        "flag_iqr",
        "flag_knn",
        "flag_if",
        "n_methods",
    ]
    ordered = frame.sort_values(order_col, ascending=ascending, kind="mergesort")
    out = ordered.loc[:, cols].head(n).copy()
    out.insert(0, "example", label)
    return out


def run_outlier_detection(df: pd.DataFrame) -> dict:
    """
    Flag unusual carrier–airport–months on the clustering population.

    The population and the six profile features come from
    ``prepare_cluster_frame`` (months with at least the 10th percentile of
    arrivals). Features are standardized before k-NN and the isolation forest.
    IQR fences are computed on the raw rates, not on the scaled columns.
    """
    frame, base_meta = prepare_cluster_frame(df)
    features = list(base_meta["features"])
    scaled, _scaler = scale_features(frame, features)
    pca = pca_summary(scaled)

    delay_fence = _upper_fence(frame["pct_delayed"])
    cancel_fence = _upper_fence(frame["pct_cancelled"])
    frame["flag_iqr_delay"] = iqr_outlier_mask(frame["pct_delayed"], k=IQR_K)
    frame["flag_iqr_cancel"] = iqr_outlier_mask(frame["pct_cancelled"], k=IQR_K)
    # Lower fences fall below 0 on both rates, so this is an upper-tail rule.
    frame["flag_iqr"] = frame["flag_iqr_delay"] | frame["flag_iqr_cancel"]

    knn_rows = []
    knn_flags: dict[int, np.ndarray] = {}
    knn_score = None
    knn_fence = None
    for k in KNN_SENSITIVITY:
        distances = _knn_mean_distance(scaled, k)
        fence = _upper_fence(pd.Series(distances))
        flagged = distances > fence["upper"]
        knn_flags[k] = flagged
        knn_rows.append(
            {
                "k": k,
                "upper_fence": round(fence["upper"], 4),
                "n_outliers": int(flagged.sum()),
                "outlier_pct": round(100 * float(flagged.mean()), 2),
            }
        )
        if k == KNN_K:
            knn_score = distances
            knn_fence = fence
    frame["knn_score"] = knn_score
    frame["flag_knn"] = knn_flags[KNN_K]
    for row in knn_rows:
        other = knn_flags[int(row["k"])]
        both = int((other & frame["flag_knn"].to_numpy()).sum())
        either = int((other | frame["flag_knn"].to_numpy()).sum())
        row["jaccard_with_k15"] = round(both / either, 3) if either else np.nan
    knn_sweep = pd.DataFrame(knn_rows)

    forest = IsolationForest(
        n_estimators=IF_ESTIMATORS,
        contamination=IF_CONTAMINATION,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    forest.fit(scaled)
    frame["if_score"] = forest.decision_function(scaled)
    frame["flag_if"] = forest.predict(scaled) == -1

    auto = IsolationForest(
        n_estimators=IF_ESTIMATORS,
        contamination="auto",
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    auto_flags = auto.fit_predict(scaled) == -1

    frame["n_methods"] = (
        frame[["flag_iqr", "flag_knn", "flag_if"]].sum(axis=1).astype(int)
    )
    frame["flag_consensus"] = frame["n_methods"] >= 2
    frame["outlier_pattern"] = _pattern_labels(frame)

    logic = logical_checks(frame)
    detail = logic.attrs["detail"]
    frame["logical_flag"] = detail.any(axis=1).to_numpy()

    any_flag = frame["n_methods"] > 0
    meta = {
        **base_meta,
        "definition": (
            "A month is an outlier when its delay rate is outside the Tukey "
            "fence, or its scaled delay profile is isolated from its neighbors, "
            "or an isolation forest splits it off easily. Consensus means at "
            "least two of those three flags. Flags are not deletions."
        ),
        "iqr_k": IQR_K,
        "iqr_delay_fence": {key: round(val, 4) for key, val in delay_fence.items()},
        "iqr_cancel_fence": {key: round(val, 4) for key, val in cancel_fence.items()},
        "iqr_lower_fence_binds": bool(
            delay_fence["lower"] > float(frame["pct_delayed"].min())
            or cancel_fence["lower"] > float(frame["pct_cancelled"].min())
        ),
        "knn_k": KNN_K,
        "knn_upper_fence": round(knn_fence["upper"], 4),
        "if_contamination": IF_CONTAMINATION,
        "if_n_estimators": IF_ESTIMATORS,
        "if_random_state": RANDOM_STATE,
        "if_auto_n_outliers": int(auto_flags.sum()),
        "if_auto_pct": round(100 * float(auto_flags.mean()), 2),
        "n_logical_flags": int(frame["logical_flag"].sum()),
        "n_logical_flags_among_outliers": int((frame["logical_flag"] & any_flag).sum()),
        "n_iqr_delay": int(frame["flag_iqr_delay"].sum()),
        "n_iqr_cancel": int(frame["flag_iqr_cancel"].sum()),
        "n_iqr_both_rates": int((frame["flag_iqr_delay"] & frame["flag_iqr_cancel"]).sum()),
    }

    summary = pd.DataFrame(
        [
            {
                "method": "iqr_rates",
                "n_outliers": int(frame["flag_iqr"].sum()),
                "outlier_pct": round(100 * float(frame["flag_iqr"].mean()), 2),
                "rule": (
                    f"pct_delayed outside [{delay_fence['lower']:.2f}, {delay_fence['upper']:.2f}] "
                    f"or pct_cancelled outside [{cancel_fence['lower']:.2f}, {cancel_fence['upper']:.2f}]"
                ),
            },
            {
                "method": "knn_distance",
                "n_outliers": int(frame["flag_knn"].sum()),
                "outlier_pct": round(100 * float(frame["flag_knn"].mean()), 2),
                "rule": (
                    f"mean distance to {KNN_K} nearest neighbors "
                    f"> {knn_fence['upper']:.3f} (upper Tukey fence of that score)"
                ),
            },
            {
                "method": "isolation_forest",
                "n_outliers": int(frame["flag_if"].sum()),
                "outlier_pct": round(100 * float(frame["flag_if"].mean()), 2),
                "rule": (
                    f"decision_function < 0 "
                    f"(contamination={IF_CONTAMINATION}, {IF_ESTIMATORS} trees, "
                    f"random_state={RANDOM_STATE})"
                ),
            },
            {
                "method": "consensus_at_least_two",
                "n_outliers": int(frame["flag_consensus"].sum()),
                "outlier_pct": round(100 * float(frame["flag_consensus"].mean()), 2),
                "rule": "flagged by at least two of iqr_rates, knn_distance, isolation_forest",
            },
        ]
    )

    pairs = [("flag_iqr", "flag_knn"), ("flag_iqr", "flag_if"), ("flag_knn", "flag_if")]
    agree_rows = []
    for left, right in pairs:
        both = frame[left] & frame[right]
        either = frame[left] | frame[right]
        agree_rows.append(
            {
                "method_a": left.removeprefix("flag_"),
                "method_b": right.removeprefix("flag_"),
                "n_both": int(both.sum()),
                "n_either": int(either.sum()),
                "jaccard": round(float(both.sum() / either.sum()), 3) if either.any() else np.nan,
            }
        )
    agreement = pd.DataFrame(agree_rows)

    profiles = pd.DataFrame(
        [
            _profile_row(frame, frame["outlier_pattern"] == "inlier", "inlier"),
            _profile_row(frame, frame["flag_iqr"], "iqr_rates"),
            _profile_row(frame, frame["flag_knn"], "knn_distance"),
            _profile_row(frame, frame["flag_if"], "isolation_forest"),
            _profile_row(frame, frame["flag_consensus"], "consensus_at_least_two"),
            _profile_row(frame, frame["outlier_pattern"] == "rate_only", "rate_only"),
            _profile_row(frame, frame["outlier_pattern"] == "shape_only", "shape_only"),
            _profile_row(frame, frame["outlier_pattern"] == "rate_and_shape", "rate_and_shape"),
        ]
    )

    period = pd.to_datetime(dict(year=frame["year"], month=frame["month"], day=1))
    monthly = (
        frame.assign(period=period)
        .groupby("period", as_index=False)
        .agg(
            n_rows=("airport", "size"),
            n_iqr=("flag_iqr", "sum"),
            n_knn=("flag_knn", "sum"),
            n_if=("flag_if", "sum"),
            n_consensus=("flag_consensus", "sum"),
        )
    )

    examples = pd.concat(
        [
            _example_block(frame, "pct_delayed", "highest_pct_delayed"),
            _example_block(frame, "pct_cancelled", "highest_pct_cancelled"),
            _example_block(frame, "knn_score", "highest_knn_score"),
            _example_block(frame, "if_score", "lowest_if_score", ascending=True),
        ],
        ignore_index=True,
    )

    return {
        "frame": frame,
        "features": features,
        "meta": meta,
        "summary": summary,
        "agreement": agreement,
        "profiles": profiles,
        "knn_sweep": knn_sweep,
        "monthly": monthly,
        "examples": examples,
        "pca": {k: v for k, v in pca.items() if k != "coords"},
        "pca_coords": pca["coords"],
        "logical_summary": logic,
    }


def score_table(result: dict) -> pd.DataFrame:
    """One row per analyzed month, with scores and flags."""
    cols = [
        "year",
        "month",
        "carrier",
        "airport",
        "arr_flights",
        "pct_delayed",
        "pct_cancelled",
        "share_carrier",
        "share_weather",
        "share_nas",
        "share_late_aircraft",
        "season",
        "knn_score",
        "if_score",
        "flag_iqr_delay",
        "flag_iqr_cancel",
        "flag_iqr",
        "flag_knn",
        "flag_if",
        "n_methods",
        "flag_consensus",
        "outlier_pattern",
        "logical_flag",
    ]
    return result["frame"][cols].copy()


def save_outlier_figures(result: dict, fig_dir: Path) -> list[Path]:
    """Save the PCA map, score fences, profile heatmap, and monthly counts."""
    fig_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    written: list[Path] = []
    frame = result["frame"]
    var = result["pca"]["variance_first_two"]

    fig, ax = plt.subplots(figsize=(8.2, 5.8))
    coords = result["pca_coords"]
    plot_df = pd.DataFrame(
        {
            "PC1": coords[:, 0],
            "PC2": coords[:, 1],
            "pattern": frame["outlier_pattern"].to_numpy(),
        }
    )
    for pattern in PATTERN_ORDER:
        part = plot_df[plot_df["pattern"] == pattern]
        ax.scatter(
            part["PC1"],
            part["PC2"],
            s=10 if pattern == "inlier" else 22,
            c=PATTERN_COLORS[pattern],
            alpha=0.28 if pattern == "inlier" else 0.8,
            linewidths=0,
            label=f"{PATTERN_LABELS[pattern]} (n={len(part):,})",
            zorder=1 if pattern == "inlier" else 2,
        )
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title(f"Outlier patterns on PC1–PC2 ({100 * var:.0f}% of scaled variance)")
    ax.legend(frameon=True, fontsize=8)
    path = fig_dir / "17_outlier_pca_scatter.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    delay_hi = result["meta"]["iqr_delay_fence"]["upper"]
    cancel_hi = result["meta"]["iqr_cancel_fence"]["upper"]
    knn_hi = result["meta"]["knn_upper_fence"]
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.0))
    panels = (
        (axes[0], frame["pct_delayed"], delay_hi, "Delay rate (%)", "Delay rate"),
        (axes[1], frame["pct_cancelled"], cancel_hi, "Cancel rate (%)", "Cancel rate"),
        (axes[2], frame["knn_score"], knn_hi, f"Mean distance to {KNN_K} neighbors", "k-NN distance"),
    )
    for ax, values, fence, xlabel, title in panels:
        ax.hist(values, bins=40, color="#4c566a", alpha=0.85)
        ax.axvline(fence, color="#b91c1c", ls="--", lw=1.4, label=f"Upper fence ({fence:.2f})")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Months")
        ax.set_title(title)
        ax.legend(fontsize=8)
    path = fig_dir / "18_outlier_score_thresholds.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    heat_groups = [
        "inlier",
        "iqr_rates",
        "knn_distance",
        "isolation_forest",
        "consensus_at_least_two",
    ]
    heat_labels = {
        "inlier": "inlier",
        "iqr_rates": "IQR",
        "knn_distance": "k-NN",
        "isolation_forest": "forest",
        "consensus_at_least_two": "consensus",
    }
    heat = result["profiles"].set_index("group").loc[heat_groups]
    heat.index = pd.Index([heat_labels[g] for g in heat.index], name="group")
    share = heat[
        [
            "mean_share_carrier",
            "mean_share_weather",
            "mean_share_nas",
            "mean_share_late_aircraft",
        ]
    ].rename(
        columns={
            "mean_share_carrier": "carrier",
            "mean_share_weather": "weather",
            "mean_share_nas": "NAS",
            "mean_share_late_aircraft": "late aircraft",
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1, 1.35]})
    rate_plot = heat.reset_index().melt(
        id_vars=["group"],
        value_vars=["mean_pct_delayed", "mean_pct_cancelled"],
        var_name="metric",
        value_name="percent",
    )
    rate_plot["metric"] = rate_plot["metric"].map(
        {
            "mean_pct_delayed": "delayed 15+ min",
            "mean_pct_cancelled": "cancelled",
        }
    )
    sns.barplot(data=rate_plot, x="group", y="percent", hue="metric", ax=axes[0])
    axes[0].tick_params(axis="x", rotation=0)
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Mean percent")
    axes[0].set_title("Delay and cancel rates")
    axes[0].legend(fontsize=8)
    sns.heatmap(share, annot=True, fmt=".2f", cmap="Blues", vmin=0, ax=axes[1])
    axes[1].set_title("Mean share of delay minutes")
    axes[1].set_ylabel("")
    path = fig_dir / "19_outlier_profile_heatmap.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    monthly = result["monthly"]
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    ax.plot(monthly["period"], monthly["n_iqr"], marker="o", label="IQR rates")
    ax.plot(monthly["period"], monthly["n_knn"], marker="s", label="k-NN")
    ax.plot(monthly["period"], monthly["n_if"], marker="^", label="Isolation forest")
    ax.plot(monthly["period"], monthly["n_consensus"], marker="D", label="Consensus (2+)")
    ax.set_ylabel("Flagged months")
    ax.set_xlabel("")
    ax.set_title("Outlier counts by month")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
    fig.autofmt_xdate()
    path = fig_dir / "20_outlier_counts_by_month.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)
    return written
